import React from 'react';
import './BiasMetricsDashboard.css';

interface ImpactRatioAlertProps {
  dimension: string;
  affectedGroups: string[];
  impactRatios: Record<string, number>;
  warnings: string[];
}

/**
 * ImpactRatioAlert component displays adverse impact warnings
 * when any group's selection rate falls below 80% of the highest group.
 * Per EEOC four-fifths rule (29 CFR 1607.4).
 */
export const ImpactRatioAlert: React.FC<ImpactRatioAlertProps> = ({
  dimension,
  affectedGroups,
  impactRatios,
  warnings,
}) => {
  if (affectedGroups.length === 0) {
    return null;
  }

  const formatDimension = (dim: string): string => {
    return dim
      .replace(/_/g, ' ')
      .replace(/\b\w/g, (c) => c.toUpperCase());
  };

  const formatPercent = (ratio: number): string => {
    return (ratio * 100).toFixed(1) + '%';
  };

  return (
    <div className="impact-ratio-alert">
      <div className="alert-header">
        <span className="alert-icon" role="img" aria-label="warning">
          !
        </span>
        <h4>Potential Adverse Impact Detected</h4>
      </div>

      <div className="alert-content">
        <p className="alert-dimension">
          <strong>Dimension:</strong> {formatDimension(dimension)}
        </p>

        <div className="affected-groups">
          <p>
            <strong>Affected Groups (below 80% threshold):</strong>
          </p>
          <ul>
            {affectedGroups.map((group) => (
              <li key={group}>
                <span className="group-name">{group}</span>
                <span className="impact-ratio">
                  Impact Ratio: {formatPercent(impactRatios[group] || 0)}
                </span>
              </li>
            ))}
          </ul>
        </div>

        {warnings.length > 0 && (
          <div className="alert-warnings">
            {warnings.map((warning, idx) => (
              <p key={idx} className="warning-text">
                {warning}
              </p>
            ))}
          </div>
        )}

        <div className="alert-action">
          <p>
            <strong>Recommended Action:</strong> Review selection criteria and
            consider whether current practices may disproportionately exclude
            qualified candidates from affected groups.
          </p>
        </div>
      </div>
    </div>
  );
};

export default ImpactRatioAlert;
