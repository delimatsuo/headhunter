import React, { useState } from 'react';
import { Tooltip } from '@mui/material';
import { AnonymizedCandidate, SignalScores } from '../../types';
import { SignalScoreBreakdown } from '../Match/SignalScoreBreakdown';
import { SkillChip } from '../Match/SkillChip';
import './AnonymizedCandidateCard.css';

interface AnonymizedCandidateCardProps {
  candidate: AnonymizedCandidate;
  rank?: number;
  onClick?: () => void;
  searchSkills?: string[];
}

/**
 * AnonymizedCandidateCard Component (BIAS-01)
 *
 * Displays candidate information with personally identifying information removed
 * to enable blind hiring and reduce unconscious bias.
 *
 * Hidden information:
 * - Name and photo
 * - Company names (current and previous)
 * - School/university names
 * - Location details
 *
 * Shown information:
 * - Skills and expertise
 * - Years of experience
 * - Industry experience
 * - Match reasons (anonymized)
 * - Signal scores (excluding company pedigree)
 * - ML trajectory predictions
 */
export const AnonymizedCandidateCard: React.FC<AnonymizedCandidateCardProps> = ({
  candidate,
  rank,
  onClick,
  searchSkills = [],
}) => {
  const [expanded, setExpanded] = useState(false);
  const [signalBreakdownExpanded, setSignalBreakdownExpanded] = useState(false);

  const handleCardClick = () => {
    if (onClick) {
      onClick();
    } else {
      setExpanded(!expanded);
    }
  };

  const getScoreColor = (score: number) => {
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

  const getExperienceLabel = (years?: number) => {
    if (years === undefined) return 'Experience not specified';
    if (years < 3) return 'Early career (0-3 years)';
    if (years < 7) return 'Mid-level (3-7 years)';
    if (years < 15) return 'Senior (7-15 years)';
    return 'Executive (15+ years)';
  };

  // Generate a short anonymized identifier for display
  const getAnonymizedId = () => {
    if (!candidate.candidateId) return 'Unknown';
    // Use last 6 characters of the ID for a short reference
    return candidate.candidateId.slice(-6).toUpperCase();
  };

  return (
    <div className={`anonymized-candidate-card ${expanded ? 'expanded' : ''}`}>
      {/* Blind Hiring Badge */}
      <div className="blind-hiring-badge">
        <span className="badge-icon">&#128100;</span>
        <span className="badge-text">Anonymized View</span>
      </div>

      <div className="card-header" onClick={handleCardClick}>
        <div className="candidate-info">
          {rank && (
            <div className="rank-badge">
              #{rank}
            </div>
          )}
          <div className="candidate-details">
            <h3 className="candidate-identifier">Candidate #{getAnonymizedId()}</h3>
            <p className="candidate-experience">
              {getExperienceLabel(candidate.yearsExperience)}
              {candidate.yearsExperience !== undefined && ` (${candidate.yearsExperience} years)`}
            </p>
          </div>
        </div>

        <div className="scores">
          <Tooltip title="Multi-signal match score based on qualifications" arrow placement="top">
            <div className={`score-badge match ${getScoreColor(candidate.score)}`}>
              <span className="score-value">{formatScore(candidate.score)}%</span>
              <span className="score-label">Match</span>
            </div>
          </Tooltip>
        </div>
      </div>

      <div className="card-content">
        {/* Skills Section - Primary Focus */}
        <div className="skills-section">
          <h4>Skills &amp; Expertise</h4>
          <div className="skill-cloud">
            {candidate.skills?.slice(0, 15).map((skill, idx) => (
              <SkillChip
                key={`${skill.name}-${idx}`}
                skill={skill.name}
                type="explicit"
                confidence={skill.weight}
                isMatched={searchSkills.some(s =>
                  s.toLowerCase() === skill.name.toLowerCase()
                )}
              />
            ))}
            {(candidate.skills?.length || 0) > 15 && (
              <span className="more-skills">+{(candidate.skills?.length || 0) - 15} more</span>
            )}
          </div>
        </div>

        {/* Industries */}
        {candidate.industries && candidate.industries.length > 0 && (
          <div className="industries-section">
            <h4>Industry Experience</h4>
            <div className="industry-tags">
              {candidate.industries.map((industry, idx) => (
                <span key={idx} className="industry-tag">{industry}</span>
              ))}
            </div>
          </div>
        )}

        {/* Match Reasons (anonymized) */}
        {candidate.matchReasons.length > 0 && (
          <div className="match-reasons-section">
            <h4>Why This Candidate Matches</h4>
            <ul className="match-reasons-list">
              {candidate.matchReasons.map((reason, idx) => (
                <li key={idx}>{reason}</li>
              ))}
            </ul>
          </div>
        )}

        {/* Signal Score Breakdown - Expandable */}
        {candidate.signalScores && (
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
              <div className="anonymized-breakdown">
                <SignalScoreBreakdown
                  signalScores={candidate.signalScores as SignalScores}
                  weightsApplied={candidate.weightsApplied as any}
                />
                <p className="breakdown-note">
                  Note: Company pedigree signals excluded in anonymized view
                </p>
              </div>
            )}
          </div>
        )}

        {/* ML Trajectory Prediction - if available */}
        {expanded && candidate.mlTrajectory && (
          <div className="trajectory-section">
            <h4>Career Trajectory Prediction</h4>
            <div className="trajectory-info">
              <p><strong>Predicted Next Role:</strong> {candidate.mlTrajectory.nextRole}</p>
              <p><strong>Confidence:</strong> {Math.round(candidate.mlTrajectory.nextRoleConfidence * 100)}%</p>
              <p><strong>Estimated Tenure:</strong> {candidate.mlTrajectory.tenureMonths.min}-{candidate.mlTrajectory.tenureMonths.max} months</p>
              <p><strong>Hireability Score:</strong> {Math.round(candidate.mlTrajectory.hireability * 100)}/100</p>
              {candidate.mlTrajectory.lowConfidence && (
                <p className="low-confidence-warning">
                  Low confidence: {candidate.mlTrajectory.uncertaintyReason}
                </p>
              )}
            </div>
          </div>
        )}
      </div>

      <div className="card-footer" onClick={() => setExpanded(!expanded)}>
        <button className="expand-button">
          {expanded ? 'Show Less' : 'Show More Details'}
        </button>
      </div>

      {/* Privacy Notice */}
      <div className="privacy-notice">
        <p>
          Identifying information hidden to reduce unconscious bias.
          Reveal candidate identity after shortlisting decision.
        </p>
      </div>
    </div>
  );
};
