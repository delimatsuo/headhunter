import React from 'react';
import { MLTrajectoryPrediction } from '../../types';
import { ConfidenceIndicator } from './ConfidenceIndicator';

interface TrajectoryPredictionProps {
  prediction: MLTrajectoryPrediction | null | undefined;
}

/**
 * Displays ML trajectory predictions for candidate career path.
 * Shows predicted next role, tenure estimate, and hireability score.
 * Phase 13 - ML Trajectory Prediction
 */
export const TrajectoryPrediction: React.FC<TrajectoryPredictionProps> = ({
  prediction,
}) => {
  // Graceful handling - return null if no prediction available
  if (!prediction) {
    return null;
  }

  // Convert hireability score (0-1) to label
  const getHireabilityLabel = (score: number): string => {
    if (score >= 0.7) {
      return 'High likelihood to join';
    }
    if (score >= 0.4) {
      return 'Moderate likelihood';
    }
    return 'Lower likelihood';
  };

  const getHireabilityColor = (score: number): string => {
    if (score >= 0.7) {
      return 'text-green-700';
    }
    if (score >= 0.4) {
      return 'text-yellow-700';
    }
    return 'text-orange-700';
  };

  const hireabilityLabel = getHireabilityLabel(prediction.hireability);
  const hireabilityColor = getHireabilityColor(prediction.hireability);

  return (
    <div className="space-y-3">
      {/* Next Role Section */}
      <div className="flex items-start gap-2">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="currentColor"
          className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5"
        >
          <path
            fillRule="evenodd"
            d="M12.97 3.97a.75.75 0 011.06 0l7.5 7.5a.75.75 0 010 1.06l-7.5 7.5a.75.75 0 11-1.06-1.06l6.22-6.22H3a.75.75 0 010-1.5h16.19l-6.22-6.22a.75.75 0 010-1.06z"
            clipRule="evenodd"
          />
        </svg>
        <div className="flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm text-gray-700">
              <span className="font-medium">Predicted Next:</span>{' '}
              {prediction.nextRole}
            </span>
            <ConfidenceIndicator
              confidence={prediction.nextRoleConfidence}
              showWarning={prediction.lowConfidence}
              size="sm"
            />
          </div>
        </div>
      </div>

      {/* Tenure Section */}
      <div className="flex items-start gap-2">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="currentColor"
          className="w-5 h-5 text-purple-600 flex-shrink-0 mt-0.5"
        >
          <path
            fillRule="evenodd"
            d="M12 2.25c-5.385 0-9.75 4.365-9.75 9.75s4.365 9.75 9.75 9.75 9.75-4.365 9.75-9.75S17.385 2.25 12 2.25zM12.75 6a.75.75 0 00-1.5 0v6c0 .414.336.75.75.75h4.5a.75.75 0 000-1.5h-3.75V6z"
            clipRule="evenodd"
          />
        </svg>
        <div className="text-sm text-gray-700">
          <span className="font-medium">Likely to stay:</span>{' '}
          {prediction.tenureMonths.min}-{prediction.tenureMonths.max} months
        </div>
      </div>

      {/* Hireability Section */}
      <div className="flex items-start gap-2">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="currentColor"
          className="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5"
        >
          <path
            fillRule="evenodd"
            d="M10.788 3.21c.448-1.077 1.976-1.077 2.424 0l2.082 5.007 5.404.433c1.164.093 1.636 1.545.749 2.305l-4.117 3.527 1.257 5.273c.271 1.136-.964 2.033-1.96 1.425L12 18.354 7.373 21.18c-.996.608-2.231-.29-1.96-1.425l1.257-5.273-4.117-3.527c-.887-.76-.415-2.212.749-2.305l5.404-.433 2.082-5.006z"
            clipRule="evenodd"
          />
        </svg>
        <div className="text-sm">
          <span className="font-medium text-gray-700">Hireability:</span>{' '}
          <span className={hireabilityColor}>{hireabilityLabel}</span>
        </div>
      </div>

      {/* Uncertainty Warning Banner */}
      {prediction.lowConfidence && prediction.uncertaintyReason && (
        <div className="mt-2 p-2 bg-yellow-50 border border-yellow-200 rounded-md">
          <div className="flex items-start gap-2">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="currentColor"
              className="w-5 h-5 text-yellow-700 flex-shrink-0"
            >
              <path
                fillRule="evenodd"
                d="M9.401 3.003c1.155-2 4.043-2 5.197 0l7.355 12.748c1.154 2-.29 4.5-2.599 4.5H4.645c-2.309 0-3.752-2.5-2.598-4.5L9.4 3.003zM12 8.25a.75.75 0 01.75.75v3.75a.75.75 0 01-1.5 0V9a.75.75 0 01.75-.75zm0 8.25a.75.75 0 100-1.5.75.75 0 000 1.5z"
                clipRule="evenodd"
              />
            </svg>
            <div className="text-xs text-yellow-800">
              <span className="font-medium">Prediction Uncertainty:</span>{' '}
              {prediction.uncertaintyReason}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
