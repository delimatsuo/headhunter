import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { EntityExtractor, createEntityExtractor, extractEntities } from '../entity-extractor';
import type { Logger } from 'pino';

// Create a shared mock function that we can control
const mockCreate = vi.fn();

// Mock together-ai with a proper class constructor
vi.mock('together-ai', () => {
  return {
    default: class MockTogether {
      chat = {
        completions: {
          create: mockCreate
        }
      };
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
      constructor(_config: { apiKey: string }) {
        // Constructor receives apiKey but we don't need to use it
      }
    }
  };
});

// Mock logger
const mockLogger = {
  info: vi.fn(),
  debug: vi.fn(),
  trace: vi.fn(),
  warn: vi.fn(),
  error: vi.fn(),
  child: vi.fn().mockReturnThis()
} as unknown as Logger;

describe('EntityExtractor', () => {
  let extractor: EntityExtractor;

  beforeEach(() => {
    vi.clearAllMocks();

    extractor = new EntityExtractor({
      config: {
        apiKey: 'test-api-key',
        model: 'test-model',
        timeoutMs: 1000,
        maxRetries: 2
      },
      logger: mockLogger
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('extractEntities', () => {
    it('should extract role and skills', async () => {
      mockCreate.mockResolvedValueOnce({
        choices: [{
          message: {
            content: JSON.stringify({
              role: 'developer',
              skills: ['Python', 'Django'],
              seniority: 'senior',
              location: 'NYC'
            })
          }
        }]
      });

      const result = await extractor.extractEntities('senior python django developer in NYC');

      expect(result.entities.role).toBe('developer');
      expect(result.entities.skills).toContain('Python');
      expect(result.entities.skills).toContain('Django');
      expect(result.entities.seniority).toBe('senior');
      expect(result.entities.location).toBe('NYC');
    });

    it('should extract experience years from "5+ years"', async () => {
      mockCreate.mockResolvedValueOnce({
        choices: [{
          message: {
            content: JSON.stringify({
              role: 'engineer',
              skills: [],
              experienceYears: { min: 5 }
            })
          }
        }]
      });

      const result = await extractor.extractEntities('engineer with 5+ years experience');

      expect(result.entities.experienceYears?.min).toBe(5);
      expect(result.entities.experienceYears?.max).toBeUndefined();
    });

    it('should extract experience years range from "3-5 years"', async () => {
      mockCreate.mockResolvedValueOnce({
        choices: [{
          message: {
            content: JSON.stringify({
              role: 'developer',
              skills: [],
              experienceYears: { min: 3, max: 5 }
            })
          }
        }]
      });

      const result = await extractor.extractEntities('developer with 3-5 years experience');

      expect(result.entities.experienceYears?.min).toBe(3);
      expect(result.entities.experienceYears?.max).toBe(5);
    });

    it('should detect remote work preference', async () => {
      mockCreate.mockResolvedValueOnce({
        choices: [{
          message: {
            content: JSON.stringify({
              role: 'engineer',
              skills: [],
              remote: true
            })
          }
        }]
      });

      const result = await extractor.extractEntities('remote software engineer');

      expect(result.entities.remote).toBe(true);
    });

    it('should filter hallucinated skills not in query', async () => {
      mockCreate.mockResolvedValueOnce({
        choices: [{
          message: {
            content: JSON.stringify({
              role: 'developer',
              skills: ['Python', 'AWS', 'Docker']  // AWS and Docker not mentioned
            })
          }
        }]
      });

      const result = await extractor.extractEntities('python developer');

      // Only Python should remain
      expect(result.entities.skills).toContain('Python');
      expect(result.entities.skills).not.toContain('AWS');
      expect(result.entities.skills).not.toContain('Docker');
    });

    it('should handle abbreviations in skill matching - js to JavaScript', async () => {
      mockCreate.mockResolvedValueOnce({
        choices: [{
          message: {
            content: JSON.stringify({
              role: 'developer',
              skills: ['JavaScript', 'TypeScript', 'Kubernetes']
            })
          }
        }]
      });

      const result = await extractor.extractEntities('js ts k8s developer');

      expect(result.entities.skills).toContain('JavaScript');
      expect(result.entities.skills).toContain('TypeScript');
      expect(result.entities.skills).toContain('Kubernetes');
    });

    it('should normalize Portuguese seniority terms - senhor', async () => {
      mockCreate.mockResolvedValueOnce({
        choices: [{
          message: {
            content: JSON.stringify({
              role: 'desenvolvedor',
              skills: ['Python'],
              seniority: 'senhor'
            })
          }
        }]
      });

      const result = await extractor.extractEntities('desenvolvedor senhor python');

      expect(result.entities.seniority).toBe('senior');
    });

    it('should normalize Portuguese seniority terms - pleno to mid', async () => {
      mockCreate.mockResolvedValueOnce({
        choices: [{
          message: {
            content: JSON.stringify({
              role: 'desenvolvedor',
              skills: ['React'],
              seniority: 'pleno'
            })
          }
        }]
      });

      const result = await extractor.extractEntities('desenvolvedor pleno react');

      expect(result.entities.seniority).toBe('mid');
    });

    it('should return empty entities for very short queries', async () => {
      const result = await extractor.extractEntities('ab');

      expect(result.entities.skills).toEqual([]);
      expect(mockCreate).not.toHaveBeenCalled();
    });

    it('should return empty entities for non-text queries', async () => {
      const result = await extractor.extractEntities('12345');

      expect(result.entities.skills).toEqual([]);
      expect(mockCreate).not.toHaveBeenCalled();
    });

    it('should handle API errors gracefully', async () => {
      mockCreate.mockRejectedValue(new Error('API error'));

      const result = await extractor.extractEntities('senior python developer');

      expect(result.entities.skills).toEqual([]);
      expect(mockLogger.error).toHaveBeenCalled();
    });

    it('should retry on failure', async () => {
      mockCreate
        .mockRejectedValueOnce(new Error('Temporary error'))
        .mockResolvedValueOnce({
          choices: [{
            message: {
              content: JSON.stringify({
                role: 'developer',
                skills: []
              })
            }
          }]
        });

      const result = await extractor.extractEntities('developer');

      expect(result.entities.role).toBe('developer');
      expect(mockCreate).toHaveBeenCalledTimes(2);
    });

    it('should report timing', async () => {
      mockCreate.mockResolvedValueOnce({
        choices: [{
          message: {
            content: JSON.stringify({ skills: [] })
          }
        }]
      });

      const result = await extractor.extractEntities('test query');

      expect(result.timingMs).toBeGreaterThanOrEqual(0);
    });

    it('should handle empty response content gracefully', async () => {
      mockCreate.mockResolvedValueOnce({
        choices: [{
          message: {
            content: ''
          }
        }]
      });

      const result = await extractor.extractEntities('test query');

      // Should return empty entities after retry failures
      expect(result.entities.skills).toEqual([]);
    });

    it('should handle missing choices gracefully', async () => {
      mockCreate.mockResolvedValueOnce({
        choices: []
      });

      const result = await extractor.extractEntities('test query');

      expect(result.entities.skills).toEqual([]);
    });

    it('should normalize role to lowercase', async () => {
      mockCreate.mockResolvedValueOnce({
        choices: [{
          message: {
            content: JSON.stringify({
              role: 'Senior Developer',
              skills: []
            })
          }
        }]
      });

      const result = await extractor.extractEntities('senior developer');

      expect(result.entities.role).toBe('senior developer');
    });

    it('should handle React.js abbreviation', async () => {
      mockCreate.mockResolvedValueOnce({
        choices: [{
          message: {
            content: JSON.stringify({
              role: 'frontend developer',
              skills: ['React.js', 'Node.js']
            })
          }
        }]
      });

      const result = await extractor.extractEntities('react node frontend developer');

      expect(result.entities.skills).toContain('React.js');
      expect(result.entities.skills).toContain('Node.js');
    });

    it('should handle GraphQL abbreviation', async () => {
      mockCreate.mockResolvedValueOnce({
        choices: [{
          message: {
            content: JSON.stringify({
              role: 'backend developer',
              skills: ['GraphQL']
            })
          }
        }]
      });

      const result = await extractor.extractEntities('gql backend developer');

      expect(result.entities.skills).toContain('GraphQL');
    });

    it('should handle MongoDB abbreviation', async () => {
      mockCreate.mockResolvedValueOnce({
        choices: [{
          message: {
            content: JSON.stringify({
              role: 'developer',
              skills: ['MongoDB']
            })
          }
        }]
      });

      const result = await extractor.extractEntities('mongo developer');

      expect(result.entities.skills).toContain('MongoDB');
    });
  });

  describe('seniority normalization', () => {
    it('should normalize jr to junior', async () => {
      mockCreate.mockResolvedValueOnce({
        choices: [{
          message: {
            content: JSON.stringify({
              seniority: 'jr',
              skills: []
            })
          }
        }]
      });

      const result = await extractor.extractEntities('jr developer');
      expect(result.entities.seniority).toBe('junior');
    });

    it('should normalize sr to senior', async () => {
      mockCreate.mockResolvedValueOnce({
        choices: [{
          message: {
            content: JSON.stringify({
              seniority: 'sr',
              skills: []
            })
          }
        }]
      });

      const result = await extractor.extractEntities('sr engineer');
      expect(result.entities.seniority).toBe('senior');
    });

    it('should normalize mgr to manager', async () => {
      mockCreate.mockResolvedValueOnce({
        choices: [{
          message: {
            content: JSON.stringify({
              seniority: 'mgr',
              skills: []
            })
          }
        }]
      });

      const result = await extractor.extractEntities('engineering mgr');
      expect(result.entities.seniority).toBe('manager');
    });

    it('should normalize tech lead to lead', async () => {
      mockCreate.mockResolvedValueOnce({
        choices: [{
          message: {
            content: JSON.stringify({
              seniority: 'tech lead',
              skills: []
            })
          }
        }]
      });

      const result = await extractor.extractEntities('tech lead position');
      expect(result.entities.seniority).toBe('lead');
    });

    it('should normalize cto to c-level', async () => {
      mockCreate.mockResolvedValueOnce({
        choices: [{
          message: {
            content: JSON.stringify({
              seniority: 'cto',
              skills: []
            })
          }
        }]
      });

      const result = await extractor.extractEntities('cto candidate');
      expect(result.entities.seniority).toBe('c-level');
    });

    it('should handle gerente (Portuguese for manager)', async () => {
      mockCreate.mockResolvedValueOnce({
        choices: [{
          message: {
            content: JSON.stringify({
              seniority: 'gerente',
              skills: []
            })
          }
        }]
      });

      const result = await extractor.extractEntities('gerente de engenharia');
      expect(result.entities.seniority).toBe('manager');
    });
  });

  describe('createEntityExtractor', () => {
    it('should throw if API key is missing', () => {
      const originalEnv = process.env.TOGETHER_API_KEY;
      delete process.env.TOGETHER_API_KEY;

      expect(() => createEntityExtractor(mockLogger, {})).toThrow('TOGETHER_API_KEY');

      process.env.TOGETHER_API_KEY = originalEnv;
    });

    it('should use environment variable for API key', () => {
      const originalEnv = process.env.TOGETHER_API_KEY;
      process.env.TOGETHER_API_KEY = 'env-api-key';

      expect(() => createEntityExtractor(mockLogger)).not.toThrow();

      process.env.TOGETHER_API_KEY = originalEnv;
    });

    it('should allow config overrides', () => {
      const originalEnv = process.env.TOGETHER_API_KEY;
      process.env.TOGETHER_API_KEY = 'env-api-key';

      const newExtractor = createEntityExtractor(mockLogger, {
        model: 'custom-model',
        timeoutMs: 500
      });

      expect(newExtractor).toBeDefined();

      process.env.TOGETHER_API_KEY = originalEnv;
    });
  });

  describe('extractEntities helper function', () => {
    it('should extract entities using the helper', async () => {
      mockCreate.mockResolvedValueOnce({
        choices: [{
          message: {
            content: JSON.stringify({
              role: 'engineer',
              skills: ['Python']
            })
          }
        }]
      });

      const entities = await extractEntities(extractor, 'python engineer');

      expect(entities.role).toBe('engineer');
      expect(entities.skills).toContain('Python');
    });
  });

  describe('natural language detection', () => {
    it('should skip extraction for single character', async () => {
      const result = await extractor.extractEntities('a');
      expect(result.entities.skills).toEqual([]);
      expect(mockCreate).not.toHaveBeenCalled();
    });

    it('should skip extraction for numbers only', async () => {
      const result = await extractor.extractEntities('123456789');
      expect(result.entities.skills).toEqual([]);
      expect(mockCreate).not.toHaveBeenCalled();
    });

    it('should skip extraction for special characters only', async () => {
      const result = await extractor.extractEntities('!@#$%^&*()');
      expect(result.entities.skills).toEqual([]);
      expect(mockCreate).not.toHaveBeenCalled();
    });

    it('should process valid short query', async () => {
      mockCreate.mockResolvedValueOnce({
        choices: [{
          message: {
            content: JSON.stringify({
              role: 'dev',
              skills: []
            })
          }
        }]
      });

      const result = await extractor.extractEntities('dev');
      expect(result).toBeDefined();
      expect(mockCreate).toHaveBeenCalled();
    });
  });
});
