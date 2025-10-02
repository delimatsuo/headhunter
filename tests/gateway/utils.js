const REQUIRED_VARS = ['GATEWAY_URL', 'TENANT_ID', 'CLIENT_ID', 'CLIENT_SECRET', 'TOKEN_ENDPOINT'];

let fetchImpl;
if (typeof fetch === 'function') {
  fetchImpl = fetch.bind(globalThis);
} else {
  try {
    ({ fetch: fetchImpl } = require('undici'));
  } catch (error) {
    throw new Error('Fetch API is not available. Install undici or upgrade to Node 18+.');
  }
}

function getMissingEnv() {
  return REQUIRED_VARS.filter((name) => !process.env[name] || process.env[name].trim().length === 0);
}

async function requestToken() {
  const missing = getMissingEnv();
  if (missing.length > 0) {
    throw new Error(`Missing environment variables: ${missing.join(', ')}`);
  }

  const endpoint = process.env.TOKEN_ENDPOINT;
  const audience = process.env.GATEWAY_AUDIENCE || 'https://api.ella.jobs/gateway';
  const payload = {
    grant_type: 'client_credentials',
    client_id: process.env.CLIENT_ID,
    client_secret: process.env.CLIENT_SECRET,
    audience
  };

  const response = await fetchImpl(endpoint, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    const errorBody = await response.text();
    throw new Error(`Token request failed with status ${response.status}: ${errorBody}`);
  }

  const data = await response.json();
  if (!data.access_token) {
    throw new Error('Token response missing access_token');
  }

  if (typeof data.token_type === 'string' && data.token_type.toLowerCase() !== 'bearer') {
    throw new Error(`Unexpected token_type: ${data.token_type}`);
  }

  return data.access_token;
}

async function gatewayFetch(path, options = {}) {
  const baseUrl = process.env.GATEWAY_URL;
  if (!baseUrl) {
    throw new Error('GATEWAY_URL must be set');
  }

  const url = new URL(path, baseUrl.endsWith('/') ? baseUrl : `${baseUrl}/`);
  const method = options.method || 'GET';
  const headers = Object.assign({}, options.headers || {});

  if (!headers.Authorization) {
    if (!options.token) {
      throw new Error('gatewayFetch requires a bearer token');
    }
    headers.Authorization = `Bearer ${options.token}`;
  }

  headers['X-Tenant-ID'] = headers['X-Tenant-ID'] || process.env.TENANT_ID;

  let body;
  if (options.body !== undefined) {
    body = typeof options.body === 'string' ? options.body : JSON.stringify(options.body);
    headers['Content-Type'] = headers['Content-Type'] || 'application/json';
  }

  const response = await fetchImpl(url.toString(), {
    method,
    headers,
    body
  });

  return response;
}

module.exports = {
  getMissingEnv,
  requestToken,
  gatewayFetch
};
