import React from 'react';
import { CandidateProfile } from '../../types';

interface SimpleCandidateCardProps {
  candidate: CandidateProfile;
  rank?: number;
}

export const SimpleCandidateCard: React.FC<SimpleCandidateCardProps> = ({ 
  candidate, 
  rank 
}) => {
  const formatScore = (score?: number) => {
    if (!score) return '0';
    return Math.round(score * 100);
  };

  const getScoreColor = (score?: number) => {
    if (!score) return 'low';
    if (score >= 0.8) return 'high';
    if (score >= 0.6) return 'medium';
    return 'low';
  };

  return (
    <div className="candidate-card">
      <div className="card-header">
        <div className="candidate-info">
          {rank && (
            <div className="rank-badge">
              #{rank}
            </div>
          )}
          <div className="candidate-details">
            <h3 className="candidate-name">{candidate.name || 'Unknown'}</h3>
            <p className="candidate-level">
              {candidate.title || 'Position not specified'}
            </p>
            <p className="candidate-experience">
              {candidate.experience || '0'} years experience
            </p>
          </div>
        </div>

        {candidate.matchScore !== undefined && (
          <div className="scores">
            <div className={`score-badge ${getScoreColor(candidate.matchScore)}`}>
              <span className="score-value">{formatScore(candidate.matchScore)}%</span>
              <span className="score-label">Match</span>
            </div>
          </div>
        )}
      </div>

      <div className="card-content">
        {candidate.skills && candidate.skills.length > 0 && (
          <div className="skills-preview">
            <div className="skill-category">
              <h4>Skills</h4>
              <div className="skills-tags">
                {candidate.skills.slice(0, 5).map((skill, index) => (
                  <span key={index} className="skill-tag technical">{skill}</span>
                ))}
                {candidate.skills.length > 5 && (
                  <span className="skill-tag more">+{candidate.skills.length - 5}</span>
                )}
              </div>
            </div>
          </div>
        )}

        {candidate.company && (
          <div className="company-info">
            <h4>Current Company</h4>
            <span className="company-tag">{candidate.company}</span>
          </div>
        )}

        {candidate.summary && (
          <div className="candidate-summary">
            <p>{candidate.summary}</p>
          </div>
        )}

        {candidate.strengths && candidate.strengths.length > 0 && (
          <div className="candidate-strengths">
            <h4>Key Strengths</h4>
            <ul>
              {candidate.strengths.slice(0, 3).map((strength, index) => (
                <li key={index}>{strength}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
};