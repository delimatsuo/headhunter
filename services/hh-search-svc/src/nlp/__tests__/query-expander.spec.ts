import { describe, it, expect, vi, beforeEach } from 'vitest';
import { QueryExpander, expandQuerySkills } from '../query-expander';
import type { Logger } from 'pino';

// Mock the local skills-graph module
vi.mock('../../shared/skills-graph', () => ({
  getCachedSkillExpansion: vi.fn()
}));

import { getCachedSkillExpansion } from '../../shared/skills-graph';
const mockedGetCachedSkillExpansion = vi.mocked(getCachedSkillExpansion);

// Mock logger
const mockLogger = {
  info: vi.fn(),
  debug: vi.fn(),
  trace: vi.fn(),
  warn: vi.fn(),
  error: vi.fn(),
  child: vi.fn().mockReturnThis()
} as unknown as Logger;

describe('QueryExpander', () => {
  let expander: QueryExpander;

  beforeEach(() => {
    vi.clearAllMocks();

    expander = new QueryExpander(mockLogger, {
      enabled: true,
      maxDepth: 1,
      confidenceThreshold: 0.8,
      maxExpansionsPerSkill: 5,
      expandedSkillWeight: 0.6
    });
  });

  describe('expandSkills', () => {
    it('should return explicit skills when expansion is disabled', () => {
      const disabledExpander = new QueryExpander(mockLogger, { enabled: false });

      const result = disabledExpander.expandSkills(['Python', 'JavaScript']);

      expect(result.explicitSkills).toEqual(['Python', 'JavaScript']);
      expect(result.allSkills).toEqual(['Python', 'JavaScript']);
      expect(mockedGetCachedSkillExpansion).not.toHaveBeenCalled();
    });

    it('should expand Python to include Django and Flask', () => {
      mockedGetCachedSkillExpansion.mockReturnValue({
        originalSkill: 'Python',
        originalSkillId: 'python',
        relatedSkills: [
          { skillId: 'django', skillName: 'Django', relationshipType: 'direct', distance: 1, confidence: 0.9 },
          { skillId: 'flask', skillName: 'Flask', relationshipType: 'direct', distance: 1, confidence: 0.85 },
          { skillId: 'fastapi', skillName: 'FastAPI', relationshipType: 'direct', distance: 1, confidence: 0.82 }
        ]
      });

      const result = expander.expandSkills(['Python']);

      expect(result.explicitSkills).toEqual(['Python']);
      expect(result.allSkills).toContain('Python');
      expect(result.allSkills).toContain('Django');
      expect(result.allSkills).toContain('Flask');
      expect(result.allSkills).toContain('FastAPI');
    });

    it('should filter out low-confidence expansions', () => {
      mockedGetCachedSkillExpansion.mockReturnValue({
        originalSkill: 'Python',
        originalSkillId: 'python',
        relatedSkills: [
          { skillId: 'django', skillName: 'Django', relationshipType: 'direct', distance: 1, confidence: 0.9 },
          { skillId: 'ruby', skillName: 'Ruby', relationshipType: 'direct', distance: 1, confidence: 0.5 }  // Below threshold
        ]
      });

      const result = expander.expandSkills(['Python']);

      expect(result.allSkills).toContain('Django');
      expect(result.allSkills).not.toContain('Ruby');
    });

    it('should only include direct relations', () => {
      mockedGetCachedSkillExpansion.mockReturnValue({
        originalSkill: 'Python',
        originalSkillId: 'python',
        relatedSkills: [
          { skillId: 'django', skillName: 'Django', relationshipType: 'direct', distance: 1, confidence: 0.9 },
          { skillId: 'react', skillName: 'React', relationshipType: 'indirect', distance: 2, confidence: 0.85 }
        ]
      });

      const result = expander.expandSkills(['Python']);

      expect(result.allSkills).toContain('Django');
      expect(result.allSkills).not.toContain('React');
    });

    it('should respect maxExpansionsPerSkill limit', () => {
      mockedGetCachedSkillExpansion.mockReturnValue({
        originalSkill: 'Python',
        originalSkillId: 'python',
        relatedSkills: [
          { skillId: 's1', skillName: 'Skill1', relationshipType: 'direct', distance: 1, confidence: 0.95 },
          { skillId: 's2', skillName: 'Skill2', relationshipType: 'direct', distance: 1, confidence: 0.94 },
          { skillId: 's3', skillName: 'Skill3', relationshipType: 'direct', distance: 1, confidence: 0.93 },
          { skillId: 's4', skillName: 'Skill4', relationshipType: 'direct', distance: 1, confidence: 0.92 },
          { skillId: 's5', skillName: 'Skill5', relationshipType: 'direct', distance: 1, confidence: 0.91 },
          { skillId: 's6', skillName: 'Skill6', relationshipType: 'direct', distance: 1, confidence: 0.90 },
          { skillId: 's7', skillName: 'Skill7', relationshipType: 'direct', distance: 1, confidence: 0.89 }
        ]
      });

      const limitedExpander = new QueryExpander(mockLogger, {
        maxExpansionsPerSkill: 3
      });

      const result = limitedExpander.expandSkills(['Python']);

      // Should have Python + 3 expanded = 4 total
      expect(result.allSkills.length).toBe(4);
    });

    it('should not duplicate skills across expansions', () => {
      mockedGetCachedSkillExpansion.mockImplementation((skill: string) => {
        if (skill.toLowerCase() === 'python') {
          return {
            originalSkill: 'Python',
            originalSkillId: 'python',
            relatedSkills: [
              { skillId: 'django', skillName: 'Django', relationshipType: 'direct', distance: 1, confidence: 0.9 }
            ]
          };
        }
        if (skill.toLowerCase() === 'django') {
          return {
            originalSkill: 'Django',
            originalSkillId: 'django',
            relatedSkills: [
              { skillId: 'python', skillName: 'Python', relationshipType: 'direct', distance: 1, confidence: 0.9 }
            ]
          };
        }
        return { originalSkill: skill, originalSkillId: null, relatedSkills: [] };
      });

      const result = expander.expandSkills(['Python', 'Django']);

      // Python and Django explicit, no duplicates
      const uniqueSkills = new Set(result.allSkills.map(s => s.toLowerCase()));
      expect(uniqueSkills.size).toBe(result.allSkills.length);
    });

    it('should mark explicit skills with confidence 1.0', () => {
      mockedGetCachedSkillExpansion.mockReturnValue({
        originalSkill: 'Python',
        originalSkillId: 'python',
        relatedSkills: []
      });

      const result = expander.expandSkills(['Python']);

      const pythonEntry = result.expandedSkills.find(s => s.name === 'Python');
      expect(pythonEntry?.isExplicit).toBe(true);
      expect(pythonEntry?.confidence).toBe(1.0);
    });

    it('should mark expanded skills with reduced confidence', () => {
      mockedGetCachedSkillExpansion.mockReturnValue({
        originalSkill: 'Python',
        originalSkillId: 'python',
        relatedSkills: [
          { skillId: 'django', skillName: 'Django', relationshipType: 'direct', distance: 1, confidence: 0.9 }
        ]
      });

      const result = expander.expandSkills(['Python']);

      const djangoEntry = result.expandedSkills.find(s => s.name === 'Django');
      expect(djangoEntry?.isExplicit).toBe(false);
      expect(djangoEntry?.confidence).toBe(0.9 * 0.6);  // 0.54
      expect(djangoEntry?.source).toBe('Python');
    });

    it('should handle skill not found in ontology gracefully', () => {
      mockedGetCachedSkillExpansion.mockImplementation(() => {
        throw new Error('Skill not found');
      });

      const result = expander.expandSkills(['UnknownSkill']);

      expect(result.explicitSkills).toEqual(['UnknownSkill']);
      expect(result.allSkills).toEqual(['UnknownSkill']);
    });

    it('should report timing', () => {
      mockedGetCachedSkillExpansion.mockReturnValue({
        originalSkill: 'Python',
        originalSkillId: 'python',
        relatedSkills: []
      });

      const result = expander.expandSkills(['Python']);

      expect(result.timingMs).toBeGreaterThanOrEqual(0);
    });

    it('should return empty results for empty input', () => {
      const result = expander.expandSkills([]);

      expect(result.explicitSkills).toEqual([]);
      expect(result.expandedSkills).toEqual([]);
      expect(result.allSkills).toEqual([]);
      expect(mockedGetCachedSkillExpansion).not.toHaveBeenCalled();
    });

    it('should handle skills with no related skills in ontology', () => {
      mockedGetCachedSkillExpansion.mockReturnValue({
        originalSkill: 'Python',
        originalSkillId: 'python',
        relatedSkills: []
      });

      const result = expander.expandSkills(['Python']);

      expect(result.explicitSkills).toEqual(['Python']);
      expect(result.allSkills).toEqual(['Python']);
      expect(result.expandedSkills.length).toBe(1);
      expect(result.expandedSkills[0].isExplicit).toBe(true);
    });

    it('should handle null relatedSkills array', () => {
      mockedGetCachedSkillExpansion.mockReturnValue({
        originalSkill: 'Python',
        originalSkillId: 'python',
        relatedSkills: null as unknown as []
      });

      const result = expander.expandSkills(['Python']);

      expect(result.explicitSkills).toEqual(['Python']);
      expect(result.allSkills).toEqual(['Python']);
    });
  });

  describe('getSkillWeights', () => {
    it('should return weight map with normalized skill names', () => {
      mockedGetCachedSkillExpansion.mockReturnValue({
        originalSkill: 'Python',
        originalSkillId: 'python',
        relatedSkills: [
          { skillId: 'django', skillName: 'Django', relationshipType: 'direct', distance: 1, confidence: 0.9 }
        ]
      });

      const weights = expander.getSkillWeights(['Python']);

      expect(weights.get('python')).toBe(1.0);
      expect(weights.get('django')).toBe(0.9 * 0.6);
    });

    it('should handle multiple explicit skills', () => {
      mockedGetCachedSkillExpansion.mockImplementation((skill: string) => {
        if (skill.toLowerCase() === 'python') {
          return {
            originalSkill: 'Python',
            originalSkillId: 'python',
            relatedSkills: [
              { skillId: 'django', skillName: 'Django', relationshipType: 'direct', distance: 1, confidence: 0.9 }
            ]
          };
        }
        if (skill.toLowerCase() === 'react') {
          return {
            originalSkill: 'React',
            originalSkillId: 'react',
            relatedSkills: [
              { skillId: 'javascript', skillName: 'JavaScript', relationshipType: 'direct', distance: 1, confidence: 1.0 }
            ]
          };
        }
        return { originalSkill: skill, originalSkillId: null, relatedSkills: [] };
      });

      const weights = expander.getSkillWeights(['Python', 'React']);

      expect(weights.get('python')).toBe(1.0);
      expect(weights.get('react')).toBe(1.0);
      expect(weights.get('django')).toBe(0.9 * 0.6);
      expect(weights.get('javascript')).toBe(1.0 * 0.6);
    });
  });

  describe('getSearchSkills', () => {
    it('should return flat array for search queries', () => {
      mockedGetCachedSkillExpansion.mockReturnValue({
        originalSkill: 'Python',
        originalSkillId: 'python',
        relatedSkills: [
          { skillId: 'django', skillName: 'Django', relationshipType: 'direct', distance: 1, confidence: 0.9 }
        ]
      });

      const skills = expander.getSearchSkills(['Python']);

      expect(skills).toEqual(['Python', 'Django']);
    });
  });

  describe('updateConfig', () => {
    it('should update configuration at runtime', () => {
      expander.updateConfig({ maxExpansionsPerSkill: 10 });

      const config = expander.getConfig();
      expect(config.maxExpansionsPerSkill).toBe(10);
    });

    it('should preserve other config values when updating', () => {
      const originalConfig = expander.getConfig();
      expander.updateConfig({ maxExpansionsPerSkill: 10 });

      const newConfig = expander.getConfig();
      expect(newConfig.confidenceThreshold).toBe(originalConfig.confidenceThreshold);
      expect(newConfig.enabled).toBe(originalConfig.enabled);
    });
  });

  describe('getConfig', () => {
    it('should return a copy of the configuration', () => {
      const config1 = expander.getConfig();
      const config2 = expander.getConfig();

      expect(config1).toEqual(config2);
      expect(config1).not.toBe(config2); // Different objects
    });
  });

  describe('expandQuerySkills helper', () => {
    it('should work as convenience function', () => {
      mockedGetCachedSkillExpansion.mockReturnValue({
        originalSkill: 'Python',
        originalSkillId: 'python',
        relatedSkills: []
      });

      const result = expandQuerySkills(['Python'], mockLogger);

      expect(result.explicitSkills).toEqual(['Python']);
    });

    it('should accept custom config', () => {
      mockedGetCachedSkillExpansion.mockReturnValue({
        originalSkill: 'Python',
        originalSkillId: 'python',
        relatedSkills: []
      });

      const result = expandQuerySkills(['Python'], mockLogger, { enabled: false });

      expect(result.explicitSkills).toEqual(['Python']);
      // When disabled, getCachedSkillExpansion should not be called
      expect(mockedGetCachedSkillExpansion).not.toHaveBeenCalled();
    });
  });

  describe('edge cases', () => {
    it('should handle case-insensitive deduplication', () => {
      mockedGetCachedSkillExpansion.mockImplementation((skill: string) => {
        if (skill.toLowerCase() === 'python') {
          return {
            originalSkill: 'Python',
            originalSkillId: 'python',
            relatedSkills: [
              { skillId: 'django', skillName: 'DJANGO', relationshipType: 'direct', distance: 1, confidence: 0.9 }
            ]
          };
        }
        return { originalSkill: skill, originalSkillId: null, relatedSkills: [] };
      });

      // Explicitly include 'django' (lowercase) and also expand 'Python' which returns 'DJANGO' (uppercase)
      const expanderWithDjango = new QueryExpander(mockLogger, {
        enabled: true,
        maxDepth: 1,
        confidenceThreshold: 0.8,
        maxExpansionsPerSkill: 5,
        expandedSkillWeight: 0.6
      });

      const result = expanderWithDjango.expandSkills(['Python', 'django']);

      // Should only have 2 skills (Python and django), not 3 (no duplicate DJANGO)
      expect(result.allSkills.length).toBe(2);
    });

    it('should handle mixed confidence thresholds', () => {
      mockedGetCachedSkillExpansion.mockReturnValue({
        originalSkill: 'Python',
        originalSkillId: 'python',
        relatedSkills: [
          { skillId: 'django', skillName: 'Django', relationshipType: 'direct', distance: 1, confidence: 0.85 },
          { skillId: 'flask', skillName: 'Flask', relationshipType: 'direct', distance: 1, confidence: 0.79 },  // Just below threshold
          { skillId: 'fastapi', skillName: 'FastAPI', relationshipType: 'direct', distance: 1, confidence: 0.80 }  // Exactly at threshold
        ]
      });

      const result = expander.expandSkills(['Python']);

      expect(result.allSkills).toContain('Django');
      expect(result.allSkills).toContain('FastAPI');
      expect(result.allSkills).not.toContain('Flask');
    });
  });
});
