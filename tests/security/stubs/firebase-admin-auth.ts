export const getAuth = () => ({
  verifyIdToken: async (...args: unknown[]) => {
    const mock = (globalThis as unknown as Record<string, any>).__firebaseVerifyMock;
    if (typeof mock !== 'function') {
      throw new Error('firebaseVerifyMock not configured');
    }
    return mock(...args);
  }
});
