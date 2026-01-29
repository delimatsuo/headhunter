import React, { useState, useEffect } from 'react';
import { Tooltip } from '@mui/material';
import { CandidateProfile, SkillAssessment, SkillMatchData, SignalScores, SignalWeightConfig, LLMMatchRationale } from '../../types';
import { SkillConfidenceDisplay } from '../Skills/SkillConfidenceDisplay';
import { SignalScoreBreakdown } from '../Match/SignalScoreBreakdown';
import { SkillChip } from '../Match/SkillChip';
import { TrajectoryPrediction } from './TrajectoryPrediction';
import { api } from '../../services/api';
import './SkillAwareCandidateCard.css';

// Interface for skill display data used by SkillChip
interface SkillDisplayData {
  skill: string;
  type: 'explicit' | 'inferred';
  confidence: number;
  evidence?: string;
}

interface SkillAwareCandidateCardProps {
  candidate: CandidateProfile;
  matchScore?: number;
  similarityScore?: number;  // Raw vector similarity score
  skillMatches?: SkillMatchData[];
  searchSkills?: string[];
  rank?: number;
  onClick?: () => void;
  showDetailedSkills?: boolean;
  onFindSimilar?: () => void;
  onEdit?: () => void;
  // Signal score transparency props (Phase 9)
  signalScores?: SignalScores;
  weightsApplied?: SignalWeightConfig;
  roleTypeUsed?: string;
  // LLM match rationale (TRNS-03)
  matchRationale?: LLMMatchRationale;
}

