const Module = require('module');
const originalLoad = Module._load;

Module._load = function patchedLoader(request, parent, isMain) {
  if (request === '@google-cloud/run') {
    class JobsClient {
      async runJob() {
        const executionName = `projects/headhunter-local/locations/us-central1/executions/mock-${Date.now()}`;
        return [{
          promise: async () => [{ name: executionName }]
        }];
      }

      async getJob() {
        return [{}];
      }
    }

    class ExecutionsClient {
      async getExecution() {
        return [{ state: 'SUCCEEDED', startTime: { seconds: Math.floor(Date.now() / 1000) } }];
      }
    }

    return { JobsClient, ExecutionsClient };
  }

  if (request === '@google-cloud/scheduler') {
    class CloudSchedulerClient {
      locationPath(project, location) {
        return `projects/${project}/locations/${location}`;
      }

      async getJob() {
        const error = new Error('not found');
        error.code = 5;
        throw error;
      }

      async createJob({ job }) {
        return [job];
      }

      async updateJob({ job }) {
        return [job];
      }
    }

    return { CloudSchedulerClient };
  }

  return originalLoad(request, parent, isMain);
};
