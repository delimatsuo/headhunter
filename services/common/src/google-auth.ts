import { GoogleAuth, type IdTokenClient } from 'google-auth-library';

interface CachedClient {
  client: IdTokenClient;
  token?: string;
  expiresAt?: number;
}

const TOKEN_TTL_MS = 55 * 60 * 1000; // refresh a little before the one hour expiry

export class IdTokenManager {
  private readonly auth = new GoogleAuth();
  private readonly clients = new Map<string, CachedClient>();
  private readonly inflight = new Map<string, Promise<string>>();

  async getToken(audience: string): Promise<string> {
    const normalized = audience.trim();
    const cached = this.clients.get(normalized);
    const now = Date.now();

    if (cached?.token && cached.expiresAt && now < cached.expiresAt) {
      return cached.token;
    }

    const existing = this.inflight.get(normalized);
    if (existing) {
      return existing;
    }

    const request = this.fetchToken(normalized);
    this.inflight.set(normalized, request);
    try {
      return await request;
    } finally {
      this.inflight.delete(normalized);
    }
  }

  private async fetchToken(audience: string): Promise<string> {
    let entry = this.clients.get(audience);
    if (!entry) {
      const client = await this.auth.getIdTokenClient(audience);
      entry = { client } satisfies CachedClient;
      this.clients.set(audience, entry);
    }

    const headers = await entry.client.getRequestHeaders();
    const authHeader = headers.Authorization ?? headers.authorization;
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      throw new Error('Failed to acquire ID token from GoogleAuth.');
    }

    const token = authHeader.slice('Bearer '.length);
    entry.token = token;
    entry.expiresAt = Date.now() + TOKEN_TTL_MS;
    return token;
  }
}

let sharedManager: IdTokenManager | null = null;

export function getIdTokenManager(): IdTokenManager {
  if (!sharedManager) {
    sharedManager = new IdTokenManager();
  }
  return sharedManager;
}
