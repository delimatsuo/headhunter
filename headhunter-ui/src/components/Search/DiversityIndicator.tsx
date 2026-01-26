import React, { useState } from 'react';
import { Tooltip } from '@mui/material';
import { SlateDiversityAnalysis, DiversityWarning } from '../../types';
import './DiversityIndicator.css';

interface DiversityIndicatorProps {
  analysis: SlateDiversityAnalysis;
}

/**
 * DiversityIndicator Component (BIAS-05)
 *
 * Displays diversity analysis for a candidate slate, showing:
 * - Diversity score (0-100)
 * - Warnings for concentration issues (>70% in one group)
 * - Distribution breakdown by dimension
 *
 * Helps recruiters identify when a candidate pool is too homogeneous
 * and may benefit from broader sourcing strategies.
 */
export const DiversityIndicator: React.FC<DiversityIndicatorProps> = ({
  analysis,
}) => {
  const [expanded, setExpanded] = useState(false);

  // If slate is diverse, show positive indicator
  if (!analysis.hasConcentrationIssue && analysis.diversityScore >= 60) {
    return (
      <div className="diversity-indicator diverse">
        <span className="diversity-icon">&#9989;</span>
        <span className="diversity-text">Diverse slate (score: {analysis.diversityScore}/100)</span>
      </div>
    );
  }

  const getWarningColor = (level: DiversityWarning['level']) => {
    switch (level) {
      case 'alert': return 'alert';
      case 'warning': return 'warning';
      default: return 'info';
    }
  };

  // Sort warnings by concentration percentage (most concentrated first)
  const sortedWarnings = [...analysis.warnings].sort(
    (a, b) => b.concentrationPct - a.concentrationPct
  );
  const topWarning = sortedWarnings[0];

  const formatDimensionName = (dimension: string): string => {
    switch (dimension) {
      case 'companyTier': return 'Company Background';
      case 'experienceBand': return 'Experience Level';
      case 'specialty': return 'Technical Specialty';
      default: return dimension;
    }
  };

  return (
    <div className={`diversity-indicator ${getWarningColor(topWarning?.level || 'info')}`}>
      <div className="indicator-header" onClick={() => setExpanded(!expanded)}>
        <span className="diversity-icon">
          {topWarning?.level === 'alert' ? '\u{1F6A8}' : topWarning?.level === 'warning' ? '\u26A0\uFE0F' : '\u2139\uFE0F'}
        </span>
        <span className="diversity-text">{topWarning?.message || 'Diversity analysis available'}</span>
        <span className={`expand-chevron ${expanded ? 'expanded' : ''}`}>&#9660;</span>
      </div>

      {expanded && (
        <div className="indicator-details">
          <div className="diversity-score">
            <span className="score-label">Diversity Score:</span>
            <span className={`score-value ${analysis.diversityScore < 50 ? 'low' : ''}`}>
              {analysis.diversityScore}/100
            </span>
          </div>

          {sortedWarnings.map((warning, idx) => (
            <div key={idx} className={`warning-item ${warning.level}`}>
              <p className="warning-message">{warning.message}</p>
              <p className="warning-suggestion">
                <strong>Suggestion:</strong> {warning.suggestion}
              </p>
            </div>
          ))}

          <div className="dimension-breakdown">
            <h4>Distribution by Dimension</h4>
            {analysis.dimensions.map((dim, idx) => (
              <div key={idx} className="dimension-item">
                <span className="dimension-name">{formatDimensionName(dim.dimension)}</span>
                <div className="distribution-bar">
                  {Object.entries(dim.distribution).map(([group, count]) => {
                    const pct = (count / analysis.totalCandidates) * 100;
                    return (
                      <Tooltip
                        key={group}
                        title={`${group}: ${count} candidates (${Math.round(pct)}%)`}
                        arrow
                      >
                        <div
                          className={`bar-segment ${group === dim.dominantGroup ? 'dominant' : ''}`}
                          style={{ width: `${pct}%` }}
                        />
                      </Tooltip>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
