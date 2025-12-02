import React, { useState } from 'react';
import { Tooltip } from '@mui/material';
import { CandidateProfile, MatchRationale } from '../../types';
import './CandidateCard.css';

interface CandidateCardProps {
  candidate: CandidateProfile;
  matchScore?: number;
  similarity?: number;
  rationale?: MatchRationale;
  rank?: number;
  onClick?: () => void;
}

export const CandidateCard: React.FC<CandidateCardProps> = ({
  candidate,
  matchScore,
  similarity,
  rationale,
  rank,
  onClick,
}) => {
  const [expanded, setExpanded] = useState(false);

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

  const getRecentCompanies = () =>
    // intelligent_analysis doesn't have a clean list, fallback to resume_analysis
    candidate.resume_analysis?.company_pedigree?.recent_companies || [];

  const getCompanyTier = () =>
    candidate.resume_analysis?.company_pedigree?.tier_level || 'Unknown';

  const getTrajectory = () => ({
    progression: candidate.intelligent_analysis?.career_trajectory_analysis?.promotion_velocity ||
      candidate.resume_analysis?.career_trajectory?.progression_speed || 'Not specified',
    type: candidate.resume_analysis?.career_trajectory?.trajectory_type || 'Not specified'
  });

  const getDomainExpertise = () => {
    if (candidate.intelligent_analysis?.composite_skill_profile?.domain_specialization) {
      // Split by comma if it's a string
      return candidate.intelligent_analysis.composite_skill_profile.domain_specialization.split(',').map(s => s.trim());
    }
    return candidate.resume_analysis?.career_trajectory?.domain_expertise || [];
  };

  const getEducation = () => {
    // Check if education data exists in resume_analysis (fallback)
    // Intelligent analysis currently doesn't map education explicitly in the frontend type,
    // so we rely on resume_analysis or check if we need to add it to the type.
    // For now, return null if no data found.
    const edu = candidate.resume_analysis?.education;
    if (!edu || (!edu.highest_degree && (!edu.institutions || edu.institutions.length === 0))) return null;

    return {
      degree: edu.highest_degree || 'Not specified',
      institutions: edu.institutions || []
    };
  };

  const technicalSkills = getTechnicalSkills();
  const softSkills = getSoftSkills();
  const recentCompanies = getRecentCompanies();
  const trajectory = getTrajectory();
  const domainExpertise = getDomainExpertise();
  const educationData = getEducation(); // Renamed from 'education' to 'educationData'

  const handleResumeClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (candidate.resume_url) {
      window.open(candidate.resume_url, '_blank');
    }
  };

  const handleLinkedInClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    const url = candidate.linkedin_url || candidate.personal?.linkedin;
    if (url) {
      window.open(url, '_blank');
    }
  };

  return (
    <div className={`candidate-card ${expanded ? 'expanded' : ''}`} onClick={handleCardClick}>
      <div className="card-header">
        <div className="candidate-info">
          {rank && (
            <div className="rank-badge">
              #{rank}
            </div>
          )}
          <div className="candidate-details">
            <h3 className="candidate-name">{candidate.name}</h3>
            <p className="candidate-level">
              {getLevel()}
            </p>
            <p className="candidate-experience">
              {getExperience()} years experience
            </p>
          </div>
        </div>

        <div className="scores">
          {matchScore !== undefined && (
            <Tooltip title="Overall alignment with job requirements based on skills, experience, and context." arrow placement="top">
              <div
                className={`score-badge ${getScoreColor(matchScore)}`}
              >
                <span className="score-value">{formatScore(matchScore)}%</span>
                <span className="score-label">Match</span>
              </div>
            </Tooltip>
          )}

          {similarity !== undefined && (
            <Tooltip title="Semantic similarity between the candidate profile and job description." arrow placement="top">
              <div
                className={`score-badge ${getScoreColor(similarity)}`}
              >
                <span className="score-value">{formatScore(similarity)}%</span>
                <span className="score-label">Similarity</span>
              </div>
            </Tooltip>
          )}

          {candidate.overall_score !== undefined && (
            <Tooltip title="Composite score indicating general candidate quality and fit." arrow placement="top">
              <div
                className={`score-badge ${getScoreColor(candidate.overall_score)}`}
              >
                <span className="score-value">{formatScore(candidate.overall_score)}%</span>
                <span className="score-label">Overall</span>
              </div>
            </Tooltip>
          )}
        </div>
      </div>

      <div className="card-content">
        <div className="skills-section">
          <h4>Technical Skills</h4>
          <div className="skills-tags">
            {technicalSkills.slice(0, 5).map((skill, index) => (
              <span key={index} className="skill-tag technical">{skill}</span>
            ))}
            {technicalSkills.length > 5 && (
              <span className="skill-tag more">+{technicalSkills.length - 5}</span>
            )}
            {technicalSkills.length === 0 && <span className="text-muted">No technical skills listed</span>}
          </div>
        </div>

        {softSkills.length > 0 && (
          <div className="skill-category">
            <h4>Soft Skills</h4>
            <div className="skills-tags">
              {softSkills.slice(0, 3).map((skill, index) => (
                <span key={index} className="skill-tag soft">{skill}</span>
              ))}
              {softSkills.length > 3 && (
                <span className="skill-tag more">+{softSkills.length - 3}</span>
              )}
            </div>
          </div>
        )}

        <div className="company-info">
          <h4>Recent Companies</h4>
          {recentCompanies.length > 0 ? (
            <div className="companies">
              {recentCompanies.slice(0, 3).map((company, index) => (
                <span key={index} className="company-tag">{company}</span>
              ))}
            </div>
          ) : (
            <p className="text-muted">No recent companies listed</p>
          )}
          <span className={`tier-badge ${getCompanyTier().toLowerCase()}`}>
            {getCompanyTier()} Tier
          </span>
        </div>

        {rationale && (
          <div className="rationale-section">
            <h4>Why They Match</h4>
            <div className="rationale-content">
              {rationale.overall_assessment && (
                <p className="overall-assessment">{rationale.overall_assessment}</p>
              )}
              <ul className="strengths-list">
                {rationale.strengths.slice(0, 2).map((strength, index) => (
                  <li key={index} className="strength-item">✓ {strength}</li>
                ))}
              </ul>
            </div>

            {rationale.gaps.length > 0 && (
              <div className="rationale-section">
                <h4>Potential Gaps</h4>
                <ul className="gaps-list">
                  {rationale.gaps.slice(0, 2).map((gap, index) => (
                    <li key={index} className="gap-item">• {gap}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>

      {expanded && (
        <div className="card-details">
          <div className="details-grid">
            <div className="detail-section">
              <h4>Career Trajectory</h4>
              <p><strong>Progression:</strong> {trajectory.progression}</p>
              <p><strong>Type:</strong> {trajectory.type}</p>
              <div className="domain-expertise">
                <strong>Domain Expertise:</strong>
                {domainExpertise.length > 0 ? (
                  domainExpertise.map((domain, index) => (
                    <span key={index} className="domain-tag">{domain}</span>
                  ))
                ) : (
                  <span className="text-muted"> Not specified</span>
                )}
              </div>
            </div>

            {candidate.resume_analysis?.leadership_scope && (
              <div className="detail-section">
                <h4>Leadership</h4>
                <p><strong>Has Leadership:</strong> {candidate.resume_analysis.leadership_scope.has_leadership ? 'Yes' : 'No'}</p>
                {candidate.resume_analysis.leadership_scope.team_size && (
                  <p><strong>Team Size:</strong> {candidate.resume_analysis.leadership_scope.team_size}</p>
                )}
                {candidate.resume_analysis.leadership_scope.leadership_level && (
                  <p><strong>Level:</strong> {candidate.resume_analysis.leadership_scope.leadership_level}</p>
                )}
              </div>
            )}

            {educationData && (
              <div className="detail-section">
                <h4>Education</h4>
                <p><strong>Highest Degree:</strong> {educationData.degree}</p>
                <div className="institutions">
                  <strong>Institutions:</strong>
                  {educationData.institutions.length > 0 ? (
                    educationData.institutions.map((institution, index) => (
                      <span key={index} className="institution-tag">{institution}</span>
                    ))
                  ) : (
                    <span className="text-muted"> Not specified</span>
                  )}
                </div>
              </div>
            )}

            {candidate.recruiter_insights && (
              <div className="detail-section">
                <h4>Recruiter Insights</h4>
                <div className="recruiter-strengths">
                  <strong>Strengths:</strong>
                  <ul>
                    {(candidate.recruiter_insights.strengths || []).map((strength, index) => (
                      <li key={index}>{strength}</li>
                    ))}
                  </ul>
                </div>
                <p><strong>Recommendation:</strong> {candidate.recruiter_insights.recommendation || 'Not specified'}</p>
              </div>
            )}

            {rationale && (
              <div className="detail-section full-width">
                <h4>Complete Assessment</h4>
                <p className="overall-assessment">{rationale.overall_assessment}</p>

                {rationale.risk_factors.length > 0 && (
                  <div className="risk-factors">
                    <strong>Risk Factors:</strong>
                    <ul>
                      {rationale.risk_factors.map((risk, index) => (
                        <li key={index} className="risk-item">⚠️ {risk}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      <div className="card-footer">
        <button className="expand-button">
          {expanded ? 'Show Less' : 'Show More'}
        </button>
      </div>
    </div>
  );
};