import { PubSub, type Topic } from '@google-cloud/pubsub';
import { getLogger } from '@hh/common';
import pRetry from 'p-retry';

import type { AdminPubSubConfig } from './config';
import type { RefreshPubSubAttributes, RefreshPubSubPayload } from './types';

const logger = getLogger({ module: 'admin-pubsub-client' });

export class AdminPubSubClient {
  private readonly pubsub: PubSub;
  private readonly config: AdminPubSubConfig;
  private readonly topics = new Map<string, Topic>();

  constructor(config: AdminPubSubConfig, pubsubClient?: PubSub) {
    this.config = config;
    this.pubsub = pubsubClient ?? new PubSub({ enableOpenTelemetryTracing: false });
  }

  async publishPostingsRefresh(payload: RefreshPubSubPayload): Promise<string> {
    const topic = await this.getTopic(this.config.postingsTopic);
    return this.publishMessage(topic, payload, this.buildAttributes(payload));
  }

  async publishProfilesRefresh(payload: RefreshPubSubPayload): Promise<string> {
    const topic = await this.getTopic(this.config.profilesTopic);
    return this.publishMessage(topic, payload, this.buildAttributes(payload));
  }

  async healthCheck(): Promise<boolean> {
    if (!this.config.healthCheckEnabled) {
      logger.info('Pub/Sub health check disabled via configuration.');
      return true;
    }
    try {
      await Promise.all([
        this.getTopic(this.config.postingsTopic).then((topic) => topic.get({ autoCreate: false })),
        this.getTopic(this.config.profilesTopic).then((topic) => topic.get({ autoCreate: false }))
      ]);
      return true;
    } catch (error) {
      logger.warn({ error }, 'Pub/Sub health check failed.');
      return false;
    }
  }

  private buildAttributes(payload: RefreshPubSubPayload): RefreshPubSubAttributes {
    const requestId = payload.requestId ?? `${payload.tenantId}:${payload.requestedAt}`;
    return {
      requestId,
      tenantId: payload.tenantId,
      scope: payload.scope,
      priority: payload.priority,
      force: payload.force ? 'true' : 'false'
    } satisfies RefreshPubSubAttributes;
  }

  private async getTopic(name: string): Promise<Topic> {
    const cached = this.topics.get(name);
    if (cached) {
      return cached;
    }

    const topic = this.pubsub.topic(name, {
      messageOrdering: this.config.orderingEnabled,
      batching: {
        maxMessages: 10,
        maxMilliseconds: 500
      }
    });

    this.topics.set(name, topic);
    return topic;
  }

  private async publishMessage(topic: Topic, payload: RefreshPubSubPayload, attributes: RefreshPubSubAttributes): Promise<string> {
    const maxRetries = Math.max(0, this.config.retryLimit);

    return pRetry(
      async () => {
        const timeoutMs = this.config.timeoutMs;
        let timeout: NodeJS.Timeout | undefined;
        const orderingKey = this.renderOrderingKey(attributes);
        const messageOptions: Parameters<Topic['publishMessage']>[0] = {
          data: Buffer.from(JSON.stringify(payload)),
          attributes
        };

        if (orderingKey) {
          messageOptions.orderingKey = orderingKey;
        }

        const publishPromise = topic.publishMessage(messageOptions);

        const timeoutPromise = new Promise<never>((_, reject) => {
          timeout = setTimeout(() => reject(new Error('Pub/Sub publish timed out')), timeoutMs);
        });

        try {
          const messageId = await Promise.race([publishPromise, timeoutPromise]);
          return messageId as string;
        } finally {
          if (timeout) {
            clearTimeout(timeout);
          }
        }
      },
      {
        retries: maxRetries,
        factor: 2,
        minTimeout: 200,
        onFailedAttempt: (error) => {
          logger.warn(
            {
              attemptNumber: error.attemptNumber,
              retriesLeft: error.retriesLeft,
              scope: attributes.scope,
              tenantId: attributes.tenantId
            },
            'Failed to publish refresh request.'
          );
        }
      }
    );
  }

  private renderOrderingKey(attributes: RefreshPubSubAttributes): string | undefined {
    if (!this.config.orderingEnabled) {
      return undefined;
    }

    const template = this.config.orderingKeyTemplate ?? '${scope}:${tenantId}';
    const replacements: Record<string, string | undefined> = {
      scope: attributes.scope,
      tenantId: attributes.tenantId,
      priority: attributes.priority,
      requestId: attributes.requestId,
      force: attributes.force
    };

    const rendered = template.replace(/\$\{(scope|tenantId|priority|requestId|force)\}/g, (_match, key: string) => replacements[key] ?? '');
    const trimmed = rendered.trim();
    return trimmed.length > 0 ? trimmed : undefined;
  }
}
