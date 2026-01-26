import React, { useState, useEffect, useCallback } from 'react';
import { api, BiasMetricsResponse, DimensionMetrics } from '../../services/api';
import { SelectionRateChart } from './SelectionRateChart';
import { ImpactRatioAlert } from './ImpactRatioAlert';
import './BiasMetricsDashboard.css';

/**
 * BiasMetricsDashboard displays selection rate analysis for EEOC compliance monitoring.
 * Implements BIAS-03 (selection rate dashboard) and BIAS-04 (impact ratio alerts).
 *
 * Features:
 * - Selection rates by dimension (company tier, experience band, specialty)
 * - Adverse impact alerts when any group falls below 80% of highest group
 * - Configurable time period (7, 30, 90 days)
 * - Statistical significance warnings for small samples
 */
export const BiasMetricsDashboard: React.FC = () => {
  const [metrics, setMetrics] = useState<BiasMetricsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedDays, setSelectedDays] = useState(30);

  const loadMetrics = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const data = await api.getBiasMetrics({ days: selectedDays, dimension: 'all' });
      setMetrics(data);
    } catch (err) {
      setError(
        'Failed to load bias metrics. Make sure the bias metrics worker has been run.'
      );
      console.error('[BiasMetricsDashboard] Load error:', err);
    } finally {
      setLoading(false);
    }
  }, [selectedDays]);

  useEffect(() => {
    loadMetrics();
  }, [loadMetrics]);

  const formatDate = (dateStr: string | null): string => {
    if (!dateStr) return 'N/A';
    try {
      return new Date(dateStr).toLocaleString();
    } catch {
      return dateStr;
    }
  };

  // Loading state
  if (loading) {
    return (
      <div className="bias-metrics-dashboard loading">
        <div className="loading-spinner" />
        <p>Loading bias metrics...</p>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="bias-metrics-dashboard error">
        <p className="error-message">{error}</p>
        <button onClick={loadMetrics} className="retry-button">
          Retry
        </button>
      </div>
    );
  }

  // Empty state - no metrics computed yet
  if (!metrics || !metrics.computed_at) {
    return (
      <div className="bias-metrics-dashboard empty">
        <h3>No Bias Metrics Available</h3>
        <p>
          Bias metrics have not been computed yet. Run the bias metrics worker
          to generate selection rate data.
        </p>
        <pre className="code-snippet">
          python scripts/bias_metrics_worker.py --days 30 --all-dimensions --save-to-db
        </pre>
        <button onClick={loadMetrics} className="retry-button">
          Refresh
        </button>
      </div>
    );
  }

  const dimensions = Object.values(metrics.dimensions) as DimensionMetrics[];
  const dimensionsWithAdverseImpact = dimensions.filter(
    (d) => d.adverse_impact_detected
  );

  return (
    <div className="bias-metrics-dashboard">
      {/* Header */}
      <div className="dashboard-header">
        <h2>Bias Metrics Dashboard</h2>
        <p className="subtitle">
          Selection rate analysis for EEOC compliance monitoring
        </p>

        <div className="period-selector">
          <label htmlFor="period-select">Analysis Period:</label>
          <select
            id="period-select"
            value={selectedDays}
            onChange={(e) => setSelectedDays(Number(e.target.value))}
          >
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
          <button onClick={loadMetrics} className="refresh-button" title="Refresh data">
            Refresh
          </button>
        </div>

        <p className="computed-at">
          Last computed: {formatDate(metrics.computed_at)}
        </p>
      </div>

      {/* Adverse Impact Alerts */}
      {metrics.any_adverse_impact && dimensionsWithAdverseImpact.length > 0 && (
        <div className="alerts-section">
          <h3>Adverse Impact Alerts</h3>
          {dimensionsWithAdverseImpact.map((dim) => (
            <ImpactRatioAlert
              key={dim.dimension}
              dimension={dim.dimension}
              affectedGroups={dim.adverse_impact_groups}
              impactRatios={dim.impact_ratios}
              warnings={dim.warnings}
            />
          ))}
        </div>
      )}

      {/* All Warnings Summary */}
      {metrics.all_warnings.length > 0 && (
        <div className="warnings-summary">
          <h3>Summary Warnings</h3>
          <ul>
            {metrics.all_warnings.map((warning, idx) => (
              <li key={idx}>{warning}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Status Badge */}
      {!metrics.any_adverse_impact && dimensions.length > 0 && (
        <div className="status-badge success">
          <span className="status-icon">OK</span>
          <span>All groups within acceptable impact ratio thresholds</span>
        </div>
      )}

      {/* Charts Section */}
      <div className="charts-section">
        <h3>Selection Rates by Dimension</h3>
        <p className="section-description">
          The four-fifths rule (80% threshold) is shown for adverse impact detection.
          Groups with selection rates below 80% of the highest group are flagged.
        </p>

        {dimensions.length === 0 ? (
          <p className="no-data">No dimension data available for this period.</p>
        ) : (
          <div className="charts-grid">
            {dimensions.map((dim) => (
              <SelectionRateChart
                key={dim.dimension}
                dimension={dim.dimension}
                selectionRates={dim.selection_rates}
                impactRatios={dim.impact_ratios}
                sampleSizes={dim.sample_sizes}
                overallRate={dim.overall_rate}
              />
            ))}
          </div>
        )}
      </div>

      {/* Methodology Note */}
      <div className="methodology-note">
        <h4>Methodology</h4>
        <p>
          Selection rates are calculated using Fairlearn's MetricFrame. The impact
          ratio compares each group's selection rate to the highest-selected group.
          A ratio below 0.8 (80%) indicates potential adverse impact per the
          four-fifths rule (29 CFR 1607.4).
        </p>
        <p>
          <strong>Important:</strong> This analysis uses inferred dimensions
          (company tier, experience band, specialty) as demographic proxies.
          It does not use actual protected characteristic data.
        </p>
      </div>
    </div>
  );
};

export default BiasMetricsDashboard;
