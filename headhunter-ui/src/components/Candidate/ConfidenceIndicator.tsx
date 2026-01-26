import React from 'react';
import { Tooltip } from '@mui/material';

interface ConfidenceIndicatorProps {
  confidence: number;
  showWarning?: boolean;
  size?: 'sm' | 'md';
}

/**
 * Displays confidence level as a color-coded percentage badge.
 * For ML predictions (Phase 13) - shows visual warning for low confidence.
 *
 * Color scheme:
 * - Green (>=80%): High confidence
 * - Yellow (60-79%): Medium confidence
 * - Red (<60%): Low confidence (warning state)
 */
export const ConfidenceIndicator: React.FC<ConfidenceIndicatorProps> = ({
  confidence,
  showWarning = false,
  size = 'md',
}) => {
  const percentage = Math.round(confidence * 100);

  // Determine color based on confidence threshold
  const getColorClasses = () => {
    if (percentage >= 80) {
      return 'bg-green-100 text-green-800';
    }
    if (percentage >= 60) {
      return 'bg-yellow-100 text-yellow-800';
    }
    return 'bg-red-100 text-red-800';
  };

  const sizeClasses = size === 'sm' ? 'text-xs px-2 py-1' : 'text-sm px-2.5 py-1.5';

  const badge = (
    <div
      className={`inline-flex items-center gap-1 rounded-full font-medium ${getColorClasses()} ${sizeClasses}`}
    >
      {showWarning && percentage < 60 && (
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="currentColor"
          className="w-4 h-4"
        >
          <path
            fillRule="evenodd"
            d="M9.401 3.003c1.155-2 4.043-2 5.197 0l7.355 12.748c1.154 2-.29 4.5-2.599 4.5H4.645c-2.309 0-3.752-2.5-2.598-4.5L9.4 3.003zM12 8.25a.75.75 0 01.75.75v3.75a.75.75 0 01-1.5 0V9a.75.75 0 01.75-.75zm0 8.25a.75.75 0 100-1.5.75.75 0 000 1.5z"
            clipRule="evenodd"
          />
        </svg>
      )}
      <span>{percentage}%</span>
    </div>
  );

  // Add tooltip for low confidence warning
  if (showWarning && percentage < 60) {
    return (
      <Tooltip
        title="Low confidence prediction - limited data or uncertain trajectory"
        arrow
        placement="top"
      >
        {badge}
      </Tooltip>
    );
  }

  return badge;
};
