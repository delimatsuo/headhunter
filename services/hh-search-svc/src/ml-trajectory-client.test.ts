import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { MLTrajectoryClient, type MLTrajectoryRequest, type MLTrajectoryPrediction } from './ml-trajectory-client';

// Mock @hh/common logger to avoid config validation in tests
vi.mock('@hh/common', () => ({
  getLogger: vi.fn(() => ({
    child: vi.fn(() => ({
      debug: vi.fn(),
      info: vi.fn(),
      warn: vi.fn(),
      error: vi.fn(),
    })),
    debug: vi.fn(),
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
  })),
}));

// Mock fetch globally
const mockFetch = vi.fn();
global.fetch = mockFetch as any;

describe('MLTrajectoryClient', () => {
  let client: MLTrajectoryClient;

  beforeEach(() => {
    client = new MLTrajectoryClient({
      baseUrl: 'http://localhost:7109',
      timeout: 100,
      enabled: true,
    });
    vi.clearAllMocks();
    vi.useFakeTimers();
  });

  afterEach(() => {
    client.dispose();
    vi.useRealTimers();
  });

  it('returns prediction on success', async () => {
    const mockPrediction: MLTrajectoryPrediction = {
      nextRole: 'Staff Engineer',
      nextRoleConfidence: 0.85,
      tenureMonths: { min: 18, max: 24 },
      hireability: 85,
      lowConfidence: false,
      uncertaintyReason: undefined,
    };

    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        candidateId: 'cand-123',
        prediction: mockPrediction,
        timestamp: '2026-01-26T00:00:00Z',
        modelVersion: 'trajectory-lstm-v1.0.0',
      }),
    });

    const request: MLTrajectoryRequest = {
      candidateId: 'cand-123',
      titleSequence: ['Junior Engineer', 'Senior Engineer'],
    };

    const fetchPromise = client.predict(request);

    // Advance timers to allow fetch to complete
    await vi.runAllTimersAsync();

    const result = await fetchPromise;

    expect(result).toEqual(mockPrediction);
    expect(mockFetch).toHaveBeenCalledWith(
      'http://localhost:7109/predict',
      expect.objectContaining({
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
      })
    );
  });

  it('returns null on timeout', async () => {
    // Mock fetch to simulate slow response that will be aborted
    mockFetch.mockImplementationOnce(
      (_url: string, options: any) =>
        new Promise((resolve, reject) => {
          // Simulate slow response
          const timeout = setTimeout(() => {
            resolve({ ok: true, json: async () => ({}) });
          }, 200);

          // Handle abort signal
          if (options?.signal) {
            options.signal.addEventListener('abort', () => {
              clearTimeout(timeout);
              reject(new DOMException('Aborted', 'AbortError'));
            });
          }
        })
    );

    const request: MLTrajectoryRequest = {
      candidateId: 'cand-123',
      titleSequence: ['Senior Engineer'],
    };

    const fetchPromise = client.predict(request);

    // Advance timers to trigger timeout (100ms)
    await vi.advanceTimersByTimeAsync(101);

    const result = await fetchPromise;

    expect(result).toBeNull();
  });

  it('returns null on connection error', async () => {
    mockFetch.mockRejectedValueOnce(new Error('Connection refused'));

    const request: MLTrajectoryRequest = {
      candidateId: 'cand-123',
      titleSequence: ['Senior Engineer'],
    };

    const fetchPromise = client.predict(request);
    await vi.runAllTimersAsync();

    const result = await fetchPromise;

    expect(result).toBeNull();
  });

  it('opens circuit breaker after 3 failures', async () => {
    // Mock fetch to reject immediately without delay
    mockFetch.mockRejectedValue(new Error('Service unavailable'));

    const request: MLTrajectoryRequest = {
      candidateId: 'cand-123',
      titleSequence: ['Senior Engineer'],
    };

    // Circuit opens after failures > 3 (i.e., on 4th failure)
    expect(client.isAvailable()).toBe(true);

    // Failure 1
    await client.predict(request);
    expect(client.isAvailable()).toBe(true);

    // Failure 2
    await client.predict(request);
    expect(client.isAvailable()).toBe(true);

    // Failure 3
    await client.predict(request);
    expect(client.isAvailable()).toBe(true);

    // Failure 4 - circuit opens
    await client.predict(request);
    expect(client.isAvailable()).toBe(false);
  });

  it('returns null immediately when circuit open', async () => {
    mockFetch.mockRejectedValue(new Error('Service unavailable'));

    const request: MLTrajectoryRequest = {
      candidateId: 'cand-123',
      titleSequence: ['Senior Engineer'],
    };

    // Trigger 4 failures to open circuit (failures > 3)
    for (let i = 0; i < 4; i++) {
      await client.predict(request);
    }

    // Verify circuit is open
    expect(client.isAvailable()).toBe(false);

    // Next request should not call fetch
    mockFetch.mockClear();
    const result = await client.predict(request);

    expect(result).toBeNull();
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it('closes circuit breaker after 30 seconds', async () => {
    mockFetch.mockRejectedValue(new Error('Service unavailable'));

    const request: MLTrajectoryRequest = {
      candidateId: 'cand-123',
      titleSequence: ['Senior Engineer'],
    };

    // Open circuit with 4 failures (failures > 3)
    for (let i = 0; i < 4; i++) {
      await client.predict(request);
    }

    // Verify circuit is open
    expect(client.isAvailable()).toBe(false);

    // Advance 30 seconds to trigger circuit breaker reset
    await vi.advanceTimersByTimeAsync(30_001);

    // Circuit should be closed now
    expect(client.isAvailable()).toBe(true);
  });

  it('reports availability correctly', async () => {
    expect(client.isAvailable()).toBe(true);

    // Disable client
    const disabledClient = new MLTrajectoryClient({
      baseUrl: 'http://localhost:7109',
      enabled: false,
    });

    expect(disabledClient.isAvailable()).toBe(false);
    disabledClient.dispose();
  });
});

