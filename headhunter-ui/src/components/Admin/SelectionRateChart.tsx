import React from 'react';
import './BiasMetricsDashboard.css';

interface SelectionRateChartProps {
  dimension: string;
  selectionRates: Record<string, number>;
  impactRatios: Record<string, number>;
  sampleSizes: Record<string, number>;
  overallRate: number;
}

/**
 * SelectionRateChart displays selection rates by group as horizontal bars.
 * Shows 80% threshold line for four-fifths rule compliance checking.
 */
export const SelectionRateChart: React.FC<SelectionRateChartProps> = ({
  dimension,
  selectionRates,
  impactRatios,
  sampleSizes,
  overallRate,
}) => {
  const formatDimension = (dim: string): string => {
    return dim
      .replace(/_/g, ' ')
      .replace(/\b\w/g, (c) => c.toUpperCase());
  };

  const formatPercent = (value: number): string => {
    return (value * 100).toFixed(1) + '%';
  };

  // Sort by selection rate descending
  const sortedGroups = Object.entries(selectionRates)
    .sort(([, a], [, b]) => b - a);

  // Find max rate for scaling bars
  const maxRate = Math.max(...Object.values(selectionRates), overallRate);

  // Check for small samples
  const hasSmallSamples = Object.values(sampleSizes).some((n) => n < 20);

  return (
    <div className="selection-rate-chart">
      <h4>{formatDimension(dimension)}</h4>

      <div className="chart-container">
        {/* Reference line at 80% of max */}
        <div
          className="threshold-line"
          style={{ left: `${(maxRate * 0.8 / maxRate) * 100}%` }}
          title="80% Threshold (Four-Fifths Rule)"
        >
          <span className="threshold-label">80%</span>
        </div>

        {/* Overall rate reference */}
        <div
          className="overall-line"
          style={{ left: `${(overallRate / maxRate) * 100}%` }}
          title={`Overall Rate: ${formatPercent(overallRate)}`}
        />

        {/* Bars for each group */}
        <div className="bars-container">
          {sortedGroups.map(([group, rate]) => {
            const isBelowThreshold = impactRatios[group] < 0.8;
            const barWidth = (rate / maxRate) * 100;

            return (
              <div key={group} className="bar-row">
                <div className="bar-label" title={group}>
                  {group}
                </div>
                <div className="bar-track">
                  <div
                    className={`bar-fill ${isBelowThreshold ? 'below-threshold' : 'above-threshold'}`}
                    style={{ width: `${barWidth}%` }}
                  >
                    <span className="bar-value">{formatPercent(rate)}</span>
                  </div>
                </div>
                <div className="bar-sample" title="Sample size">
                  n={sampleSizes[group] || 0}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="chart-legend">
        <div className="legend-item">
          <span className="legend-color above-threshold" />
          <span>Above 80% threshold</span>
        </div>
        <div className="legend-item">
          <span className="legend-color below-threshold" />
          <span>Below 80% threshold</span>
        </div>
      </div>

      {hasSmallSamples && (
        <div className="small-sample-warning">
          Note: Some groups have fewer than 20 candidates. Results may not be
          statistically significant.
        </div>
      )}
    </div>
  );
};

export default SelectionRateChart;
