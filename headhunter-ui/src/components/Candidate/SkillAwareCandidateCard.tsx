import React, { useState, useEffect } from 'react';
import { Tooltip } from '@mui/material';
import { CandidateProfile, SkillAssessment, SkillMatchData } from '../../types';
import { SkillConfidenceDisplay } from '../Skills/SkillConfidenceDisplay';
import { api } from '../../services/api';
import './SkillAwareCandidateCard.css';

interface SkillAwareCandidateCardProps {
  candidate: CandidateProfile;
  matchScore?: number;
  similarity?: number;
  skillMatches?: SkillMatchData[];
  searchSkills?: string[];
  rank?: number;
  onClick?: () => void;
  showDetailedSkills?: boolean;
  onFindSimilar?: () => void;
}

export const SkillAwareCandidateCard: React.FC<SkillAwareCandidateCardProps> = ({
  candidate,
  matchScore,
  similarity,
  skillMatches = [],
  searchSkills = [],
  rank,
  onClick,
  showDetailedSkills = false,
  onFindSimilar,
}) => {
  const [expanded, setExpanded] = useState(false);
  const [skillAssessment, setSkillAssessment] = useState<SkillAssessment | null>(null);
  const [loadingSkills, setLoadingSkills] = useState(false);
  const [skillsLoaded, setSkillsLoaded] = useState(false);

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

  // Data extraction helpers
  const getExperience = () =>
    candidate.intelligent_analysis?.career_trajectory_analysis?.years_experience ||
    candidate.resume_analysis?.years_experience ||
    0;

  const getLevel = () =>
    candidate.intelligent_analysis?.career_trajectory_analysis?.current_level ||
    candidate.resume_analysis?.career_trajectory?.current_level ||
    'Not specified';

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
    if (candidate.original_data?.experience) {
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
    if (candidate.original_data?.education) {
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
    progression: candidate.intelligent_analysis?.career_trajectory_analysis?.promotion_velocity ||
      candidate.resume_analysis?.career_trajectory?.progression_speed || 'Not specified',
    type: candidate.resume_analysis?.career_trajectory?.trajectory_type || 'Not specified'
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

  const timelineData = parseExperience(candidate.original_data?.experience);

  const handleResumeClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (candidate.resume_url) {
      window.open(candidate.resume_url, '_blank');
    }
  };

  const linkedInUrl = candidate.linkedin_url || candidate.personal?.linkedin;

  // Generate a dynamic rationale if the backend one is generic
  const generateDynamicRationale = () => {
    const backendRationale = candidate.rationale?.overall_assessment ||
      (candidate.matchReasons && candidate.matchReasons.length > 0 ? candidate.matchReasons.join('. ') + '.' : '');

    if (backendRationale && backendRationale.length > 50 && !backendRationale.startsWith("Strong match based on")) {
      return backendRationale;
    }

    const role = candidate.current_role || candidate.resume_analysis?.current_role || 'Candidate';
    const years = getExperience();
    const companies = getRecentCompanies();
    const skills = technicalSkills.slice(0, 3).join(', ');

    let synthesized = `${role} with ${years} years of experience.`;
    if (companies.length > 0) {
      synthesized += ` Previously at ${companies.join(', ')}.`;
    }
    if (skills) {
      synthesized += ` Strong background in ${skills}.`;
    }

    if (matchScore && matchScore > 80) {
      synthesized += " Highly aligned with job requirements.";
    }

    return synthesized;
  };

  const dynamicRationale = generateDynamicRationale();

  // Smart Skill Grouping
  const topSkills = technicalSkills.filter(skill =>
    searchSkills.some(s => skill.toLowerCase().includes(s.toLowerCase()))
  );
  const otherSkills = technicalSkills.filter(skill =>
    !searchSkills.some(s => skill.toLowerCase().includes(s.toLowerCase()))
  );
  const displaySkills = [...topSkills, ...otherSkills].slice(0, 8);
  const remainingSkills = technicalSkills.length - 8;

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
            </div>
            <p className="candidate-level">
              {getLevel()} • {getExperience()} years
            </p>
            <p className="candidate-role">
              {candidate.current_role || candidate.resume_analysis?.current_role || 'Role not specified'}
            </p>
          </div>
        </div>

        <div className="scores">
          {matchScore !== undefined && (
            <Tooltip title="Overall alignment with job requirements." arrow placement="top">
              <div className={`score-badge ${getScoreColor(matchScore)}`}>
                <span className="score-value">{formatScore(matchScore)}%</span>
                <span className="score-label">Match</span>
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
                style={{
                  background: 'linear-gradient(135deg, #8B5CF6 0%, #6366F1 100%)',
                  color: 'white',
                  border: 'none'
                }}
              >
                Find Similar
              </button>
            )}
            {linkedInUrl ? (
              <button
                className="btn-premium btn-linkedin"
                onClick={(e) => {
                  e.stopPropagation();
                  window.open(linkedInUrl, '_blank');
                }}
              >
                Verify on LinkedIn
              </button>
            ) : (
              <button
                className="btn-premium btn-resume"
                onClick={(e) => {
                  e.stopPropagation();
                  window.open(`https://www.linkedin.com/search/results/all/?keywords=${encodeURIComponent(candidate.name)}`, '_blank');
                }}
              >
                Search LinkedIn
              </button>
            )}

            {candidate.resume_url && (
              <button className="btn-premium btn-resume" onClick={handleResumeClick}>
                View Resume
              </button>
            )}
          </div>
        </div>

        {/* 2. Smart Skill Cloud */}
        <div className="highlights-section" style={{ border: 'none', padding: '0 0 16px 0' }}>
          <div className="smart-skill-cloud">
            {displaySkills.map((skill, i) => {
              const isMatched = topSkills.includes(skill);
              return (
                <span key={i} className={`skill-chip ${isMatched ? 'matched' : 'other'}`}>
                  {skill}
                </span>
              );
            })}
            {remainingSkills > 0 && (
              <span className="more-skills-badge" onClick={(e) => { e.stopPropagation(); setExpanded(true); }}>
                +{remainingSkills} more
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
                    {timelineData.map((item, idx) => (
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