export const SkillAwareCandidateCard: React.FC<SkillAwareCandidateCardProps> = ({
  candidate,
  matchScore,
  similarityScore,
  skillMatches = [],
  searchSkills = [],
  rank,
  onClick,
  showDetailedSkills = false,
  onFindSimilar,
  onEdit,
  signalScores,
  weightsApplied,
  roleTypeUsed,
  matchRationale,
}) => {
  const [expanded, setExpanded] = useState(false);
  const [skillAssessment, setSkillAssessment] = useState<SkillAssessment | null>(null);
  const [loadingSkills, setLoadingSkills] = useState(false);
  const [skillsLoaded, setSkillsLoaded] = useState(false);
  const [signalBreakdownExpanded, setSignalBreakdownExpanded] = useState(false);

  const candidateId = candidate.candidate_id || candidate.id || '';

  useEffect(() => {
    if (expanded && showDetailedSkills && !skillsLoaded && candidateId) {
      loadSkillAssessment();
    }
  }, [expanded, showDetailedSkills, skillsLoaded, candidateId]);

  const loadSkillAssessment = async () => {
    if (!candidateId) return;

    setLoadingSkills(true);
    try {
      const response = await api.getCandidateSkillAssessment(candidateId);
      if (response.success && response.data) {
        setSkillAssessment(response.data.skill_assessment);
        setSkillsLoaded(true);
      }
    } catch (error) {
      console.error('Error loading skill assessment:', error);
    } finally {
      setLoadingSkills(false);
    }
  };

  const handleCardClick = () => {
    if (onClick) {
      onClick();
    } else {
      setExpanded(!expanded);
    }
  };

  const getScoreColor = (score: number) => {
    // Handle both 0-100 and 0-1 scales
    const normalizedScore = score <= 1 ? score * 100 : score;
    if (normalizedScore >= 80) return 'excellent';
    if (normalizedScore >= 60) return 'good';
    if (normalizedScore >= 40) return 'fair';
    return 'poor';
  };

  const formatScore = (score: number) => {
    const normalizedScore = score <= 1 ? score * 100 : score;
    return Math.round(normalizedScore);
  };

  // Check if Match Score and Similarity Score are meaningfully different
  const scoresAreDifferent = () => {
    if (matchScore === undefined || similarityScore === undefined) return false;
    const normalizedMatch = matchScore <= 1 ? matchScore * 100 : matchScore;
    const normalizedSim = similarityScore <= 1 ? similarityScore * 100 : similarityScore;
    return Math.abs(normalizedMatch - normalizedSim) > 1; // More than 1% difference
  };

  const getOverallConfidence = () => {
    if (skillAssessment) {
      return skillAssessment.average_confidence;
    }
    // Fallback calculation from basic candidate data
    return candidate.overall_score ? candidate.overall_score * 100 : 0;
  };

  const getMatchedSkillsCount = () => {
    if (!searchSkills.length) return 0;

    const technicalSkills = candidate.intelligent_analysis?.explicit_skills?.technical_skills?.map(s =>
      typeof s === 'string' ? s : s.skill
    ) || candidate.resume_analysis?.technical_skills || [];

    const softSkills = candidate.intelligent_analysis?.explicit_skills?.soft_skills?.map(s =>
      typeof s === 'string' ? s : s.skill
    ) || candidate.resume_analysis?.soft_skills || [];

    const candidateSkills = [...technicalSkills, ...softSkills].map(skill => skill.toLowerCase());

    return searchSkills.filter(skill =>
      candidateSkills.some(cSkill => cSkill.includes(skill.toLowerCase()))
    ).length;
  };

  const getSkillMatchPercentage = () => {
    if (!searchSkills.length) return 0;
    return Math.round((getMatchedSkillsCount() / searchSkills.length) * 100);
  };

  // Data extraction helpers - cast to any for flexible property access
  const c = candidate as any;

  // Handle both nested (legacy) and flat (new enrichment) schemas
  // NOTE: getLevel must be defined before getExperience since getExperience calls it

  const getLevel = () => {
    // First try explicit level fields - handle both nested and flat schemas
    const explicitLevel =
      c.current_level ||
      c.profile?.current_level ||
      c.intelligent_analysis?.career_trajectory?.current_level ||
      c.intelligent_analysis?.career_trajectory_analysis?.current_level ||
      c.intelligent_analysis?.level ||  // Flat schema from new enrichment
      c.resume_analysis?.career_trajectory?.current_level ||
      c.metadata?.current_level ||
      c.searchable?.level;

    // Normalize explicit level if found
    if (explicitLevel) {
      const levelLower = explicitLevel.toLowerCase();
      // Normalize common variations
      if (levelLower === 'mid' || levelLower === 'pleno') return 'Mid-Level';
      if (levelLower === 'jr' || levelLower === 'júnior') return 'Junior';
      if (levelLower === 'sr' || levelLower === 'sênior') return 'Senior';
      return explicitLevel;
    }

    // Try to extract seniority from the role/title AND headline
    const roleTitle = c.current_role || c.profile?.current_role || c.title || '';
    const headline = c.headline || '';
    const combinedText = `${roleTitle} ${headline}`;

    // Patterns include Portuguese equivalents
    const seniorityPatterns = [
      { pattern: /\b(principal|staff|diretor|director)\b/i, level: 'Principal' },
      { pattern: /\b(lead|tech lead|líder|lider)\b/i, level: 'Lead' },
      // Portuguese: Especialista, Sênior, Senior, Sr
      { pattern: /\b(senior|sr\.?|sênior|especialista|specialist)\b/i, level: 'Senior' },
      // Portuguese: Pleno (mid-level)
      { pattern: /\b(mid[-\s]?level|pleno)\b/i, level: 'Mid-Level' },
      // Portuguese: Júnior, Junior, Jr
      { pattern: /\b(junior|jr\.?|júnior)\b/i, level: 'Junior' },
      { pattern: /\b(intern|estagiário|estagiario|trainee)\b/i, level: 'Intern' },
    ];

    for (const { pattern, level } of seniorityPatterns) {
      if (pattern.test(combinedText)) {
        return level;
      }
    }

    return 'Not specified';
  };

  // Flat schema: intelligent_analysis.years, intelligent_analysis.level
  // Nested schema: intelligent_analysis.career_trajectory_analysis.years_experience
  const getExperience = () => {
    // Try explicit years fields first
    const explicitYears =
      c.years_experience ||
      c.profile?.years_experience ||
      c.intelligent_analysis?.career_trajectory?.years_experience ||
      c.intelligent_analysis?.career_trajectory_analysis?.years_experience ||
      c.intelligent_analysis?.years ||  // Flat schema from new enrichment
      c.resume_analysis?.years_experience ||
      c.metadata?.years_experience ||
      c.searchable?.years_experience;

    if (explicitYears && explicitYears > 0) return explicitYears;

    // Try to calculate from experience_history (oldest start date)
    const expHistory = (candidate as any).experience_history;
    if (expHistory && Array.isArray(expHistory) && expHistory.length > 0) {
      const dates = expHistory
        .map((exp: any) => exp.start_date)
        .filter((d: string) => d && /^\d{4}/.test(d))
        .map((d: string) => parseInt(d.substring(0, 4), 10))
        .filter((y: number) => y > 1990 && y <= new Date().getFullYear());

      if (dates.length > 0) {
        const oldestYear = Math.min(...dates);
        const yearsExp = new Date().getFullYear() - oldestYear;
        if (yearsExp > 0 && yearsExp < 50) return yearsExp;
      }
    }

    // Fallback: estimate years based on detected level (minimum typical experience)
    // This is a rough estimate when no explicit data is available
    const level = getLevel();
    if (level === 'Principal' || level === 'Lead') return 8;  // Principal/Lead typically 8+ years
    if (level === 'Senior') return 5;  // Senior typically 5+ years
    if (level === 'Mid-Level') return 3;  // Mid typically 3+ years
    if (level === 'Junior') return 1;  // Junior typically 1+ years

    return 0;
  };

  const getTechnicalSkills = () => {
    if (candidate.intelligent_analysis?.explicit_skills?.technical_skills) {
      return candidate.intelligent_analysis.explicit_skills.technical_skills.map(s =>
        typeof s === 'string' ? s : s.skill
      );
    }
    return candidate.resume_analysis?.technical_skills || [];
  };

  const getSoftSkills = () => {
    if (candidate.intelligent_analysis?.explicit_skills?.soft_skills) {
      return candidate.intelligent_analysis.explicit_skills.soft_skills.map(s =>
        typeof s === 'string' ? s : s.skill
      );
    }
    return candidate.resume_analysis?.soft_skills || [];
  };

  const getRecentCompanies = () => {
    const companies = candidate.resume_analysis?.company_pedigree?.recent_companies;
    if (companies && companies.length > 0) return companies;

    // Fallback to parsing original_data.experience
    if (candidate.original_data?.experience && typeof candidate.original_data.experience === 'string') {
      const lines = candidate.original_data.experience.split('\n');
      const extractedCompanies: string[] = [];
      for (const line of lines) {
        // Look for pattern like "Company : Role"
        if (line.includes(':')) {
          const parts = line.split(':');
          if (parts.length > 1) {
            // Clean up company name (remove dates if attached)
            let company = parts[0].trim();
            // Remove leading date patterns like "- 2020/10 - "
            company = company.replace(/^-\s*\d{4}\/\d{2}\s*-\s*(\d{4}\/\d{2}|current)?\s*/i, '').trim();
            if (company && company.length < 50) { // Sanity check length
              extractedCompanies.push(company);
            }
          }
        }
      }
      // Deduplicate and return top 3
      return Array.from(new Set(extractedCompanies)).slice(0, 3);
    }
    return [];
  };

  const getEducation = () => {
    const edu = candidate.resume_analysis?.education;
    if (edu && (edu.highest_degree || (edu.institutions && edu.institutions.length > 0))) {
      return {
        degree: edu.highest_degree || 'Not specified',
        institutions: edu.institutions || []
      };
    }

    // Fallback to parsing original_data.education
    if (candidate.original_data?.education && typeof candidate.original_data.education === 'string') {
      const lines = candidate.original_data.education.split('\n');
      const institutions: string[] = [];
      let degree = 'Not specified';

      for (const line of lines) {
        // Example: "- 2011/01 - 2013/01\nTecnologo - Universidade Positivo\nAnalise E Desenvolvimento"
        if (line.includes('-') && !line.match(/^\s*-\s*\d{4}/)) {
          const parts = line.split('-');
          if (parts.length > 1) {
            const potentialInst = parts[1].trim();
            if (potentialInst) institutions.push(potentialInst);
            if (degree === 'Not specified') degree = parts[0].trim();
          }
        } else if (!line.startsWith('-') && line.trim().length > 0 && !line.match(/^\d{4}/)) {
          // Assume lines that are not dates are institutions or degrees
          if (degree === 'Not specified' && (line.includes('Bachelor') || line.includes('Master') || line.includes('Degree'))) {
            degree = line.trim();
          } else {
            institutions.push(line.trim());
          }
        }
      }

      if (institutions.length > 0 || degree !== 'Not specified') {
        return {
          degree,
          institutions: Array.from(new Set(institutions)).slice(0, 2)
        };
      }
    }

    return null;
  };

  const getTrajectory = () => ({
    progression: (candidate.intelligent_analysis as any)?.career_trajectory?.progression_speed ||
      (candidate.intelligent_analysis as any)?.career_trajectory_analysis?.promotion_velocity ||
      candidate.resume_analysis?.career_trajectory?.progression_speed || 'Not specified',
    type: (candidate.intelligent_analysis as any)?.career_trajectory?.trajectory_type ||
      candidate.resume_analysis?.career_trajectory?.trajectory_type || 'Not specified'
  });

  const getDomainExpertise = () => {
    return candidate.intelligent_analysis?.career_trajectory_analysis?.domain_expertise ||
      candidate.resume_analysis?.career_trajectory?.domain_expertise || [];
  };



  const technicalSkills = getTechnicalSkills();
  const educationData = getEducation();
  const recentCompanies = getRecentCompanies();
  const trajectory = getTrajectory();
  const domainExpertise = getDomainExpertise();

  // Helper to parse experience string into structured timeline
  const parseExperience = (expString?: string) => {
    if (!expString) return [];
    const lines = expString.split('\n');
    const timeline: { date: string; role: string; company: string }[] = [];

    let currentDate = '';

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;

      // Match date line: "- 2020/10 -" or "- 2020/10 - 2021/05"
      if (trimmed.startsWith('-') && /\d{4}/.test(trimmed)) {
        currentDate = trimmed.replace(/^-/, '').trim();
      }
      // Match content line: "Company : Role" or just "Company"
      else if (currentDate) {
        const parts = trimmed.split(':');
        const company = parts[0].trim();
        const role = parts.length > 1 ? parts[1].trim() : '';

        if (company) {
          timeline.push({
            date: currentDate,
            company,
            role: role || 'Role not specified'
          });
          currentDate = ''; // Reset for next entry
        }
      }
    }
    return timeline.slice(0, 5); // Limit to top 5
  };

  // Get timeline data - prefer experience_history from PostgreSQL, with multiple fallbacks
  const getTimelineData = () => {
    // Source 1: experience_history from PostgreSQL sourcing.experience table
    const expHistory = (candidate as any).experience_history;
    if (expHistory && Array.isArray(expHistory) && expHistory.length > 0) {
      // Deduplicate by company + title + start_date
      const seen = new Set<string>();
      const deduped = expHistory.filter((exp: any) => {
        const key = `${exp.company_name}|${exp.title}|${exp.start_date}`;
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      });

      return deduped.slice(0, 5).map((exp: any) => {
        const startDate = exp.start_date || '';
        const endDate = exp.is_current ? 'Present' : (exp.end_date || '');
        const dateRange = startDate ? `${startDate} - ${endDate}` : '';
        return {
          date: dateRange,
          role: exp.title || 'Role not specified',
          company: exp.company_name || 'Company not specified'
        };
      });
    }

    // Source 2: intelligent_analysis.experience (array format from AI enrichment)
    const iaExperience = (candidate as any).intelligent_analysis?.experience;
    if (iaExperience && Array.isArray(iaExperience) && iaExperience.length > 0) {
      return iaExperience.slice(0, 5).map((exp: any) => ({
        date: exp.dates || exp.date_range || '',
        role: exp.title || exp.role || exp.position || 'Role not specified',
        company: exp.company || exp.company_name || exp.organization || 'Company not specified'
      }));
    }

    // Source 3: original_data.experience (could be string or array)
    const expData = candidate.original_data?.experience;
    // 3a: If it's a string, parse it
    if (typeof expData === 'string' && expData.trim().length > 0) {
      const parsed = parseExperience(expData);
      if (parsed.length > 0) return parsed;
    }
    // 3b: If it's an array, map it
    if (Array.isArray(expData) && expData.length > 0) {
      return (expData as any[]).slice(0, 5).map((exp: any) => ({
        date: exp.dates || exp.date_range || exp.start_date || '',
        role: exp.title || exp.role || exp.position || 'Role not specified',
        company: exp.company || exp.company_name || 'Company not specified'
      }));
    }

    // Source 4: Combine roles + companies from enrichment (if both available)
    const ia = (candidate as any).intelligent_analysis || {};
    const roles = ia.roles || [];
    const companies = ia.companies || [];
    if (roles.length > 0 && companies.length > 0) {
      // Zip roles with companies for a rough timeline
      const maxLen = Math.min(roles.length, companies.length, 5);
      const timeline: { date: string; role: string; company: string }[] = [];
      for (let i = 0; i < maxLen; i++) {
        timeline.push({
          date: i === 0 ? 'Current' : '',
          role: roles[i] || 'Role not specified',
          company: companies[i] || 'Company not specified'
        });
      }
      if (timeline.length > 0) return timeline;
    }

    // Source 5: Fallback - construct from current role/company if available
    const currentRole = c.current_role || candidate.current_role || c.title || '';
    const currentCompany = c.current_company || c.profile?.current_company || '';
    if (currentRole && currentCompany) {
      return [{
        date: 'Current',
        role: currentRole,
        company: currentCompany
      }];
    }

    // Source 6: Use just companies from enrichment with role from headline
    if (companies.length > 0) {
      const roleFromHeadline = (c.headline || '').split(' at ')[0]?.trim() ||
                               (c.headline || '').split('|')[0]?.trim() ||
                               'Software Engineer';
      return companies.slice(0, 3).map((company: string, i: number) => ({
        date: i === 0 ? 'Current' : '',
        role: i === 0 ? roleFromHeadline : 'Software Engineer',
        company: company
      }));
    }

    // Source 7: Parse from headline as last resort
    const headline = c.headline || '';
    if (headline && headline.includes(' at ')) {
      const parts = headline.split(' at ');
      if (parts.length >= 2) {
        return [{
          date: 'Current',
          role: parts[0].trim(),
          company: parts.slice(1).join(' at ').trim()
        }];
      }
    }

    // Source 8: Parse headline with pipe separator (common format)
    if (headline && headline.includes('|')) {
      const parts = headline.split('|').map((p: string) => p.trim());
      if (parts.length >= 2) {
        // Usually format is "Role | Company" or "Role at Company | Skills"
        let role = parts[0];
        let company = parts[1];
        // Check if role contains "at" for embedded company
        if (role.includes(' at ')) {
          const subParts = role.split(' at ');
          role = subParts[0].trim();
          company = subParts.slice(1).join(' at ').trim();
        }
        return [{
          date: 'Current',
          role: role,
          company: company
        }];
      }
    }

    return [];
  };

  const timelineData = getTimelineData();

  const handleResumeClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (candidate.resume_url) {
      window.open(candidate.resume_url, '_blank');
    }
  };

  // Extract and normalize LinkedIn URL - add https:// if missing
  const rawLinkedIn = candidate.linkedin_url || candidate.personal?.linkedin ||
    (candidate.intelligent_analysis as any)?.personal_details?.linkedin || '';
  const linkedInUrl = rawLinkedIn && !rawLinkedIn.startsWith('http')
    ? `https://${rawLinkedIn}`
    : rawLinkedIn;

  // Generate a dynamic, personalized rationale for each candidate
  const generateDynamicRationale = () => {
    // Check if we have a meaningful backend rationale (not template-like)
    const backendRationale = candidate.rationale?.overall_assessment ||
      (candidate.matchReasons && candidate.matchReasons.length > 0 ? candidate.matchReasons.join('. ') + '.' : '');

    // Skip backend rationale if it's template-like (contains common phrases)
    const isTemplated = backendRationale && (
      backendRationale.includes('required skills') ||
      backendRationale.includes('Excellent tech fit') ||
      backendRationale.includes('Seniority is ideal') ||
      backendRationale.includes('Missing') && backendRationale.includes('but') ||
      backendRationale.startsWith('Strong match based on')
    );

    // Use backend rationale only if it's unique and substantial
    if (backendRationale && backendRationale.length > 80 && !isTemplated) {
      return backendRationale;
    }

    // Build personalized rationale from candidate data
    const parts: string[] = [];
    const role = candidate.current_role || candidate.resume_analysis?.current_role || c.title || '';
    const years = getExperience();
    const companies = getRecentCompanies();
    const level = getLevel();

    // 1. Role and experience summary
    if (role) {
      const experiencePhrase = years > 0 ? ` with ${years}+ years` : '';
      parts.push(`${role}${experiencePhrase}`);
    }

    // 2. Company context (mention notable companies)
    if (companies.length > 0) {
      const topCompany = companies[0];
      if (companies.length === 1) {
        parts.push(`at ${topCompany}`);
      } else {
        parts.push(`currently at ${topCompany}`);
      }
    }

    // 3. Skill match analysis (personalized based on searched skills)
    const candidateSkillsLower = technicalSkills.map(s => s.toLowerCase());
    const matchedSkills = searchSkills.filter(sk =>
      candidateSkillsLower.some(cs => cs.includes(sk.toLowerCase()) || sk.toLowerCase().includes(cs))
    );

    if (matchedSkills.length > 0 && searchSkills.length > 0) {
      const matchPercent = Math.round((matchedSkills.length / searchSkills.length) * 100);
      if (matchPercent >= 80) {
        parts.push(`Strong alignment: ${matchedSkills.slice(0, 3).join(', ')}`);
      } else if (matchPercent >= 50) {
        parts.push(`Solid fit with ${matchedSkills.slice(0, 3).join(', ')}`);
      } else if (matchedSkills.length > 0) {
        parts.push(`Has ${matchedSkills.slice(0, 2).join(', ')}`);
      }
    } else if (technicalSkills.length > 0) {
      parts.push(`Skills: ${technicalSkills.slice(0, 3).join(', ')}`);
    }

    // 4. Experience fit assessment
    if (level && level !== 'Not specified') {
      const levelLower = level.toLowerCase();
      if (levelLower.includes('senior') || levelLower.includes('lead') || levelLower.includes('principal')) {
        parts.push('Experienced professional');
      } else if (levelLower.includes('mid')) {
        parts.push('Growing professional');
      }
    }

    // 5. Score-based qualifier
    const normalizedScore = matchScore ? (matchScore <= 1 ? matchScore * 100 : matchScore) : 0;
    if (normalizedScore >= 80) {
      parts.push('Excellent overall fit');
    } else if (normalizedScore >= 70) {
      parts.push('Strong match potential');
    } else if (normalizedScore >= 60) {
      parts.push('Good candidate to consider');
    }

    // Combine into readable sentence
    if (parts.length === 0) {
      return 'Profile matches search criteria.';
    }

    return parts.join('. ') + '.';
  };

  const dynamicRationale = generateDynamicRationale();

  // Helper to collect and format skills for SkillChip display
  const getSkillsForDisplay = (): SkillDisplayData[] => {
    const explicit = candidate.intelligent_analysis?.explicit_skills?.technical_skills || [];
    const inferredHigh = candidate.intelligent_analysis?.inferred_skills?.highly_probable_skills || [];
    const inferredMedium = candidate.intelligent_analysis?.inferred_skills?.probable_skills || [];
    const inferredLow = candidate.intelligent_analysis?.inferred_skills?.likely_skills || [];

    // Map explicit skills to display format
    const explicitChips: SkillDisplayData[] = explicit.map(s => ({
      skill: typeof s === 'string' ? s : s.skill,
      type: 'explicit' as const,
      confidence: 1,
    }));

    // Map inferred skills with their confidence levels
    // Cast to any to handle potential reasoning field from backend
    const inferredChips: SkillDisplayData[] = [
      ...inferredHigh.map((s: any) => ({
        skill: s.skill,
        type: 'inferred' as const,
        confidence: s.confidence,
        evidence: s.reasoning || undefined
      })),
      ...inferredMedium.map((s: any) => ({
        skill: s.skill,
        type: 'inferred' as const,
        confidence: s.confidence,
        evidence: s.reasoning || undefined
      })),
      ...inferredLow.map((s: any) => ({
        skill: s.skill,
        type: 'inferred' as const,
        confidence: s.confidence,
        evidence: s.reasoning || undefined
      })),
    ];

    // Combine and limit to 15 total skills
    return [...explicitChips, ...inferredChips].slice(0, 15);
  };

  const getRole = () => {
    // First, try to get actual job title from experience timeline (most accurate)
    const expData = c.original_data?.experience;
    const timelineData = parseExperience(typeof expData === 'string' ? expData : undefined);
    if (timelineData.length > 0 && timelineData[0].role && timelineData[0].role !== 'Role not specified') {
      return timelineData[0].role;
    }

    // Try intelligent_analysis for role competencies
    const iaRole = c.intelligent_analysis?.role_based_competencies?.current_role_competencies?.role;
    if (iaRole) return iaRole;

    // Fallback to other sources - but filter out generic seniority-only values
    const candidates = [
      c.current_role,
      c.profile?.current_role,
      c.title,
      c.resume_analysis?.current_role,
      c.analysis?.current_role?.title,
      c.searchable_data?.current_title
    ].filter(Boolean);

    for (const role of candidates) {
      // Skip if it's just a generic level like "Senior" or "Senior Leadership"
      const seniorityOnlyPattern = /^(intern|junior|associate|mid-level|senior|staff|principal|lead|manager|director|vp|head|chief|executive|leadership|member)$/i;
      const tokens = role.toLowerCase().split(/[\s-]+/);
      const isOnlySeniority = tokens.every((t: string) =>
        seniorityOnlyPattern.test(t) || t === 'level' || t === 'technical'
      );

      if (!isOnlySeniority) {
        return role;
      }
    }

    // Last resort: use level if it looks like a title
    const level = getLevel();
    if (level && level.length > 20) return level;

    return 'Role not specified';
  };

  const role = getRole();
  const rawLevel = getLevel();

  // Helper to extract just the seniority level if possible
  const getDisplayLevel = () => {
    const lowerLevel = rawLevel.toLowerCase();
    const lowerRole = role.toLowerCase();

    // If level is effectively the same as role, don't show it as "Level"
    if (lowerRole.includes(lowerLevel) || lowerLevel.includes(lowerRole)) {
      // Try to extract standard seniority terms
      const seniorityTerms = ['intern', 'junior', 'associate', 'mid-level', 'senior', 'staff', 'principal', 'lead', 'manager', 'director', 'vp', 'head', 'chief', 'executive'];
      const foundTerm = seniorityTerms.find(term => lowerLevel.includes(term));

      if (foundTerm) {
        return foundTerm.charAt(0).toUpperCase() + foundTerm.slice(1);
      }
      return null; // Hide level if it's just a duplicate title and we can't extract a simple level
    }

    return rawLevel;
  };

  const displayLevel = getDisplayLevel();

  return (
    <div className={`skill-aware-candidate-card ${expanded ? 'expanded' : ''}`}>
      <div className="card-header" onClick={handleCardClick}>
        <div className="candidate-info">
          {rank && (
            <div className="rank-badge">
              #{rank}
            </div>
          )}
          <div className="candidate-details">
            <div className="name-row">
              <h3 className="candidate-name">{candidate.name}</h3>
              {linkedInUrl && (
                <a
                  href={linkedInUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="linkedin-icon-link"
                  onClick={(e) => e.stopPropagation()}
                  title="Open LinkedIn Profile"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" data-supported-dps="24x24" fill="#0077b5" width="24" height="24" focusable="false">
                    <path d="M20.5 2h-17A1.5 1.5 0 002 3.5v17A1.5 1.5 0 003.5 22h17a1.5 1.5 0 001.5-1.5v-17A1.5 1.5 0 0020.5 2zM8 19H5v-9h3zM6.5 8.25A1.75 1.75 0 118.3 6.5a1.78 1.78 0 01-1.8 1.75zM19 19h-3v-4.74c0-1.42-.6-1.93-1.38-1.93A1.74 1.74 0 0013 14.19a.66.66 0 000 .14V19h-3v-9h2.9v1.3a3.11 3.11 0 012.7-1.4c1.55 0 3.36.86 3.36 3.66z"></path>
                  </svg>
                </a>
              )}
              {onEdit && (
                <button
                  className="edit-icon-btn"
                  onClick={(e) => {
                    e.stopPropagation();
                    onEdit();
                  }}
                  title="Edit Candidate"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" width="18" height="18">
                    <path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z" />
                  </svg>
                </button>
              )}
            </div>
            <p className="candidate-level">
              {displayLevel ? `${displayLevel} • ` : ''}{getExperience()} years
            </p>
            <p className="candidate-role">
              {role}
            </p>
          </div>
        </div>

        <div className="scores">
          {matchScore !== undefined && (
            <Tooltip title="LLM-influenced match score (considers qualitative fit)" arrow placement="top">
              <div className={`score-badge match ${getScoreColor(matchScore)}`}>
                <span className="score-value">{formatScore(matchScore)}%</span>
                <span className="score-label">Match</span>
              </div>
            </Tooltip>
          )}
          {similarityScore !== undefined && scoresAreDifferent() && (
            <Tooltip title="Raw vector similarity (semantic profile match)" arrow placement="top">
              <div className={`score-badge similarity ${getScoreColor(similarityScore)}`}>
                <span className="score-value">{formatScore(similarityScore)}%</span>
                <span className="score-label">Sim</span>
              </div>
            </Tooltip>
          )}
        </div>
      </div>

      <div className="card-content">
        {/* 1. AI Hero Section */}
        <div className="ai-hero-section">
          <div className="ai-hero-header">
            <span className="ai-icon">✨</span>
            <span className="ai-label">AI Insight</span>
          </div>
          <p className="ai-rationale">
            {dynamicRationale}
          </p>

          <div className="premium-actions">
            {onFindSimilar && (
              <button
                className="btn-premium btn-similar"
                onClick={(e) => {
                  e.stopPropagation();
                  onFindSimilar();
                }}
              >
                ✨ Find Similar Candidates
              </button>
            )}

            {candidate.resume_url && (
              <button className="btn-premium btn-resume" onClick={handleResumeClick}>
                View Resume
              </button>
            )}
          </div>
        </div>

        {/* Signal Score Breakdown - expandable section after AI hero */}
        {signalScores && (
          <div className="signal-breakdown-section">
            <button
              className="breakdown-toggle"
              onClick={(e) => {
                e.stopPropagation();
                setSignalBreakdownExpanded(!signalBreakdownExpanded);
              }}
            >
              <span>Score Breakdown</span>
              <span className={`chevron ${signalBreakdownExpanded ? 'expanded' : ''}`}>&#9660;</span>
            </button>
            {signalBreakdownExpanded && (
              <SignalScoreBreakdown
                signalScores={signalScores}
                weightsApplied={weightsApplied}
              />
            )}
          </div>
        )}

        {/* LLM Match Rationale - TRNS-03 */}
        {matchRationale && matchRationale.summary && (
          <div className="match-rationale-section">
            <h4 className="rationale-header">
              <span className="ai-sparkle-icon">&#10024;</span>
              Why This Candidate Matches
            </h4>

            <p className="rationale-summary">{matchRationale.summary}</p>

            {matchRationale.keyStrengths && matchRationale.keyStrengths.length > 0 && (
              <div className="key-strengths">
                <span className="strengths-label">Key Strengths:</span>
                <ul className="strengths-list">
                  {matchRationale.keyStrengths.map((strength, idx) => (
                    <li key={idx}>{strength}</li>
                  ))}
                </ul>
              </div>
            )}

            {matchRationale.signalHighlights && matchRationale.signalHighlights.length > 0 && (
              <div className="signal-highlights">
                {matchRationale.signalHighlights.map((highlight, idx) => (
                  <div key={idx} className="signal-highlight-item">
                    <span className="signal-highlight-name">{highlight.signal}</span>
                    <span className="signal-highlight-score">{Math.round(highlight.score * 100)}%</span>
                    <span className="signal-highlight-reason">{highlight.reason}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* 2. Smart Skill Cloud - using SkillChip with confidence badges */}
        <div className="highlights-section" style={{ border: 'none', padding: '0 0 16px 0' }}>
          <div className="smart-skill-cloud">
            {getSkillsForDisplay().map((skillData, idx) => (
              <SkillChip
                key={`${skillData.skill}-${idx}`}
                skill={skillData.skill}
                type={skillData.type}
                confidence={skillData.confidence}
                evidence={skillData.evidence}
                isMatched={searchSkills?.some(s =>
                  s.toLowerCase() === skillData.skill.toLowerCase()
                )}
              />
            ))}
            {technicalSkills.length > 15 && (
              <span className="more-skills-badge" onClick={(e) => { e.stopPropagation(); setExpanded(true); }}>
                +{technicalSkills.length - 15} more
              </span>
            )}
          </div>
        </div>

        {/* Expanded Details */}
        {expanded && (
          <div className="card-details">
            <div className="divider"></div>

            <div className="details-grid">
              {/* 3. Visual Timeline */}
              <div className="detail-section" style={{ gridColumn: '1 / -1' }}>
                <h4>Experience Timeline</h4>
                {timelineData.length > 0 ? (
                  <div className="visual-timeline">
                    {timelineData.map((item: { date: string; role: string; company: string }, idx: number) => (
                      <div key={idx} className="timeline-item">
                        <div className="timeline-dot"></div>
                        <div className="timeline-content">
                          <span className="timeline-role">{item.role}</span>
                          <span className="timeline-company">{item.company}</span>
                          <span className="timeline-date">{item.date}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p style={{ color: '#666', fontStyle: 'italic' }}>No detailed timeline available.</p>
                )}
              </div>

              {educationData && (
                <div className="detail-section">
                  <h4>Education</h4>
                  <p><strong>Highest Degree:</strong> {educationData.degree}</p>
                  <div className="institutions">
                    {educationData.institutions.map((inst, index) => (
                      <span key={index} className="institution-tag">{inst}</span>
                    ))}
                  </div>
                </div>
              )}

              {/* Career Trajectory */}
              {(trajectory.progression !== 'Not specified' || trajectory.type !== 'Not specified') && (
                <div className="detail-section">
                  <h4>Career Trajectory</h4>
                  <div className="trajectory-info">
                    {trajectory.type !== 'Not specified' && (
                      <p><strong>Path:</strong> {trajectory.type.charAt(0).toUpperCase() + trajectory.type.slice(1)}</p>
                    )}
                    {trajectory.progression !== 'Not specified' && (
                      <p><strong>Progression:</strong> {trajectory.progression.charAt(0).toUpperCase() + trajectory.progression.slice(1)}</p>
                    )}
                  </div>
                </div>
              )}

              {/* ML Trajectory Prediction - Phase 13 */}
              {candidate.mlTrajectory && (
                <div className="detail-section" style={{ gridColumn: '1 / -1' }}>
                  <h4 className="text-xs font-medium text-gray-500 mb-2">
                    ML Trajectory Prediction
                  </h4>
                  <TrajectoryPrediction prediction={candidate.mlTrajectory} />
                </div>
              )}
            </div>

            {showDetailedSkills && !skillsLoaded && (
              <button onClick={loadSkillAssessment} className="load-skills-button" style={{ marginTop: '16px' }}>
                Load Deep Skill Analysis
              </button>
            )}
          </div>
        )}
      </div>

      <div className="card-footer" onClick={() => setExpanded(!expanded)}>
        <button className="expand-button">
          {expanded ? 'Hide Details' : 'Show Full Profile'}
        </button>
      </div>
    </div>
  );
};