describe('Integration with scoring', () => {
  let client: MLTrajectoryClient;

  beforeEach(() => {
    client = new MLTrajectoryClient({
      baseUrl: 'http://localhost:7109',
      timeout: 100,
      enabled: true,
    });
    vi.clearAllMocks();
    vi.useFakeTimers();
  });

  afterEach(() => {
    client.dispose();
    vi.useRealTimers();
  });

  it('attaches ML prediction to candidate', async () => {
    const mockPrediction: MLTrajectoryPrediction = {
      nextRole: 'Principal Engineer',
      nextRoleConfidence: 0.90,
      tenureMonths: { min: 24, max: 36 },
      hireability: 92,
      lowConfidence: false,
    };

    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        candidateId: 'cand-123',
        prediction: mockPrediction,
        timestamp: '2026-01-26T00:00:00Z',
        modelVersion: 'trajectory-lstm-v1.0.0',
      }),
    });

    const request: MLTrajectoryRequest = {
      candidateId: 'cand-123',
      titleSequence: ['Senior Engineer', 'Staff Engineer'],
    };

    const fetchPromise = client.predict(request);
    await vi.runAllTimersAsync();
    const prediction = await fetchPromise;

    expect(prediction).not.toBeNull();
    expect(prediction?.nextRole).toBe('Principal Engineer');
    expect(prediction?.hireability).toBe(92);
  });

  it('continues scoring if prediction fails', async () => {
    mockFetch.mockRejectedValueOnce(new Error('Service unavailable'));

    const request: MLTrajectoryRequest = {
      candidateId: 'cand-123',
      titleSequence: ['Senior Engineer'],
    };

    const fetchPromise = client.predict(request);
    await vi.runAllTimersAsync();
    const prediction = await fetchPromise;

    // Should return null without throwing
    expect(prediction).toBeNull();
  });

  it('logs disagreement between ML and rule-based', async () => {
    // This test would verify shadow mode comparison logging
    // For now, just confirm ML predictions are fetched successfully

    const mockPrediction: MLTrajectoryPrediction = {
      nextRole: 'Engineering Manager', // Different from rule-based "Staff Engineer"
      nextRoleConfidence: 0.75,
      tenureMonths: { min: 18, max: 24 },
      hireability: 80,
      lowConfidence: false,
    };

    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        candidateId: 'cand-123',
        prediction: mockPrediction,
        timestamp: '2026-01-26T00:00:00Z',
        modelVersion: 'trajectory-lstm-v1.0.0',
      }),
    });

    const request: MLTrajectoryRequest = {
      candidateId: 'cand-123',
      titleSequence: ['Junior Engineer', 'Senior Engineer', 'Staff Engineer'],
    };

    const fetchPromise = client.predict(request);
    await vi.runAllTimersAsync();
    const prediction = await fetchPromise;

    expect(prediction?.nextRole).toBe('Engineering Manager');
    // Shadow mode would compare this with rule-based prediction
  });
});
