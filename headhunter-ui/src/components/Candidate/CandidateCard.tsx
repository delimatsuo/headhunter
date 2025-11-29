import React, { useState } from 'react';
import { CandidateProfile, MatchRationale } from '../../types';

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
    if (score >= 0.8) return 'excellent';
    if (score >= 0.6) return 'good';
    if (score >= 0.4) return 'fair';
    return 'poor';
  };

  const formatScore = (score: number) => {
    if (score > 1) return Math.round(score);
    return Math.round(score * 100);
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
              {candidate.resume_analysis?.career_trajectory?.current_level || 'Not specified'}
            </p>
            <p className="candidate-experience">
              {candidate.resume_analysis?.years_experience || 0} years experience
            </p>
          </div>
        </div>

        <div className="scores">
          {matchScore !== undefined && (
            <div className={`score-badge ${getScoreColor(matchScore)}`}>
              <span className="score-value">{formatScore(matchScore)}%</span>
              <span className="score-label">Match</span>
            </div>
          )}

          {similarity !== undefined && (
            <div className={`score-badge ${getScoreColor(similarity)}`}>
              <span className="score-value">{formatScore(similarity)}%</span>
              <span className="score-label">Similarity</span>
            </div>
          )}

          <div className={`score-badge ${getScoreColor(candidate.overall_score || 0)}`}>
            <span className="score-value">{formatScore(candidate.overall_score || 0)}%</span>
            <span className="score-label">Overall</span>
          </div>
        </div>
      </div>

      <div className="card-content">
        <div className="skills-preview">
          <div className="skill-category">
            <h4>Technical Skills</h4>
            <div className="skills-tags">
              {(candidate.resume_analysis?.technical_skills || []).slice(0, 4).map((skill, index) => (
                <span key={index} className="skill-tag technical">{skill}</span>
              ))}
              {(candidate.resume_analysis?.technical_skills?.length || 0) > 4 && (
                <span className="skill-tag more">+{(candidate.resume_analysis?.technical_skills?.length || 0) - 4}</span>
              )}
            </div>
          </div>

          {(candidate.resume_analysis?.soft_skills?.length || 0) > 0 && (
            <div className="skill-category">
              <h4>Soft Skills</h4>
              <div className="skills-tags">
                {(candidate.resume_analysis?.soft_skills || []).slice(0, 3).map((skill, index) => (
                  <span key={index} className="skill-tag soft">{skill}</span>
                ))}
                {(candidate.resume_analysis?.soft_skills?.length || 0) > 3 && (
                  <span className="skill-tag more">+{(candidate.resume_analysis?.soft_skills?.length || 0) - 3}</span>
                )}
              </div>
            </div>
          )}
        </div>

        <div className="company-info">
          <h4>Recent Companies</h4>
          <div className="companies">
            {(candidate.resume_analysis?.company_pedigree?.recent_companies || []).slice(0, 3).map((company, index) => (
              <span key={index} className="company-tag">{company}</span>
            ))}
          </div>
          <span className={`tier-badge ${(candidate.resume_analysis?.company_pedigree?.tier_level || 'unknown').toLowerCase()}`}>
            {candidate.resume_analysis?.company_pedigree?.tier_level || 'Unknown'} Tier
          </span>
        </div>

        {rationale && (
          <div className="match-rationale">
            <div className="rationale-section">
              <h4>Why They Match</h4>
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
              <p><strong>Progression:</strong> {candidate.resume_analysis?.career_trajectory?.progression_speed || 'Not specified'}</p>
              <p><strong>Type:</strong> {candidate.resume_analysis?.career_trajectory?.trajectory_type || 'Not specified'}</p>
              <div className="domain-expertise">
                <strong>Domain Expertise:</strong>
                {(candidate.resume_analysis?.career_trajectory?.domain_expertise || []).map((domain, index) => (
                  <span key={index} className="domain-tag">{domain}</span>
                ))}
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

            <div className="detail-section">
              <h4>Education</h4>
              <p><strong>Highest Degree:</strong> {candidate.resume_analysis?.education?.highest_degree || 'Not specified'}</p>
              <div className="institutions">
                <strong>Institutions:</strong>
                {(candidate.resume_analysis?.education?.institutions || []).map((institution, index) => (
                  <span key={index} className="institution-tag">{institution}</span>
                ))}
              </div>
            </div>

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