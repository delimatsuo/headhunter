import { describe, it, expect } from 'vitest';
import {
  expandSenioritySynonyms,
  expandRoleSynonyms,
  expandSemanticSynonyms,
  matchesSeniorityLevel,
  getSeniorityIndex,
  compareSeniorityLevels,
  SENIORITY_SYNONYMS,
  ROLE_SYNONYMS,
  SENIORITY_HIERARCHY
} from '../semantic-synonyms';

describe('semantic-synonyms', () => {
  describe('SENIORITY_SYNONYMS', () => {
    it('should have synonyms for all hierarchy levels', () => {
      for (const level of SENIORITY_HIERARCHY) {
        expect(SENIORITY_SYNONYMS[level]).toBeDefined();
        expect(Array.isArray(SENIORITY_SYNONYMS[level])).toBe(true);
      }
    });

    it('should include Portuguese terms', () => {
      expect(SENIORITY_SYNONYMS['junior']).toContain('júnior');
      expect(SENIORITY_SYNONYMS['senior']).toContain('sênior');
      expect(SENIORITY_SYNONYMS['manager']).toContain('gerente');
      expect(SENIORITY_SYNONYMS['director']).toContain('diretor');
    });
  });

  describe('ROLE_SYNONYMS', () => {
    it('should include Portuguese terms', () => {
      expect(ROLE_SYNONYMS['developer']).toContain('desenvolvedor');
      expect(ROLE_SYNONYMS['engineer']).toContain('engenheiro');
    });

    it('should have bidirectional developer/engineer mapping', () => {
      expect(ROLE_SYNONYMS['developer']).toContain('engineer');
      expect(ROLE_SYNONYMS['engineer']).toContain('developer');
    });
  });

  describe('expandSenioritySynonyms', () => {
    it('should return direct synonyms for senior', () => {
      const result = expandSenioritySynonyms('senior');

      expect(result.original).toBe('senior');
      expect(result.synonyms).toContain('senior');
      expect(result.synonyms).toContain('sr');
      expect(result.synonyms).toContain('sr.');
      expect(result.includesHigher).toBe(false);
    });

    it('should include higher levels when requested', () => {
      const result = expandSenioritySynonyms('senior', true);

      expect(result.includesHigher).toBe(true);
      expect(result.synonyms).toContain('senior');
      expect(result.synonyms).toContain('staff');
      expect(result.synonyms).toContain('principal');
      expect(result.synonyms).toContain('lead');
      expect(result.synonyms).toContain('manager');
      expect(result.synonyms).toContain('director');
    });

    it('should handle lead level with its synonyms', () => {
      const result = expandSenioritySynonyms('lead');

      expect(result.synonyms).toContain('lead');
      expect(result.synonyms).toContain('tech lead');
      expect(result.synonyms).toContain('team lead');
      expect(result.synonyms).toContain('senior');  // Lead implies senior
      expect(result.synonyms).toContain('staff');
    });

    it('should handle Portuguese terms', () => {
      const senior = expandSenioritySynonyms('senior');
      const junior = expandSenioritySynonyms('junior');

      expect(senior.synonyms).toContain('sênior');
      expect(junior.synonyms).toContain('júnior');
    });

    it('should handle unknown levels gracefully', () => {
      const result = expandSenioritySynonyms('unknown-level');

      expect(result.original).toBe('unknown-level');
      expect(result.synonyms).toContain('unknown-level');
      expect(result.synonyms.length).toBe(1);
    });

    it('should normalize input to lowercase', () => {
      const result = expandSenioritySynonyms('SENIOR');

      expect(result.original).toBe('senior');
      expect(result.synonyms).toContain('senior');
    });

    it('should trim whitespace', () => {
      const result = expandSenioritySynonyms('  senior  ');

      expect(result.original).toBe('senior');
    });

    it('should expand mid-level correctly', () => {
      const result = expandSenioritySynonyms('mid');

      expect(result.synonyms).toContain('mid');
      expect(result.synonyms).toContain('mid-level');
      expect(result.synonyms).toContain('intermediate');
      expect(result.synonyms).toContain('pleno');
    });

    it('should include higher level synonyms when expanding', () => {
      const result = expandSenioritySynonyms('junior', true);

      // Should include all higher levels and their synonyms
      expect(result.synonyms).toContain('mid');
      expect(result.synonyms).toContain('pleno');  // Mid synonym
      expect(result.synonyms).toContain('senior');
      expect(result.synonyms).toContain('sr');     // Senior synonym
    });
  });

  describe('expandRoleSynonyms', () => {
    it('should expand developer to include engineer', () => {
      const result = expandRoleSynonyms('developer');

      expect(result.original).toBe('developer');
      expect(result.synonyms).toContain('developer');
      expect(result.synonyms).toContain('engineer');
      expect(result.synonyms).toContain('programmer');
      expect(result.synonyms).toContain('coder');
    });

    it('should expand engineer to include developer', () => {
      const result = expandRoleSynonyms('engineer');

      expect(result.synonyms).toContain('engineer');
      expect(result.synonyms).toContain('developer');
      expect(result.synonyms).toContain('programmer');
    });

    it('should handle Portuguese terms', () => {
      const result = expandRoleSynonyms('developer');

      expect(result.synonyms).toContain('desenvolvedor');
    });

    it('should expand devops roles', () => {
      const result = expandRoleSynonyms('devops');

      expect(result.synonyms).toContain('devops');
      expect(result.synonyms).toContain('sre');
      expect(result.synonyms).toContain('platform engineer');
    });

    it('should expand data scientist roles', () => {
      const result = expandRoleSynonyms('data scientist');

      expect(result.synonyms).toContain('data scientist');
      expect(result.synonyms).toContain('ml engineer');
      expect(result.synonyms).toContain('data engineer');
    });

    it('should handle unknown roles gracefully', () => {
      const result = expandRoleSynonyms('unicorn wrangler');

      expect(result.original).toBe('unicorn wrangler');
      expect(result.synonyms).toContain('unicorn wrangler');
      expect(result.synonyms.length).toBe(1);
    });

    it('should always set includesHigher to false', () => {
      const result = expandRoleSynonyms('developer');

      expect(result.includesHigher).toBe(false);
    });
  });

  describe('expandSemanticSynonyms', () => {
    it('should expand both role and seniority', () => {
      const result = expandSemanticSynonyms({
        role: 'developer',
        seniority: 'senior'
      });

      expect(result.expandedRoles).toContain('developer');
      expect(result.expandedRoles).toContain('engineer');
      expect(result.expandedSeniorities).toContain('senior');
      expect(result.expandedSeniorities).toContain('staff');  // Higher level
      expect(result.expandedSeniorities).toContain('principal');
    });

    it('should handle missing role', () => {
      const result = expandSemanticSynonyms({
        seniority: 'junior'
      });

      expect(result.expandedRoles).toEqual([]);
      expect(result.expandedSeniorities.length).toBeGreaterThan(0);
    });

    it('should handle missing seniority', () => {
      const result = expandSemanticSynonyms({
        role: 'engineer'
      });

      expect(result.expandedRoles.length).toBeGreaterThan(0);
      expect(result.expandedSeniorities).toEqual([]);
    });

    it('should handle missing fields', () => {
      const result = expandSemanticSynonyms({});

      expect(result.expandedRoles).toEqual([]);
      expect(result.expandedSeniorities).toEqual([]);
    });

    it('should expand seniorityLevels array', () => {
      const result = expandSemanticSynonyms({
        seniorityLevels: ['senior', 'lead']
      });

      expect(result.expandedSeniorities).toContain('senior');
      expect(result.expandedSeniorities).toContain('sr');
      expect(result.expandedSeniorities).toContain('lead');
      expect(result.expandedSeniorities).toContain('tech lead');
    });

    it('should not duplicate seniorities from multiple sources', () => {
      const result = expandSemanticSynonyms({
        seniority: 'senior',
        seniorityLevels: ['senior', 'staff']
      });

      // Count occurrences of 'senior'
      const seniorCount = result.expandedSeniorities.filter(s => s === 'senior').length;
      expect(seniorCount).toBe(1);
    });

    it('should include seniority higher levels only from seniority field', () => {
      const result = expandSemanticSynonyms({
        seniority: 'mid',
        seniorityLevels: ['junior']
      });

      // Should include mid's higher levels (from seniority field)
      expect(result.expandedSeniorities).toContain('senior');
      expect(result.expandedSeniorities).toContain('staff');

      // Should include junior's synonyms but not higher (from seniorityLevels)
      expect(result.expandedSeniorities).toContain('junior');
      expect(result.expandedSeniorities).toContain('entry');
    });
  });

  describe('matchesSeniorityLevel', () => {
    it('should match exact level', () => {
      expect(matchesSeniorityLevel('senior', 'senior')).toBe(true);
      expect(matchesSeniorityLevel('junior', 'junior')).toBe(true);
    });

    it('should match synonym', () => {
      expect(matchesSeniorityLevel('sr', 'senior')).toBe(true);
      expect(matchesSeniorityLevel('Sr.', 'senior')).toBe(true);
    });

    it('should match higher level when allowed', () => {
      expect(matchesSeniorityLevel('staff', 'senior', true)).toBe(true);
      expect(matchesSeniorityLevel('principal', 'senior', true)).toBe(true);
      expect(matchesSeniorityLevel('director', 'mid', true)).toBe(true);
    });

    it('should not match higher level when disallowed', () => {
      expect(matchesSeniorityLevel('staff', 'senior', false)).toBe(false);
      expect(matchesSeniorityLevel('principal', 'senior', false)).toBe(false);
    });

    it('should not match lower level', () => {
      expect(matchesSeniorityLevel('junior', 'senior', true)).toBe(false);
      expect(matchesSeniorityLevel('mid', 'staff', true)).toBe(false);
    });

    it('should handle partial matches in title', () => {
      expect(matchesSeniorityLevel('senior engineer', 'senior', true)).toBe(true);
      expect(matchesSeniorityLevel('staff software engineer', 'senior', true)).toBe(true);
    });

    it('should be case insensitive', () => {
      expect(matchesSeniorityLevel('SENIOR', 'senior')).toBe(true);
      expect(matchesSeniorityLevel('Senior', 'SENIOR')).toBe(true);
    });
  });

  describe('getSeniorityIndex', () => {
    it('should return correct index for known levels', () => {
      expect(getSeniorityIndex('junior')).toBe(0);
      expect(getSeniorityIndex('mid')).toBe(1);
      expect(getSeniorityIndex('senior')).toBe(2);
      expect(getSeniorityIndex('staff')).toBe(3);
      expect(getSeniorityIndex('principal')).toBe(4);
      expect(getSeniorityIndex('c-level')).toBe(9);
    });

    it('should return -1 for unknown levels', () => {
      expect(getSeniorityIndex('unknown')).toBe(-1);
      expect(getSeniorityIndex('intern')).toBe(-1);
    });

    it('should normalize input', () => {
      expect(getSeniorityIndex('SENIOR')).toBe(2);
      expect(getSeniorityIndex('  senior  ')).toBe(2);
    });
  });

  describe('compareSeniorityLevels', () => {
    it('should return negative when first is lower', () => {
      expect(compareSeniorityLevels('junior', 'senior')).toBeLessThan(0);
      expect(compareSeniorityLevels('mid', 'staff')).toBeLessThan(0);
    });

    it('should return positive when first is higher', () => {
      expect(compareSeniorityLevels('senior', 'junior')).toBeGreaterThan(0);
      expect(compareSeniorityLevels('director', 'manager')).toBeGreaterThan(0);
    });

    it('should return zero when equal', () => {
      expect(compareSeniorityLevels('senior', 'senior')).toBe(0);
    });

    it('should return zero when either is unknown', () => {
      expect(compareSeniorityLevels('unknown', 'senior')).toBe(0);
      expect(compareSeniorityLevels('senior', 'unknown')).toBe(0);
      expect(compareSeniorityLevels('unknown1', 'unknown2')).toBe(0);
    });

    it('should handle case differences', () => {
      expect(compareSeniorityLevels('JUNIOR', 'senior')).toBeLessThan(0);
    });
  });

  describe('SENIORITY_HIERARCHY', () => {
    it('should be in ascending order of seniority', () => {
      expect(SENIORITY_HIERARCHY[0]).toBe('junior');
      expect(SENIORITY_HIERARCHY[SENIORITY_HIERARCHY.length - 1]).toBe('c-level');
    });

    it('should have 10 levels', () => {
      expect(SENIORITY_HIERARCHY.length).toBe(10);
    });
  });
});
