export const createRemoteJWKSet = () => ({
  // no-op stub
});

export const jwtVerify = async (...args: unknown[]) => {
  const mock = (globalThis as unknown as Record<string, unknown>).__jwtVerifyMock;
  if (typeof mock !== 'function') {
    throw new Error('jwtVerifyMock not configured');
  }
  return mock(...args);
};
