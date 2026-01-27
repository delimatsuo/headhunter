import React, { useState } from 'react';
import Tooltip from '@mui/material/Tooltip';
import { SignalScores, SignalWeightConfig } from '../../types';
import './SignalScoreBreakdown.css';

/**
 * Human-readable display names for signal keys
 */
const SIGNAL_DISPLAY_NAMES: Record<keyof SignalScores, string> = {
  vectorSimilarity: 'Semantic Match',
  levelMatch: 'Seniority Level',
  specialtyMatch: 'Specialty Fit',
  techStackMatch: 'Tech Stack',
  functionMatch: 'Function Role',
  trajectoryFit: 'Career Trajectory',
  companyPedigree: 'Company Quality',
  skillsMatch: 'Skills Overall',
  skillsExactMatch: 'Exact Skills',
  skillsInferred: 'Inferred Skills',
  seniorityAlignment: 'Seniority Alignment',
  recencyBoost: 'Skill Recency',
  companyRelevance: 'Company Relevance'
};

/**
 * Detailed explanations for each signal metric
 */
const SIGNAL_DESCRIPTIONS: Record<keyof SignalScores, string> = {
  vectorSimilarity: 'AI-powered semantic similarity between the candidate\'s profile and the job description. Higher scores mean the overall experience and skills closely match what you\'re looking for.',
  levelMatch: 'How well the candidate\'s seniority level (Junior, Mid, Senior, Lead, etc.) matches the target role level.',
  specialtyMatch: 'How well the candidate\'s domain specialty (e.g., Backend, Frontend, Data Engineering, DevOps) aligns with the role requirements.',
  techStackMatch: 'Match between the candidate\'s technology stack and the required technologies for the role.',
  functionMatch: 'How well the candidate\'s job function (e.g., Engineering, Product, Design) matches the role type.',
  trajectoryFit: 'Career progression pattern - whether the candidate\'s career trajectory suggests readiness for this role.',
  companyPedigree: 'Quality signals from previous employers (tech companies, scale, industry reputation).',
  skillsMatch: 'Overall skills match combining exact and inferred skills.',
  skillsExactMatch: 'Direct match of explicitly listed skills with job requirements.',
  skillsInferred: 'Skills inferred from experience, projects, and related technologies.',
  seniorityAlignment: 'Alignment between candidate experience level and role expectations.',
  recencyBoost: 'How recently the candidate has used the required skills (recent usage scores higher).',
  companyRelevance: 'Relevance of previous companies to the hiring company\'s industry or domain.'
};

/**
 * Signal keys in display order (most important first)
 */
const SIGNAL_ORDER: (keyof SignalScores)[] = [
  'vectorSimilarity',
  'levelMatch',
  'specialtyMatch',
  'techStackMatch',
  'functionMatch',
  'trajectoryFit',
  'companyPedigree',
  'skillsExactMatch',
  'skillsInferred',
  'seniorityAlignment',
  'recencyBoost',
  'companyRelevance',
  'skillsMatch'
];

/**
 * Get color class based on score value
 * Green (>= 70%), Yellow (40-69%), Red (< 40%)
 */
function getScoreColorClass(score: number): string {
  const percentage = score * 100;
  if (percentage >= 70) return 'excellent';
  if (percentage >= 40) return 'good';
  return 'fair';
}

interface SignalScoreBreakdownProps {
  /** Signal scores (0-1 normalized) */
  signalScores: SignalScores;
  /** Optional weights applied for this search */
  weightsApplied?: SignalWeightConfig;
  /** Initial expanded state */
  expanded?: boolean;
  /** Callback when expand/collapse toggled */
  onToggle?: () => void;
}

/**
 * SignalScoreBreakdown Component
 *
 * Displays individual signal scores as horizontal progress bars with color coding.
 * Shows top 3 signals when collapsed, all signals when expanded.
 */
export const SignalScoreBreakdown: React.FC<SignalScoreBreakdownProps> = ({
  signalScores,
  weightsApplied,
  expanded: initialExpanded = false,
  onToggle
}) => {
  const [isExpanded, setIsExpanded] = useState(initialExpanded);

  // Filter to only signals that have values
  const availableSignals = SIGNAL_ORDER.filter(key => {
    const value = signalScores[key];
    return value !== undefined && value !== null;
  });

  // Sort signals by score (highest first) for collapsed view
  const sortedSignals = [...availableSignals].sort((a, b) => {
    const scoreA = signalScores[a] ?? 0;
    const scoreB = signalScores[b] ?? 0;
    return scoreB - scoreA;
  });

  // Show top 3 when collapsed, all when expanded
  const displayedSignals = isExpanded ? availableSignals : sortedSignals.slice(0, 3);

  const handleToggle = () => {
    setIsExpanded(!isExpanded);
    if (onToggle) {
      onToggle();
    }
  };

  if (availableSignals.length === 0) {
    return null;
  }

  return (
    <div className="signal-breakdown">
      <div className="signal-breakdown-header">
        <span className="signal-breakdown-title">Score Breakdown</span>
        <button
          className="signal-breakdown-toggle"
          onClick={handleToggle}
          aria-expanded={isExpanded}
        >
          {isExpanded ? 'Show less' : `Show all (${availableSignals.length})`}
        </button>
      </div>

      <div className={`signal-list ${isExpanded ? 'expanded' : 'collapsed'}`}>
        {displayedSignals.map(signalKey => {
          const score = signalScores[signalKey] ?? 0;
          const percentage = Math.round(score * 100);
          const colorClass = getScoreColorClass(score);
          const displayName = SIGNAL_DISPLAY_NAMES[signalKey];
          const weight = weightsApplied?.[signalKey as keyof SignalWeightConfig];

          const description = SIGNAL_DESCRIPTIONS[signalKey];
          const tooltipContent = (
            <div style={{ maxWidth: 280, padding: '4px 0' }}>
              <div style={{ fontWeight: 600, marginBottom: 4 }}>{displayName}: {percentage}%</div>
              <div style={{ fontSize: '12px', opacity: 0.9, lineHeight: 1.4 }}>{description}</div>
              {weight !== undefined && (
                <div style={{ fontSize: '11px', marginTop: 4, opacity: 0.7 }}>
                  Weight in scoring: {(weight * 100).toFixed(0)}%
                </div>
              )}
            </div>
          );

          return (
            <Tooltip key={signalKey} title={tooltipContent} placement="top" arrow enterDelay={300}>
              <div className="signal-row">
                <span className="signal-label">{displayName}</span>
                <div className="signal-bar-container">
                  <div
                    className={`signal-bar ${colorClass}`}
                    style={{ width: `${percentage}%` }}
                  />
                </div>
                <span className={`signal-value ${colorClass}`}>
                  {percentage}%
                </span>
              </div>
            </Tooltip>
          );
        })}
      </div>
    </div>
  );
};

export default SignalScoreBreakdown;
