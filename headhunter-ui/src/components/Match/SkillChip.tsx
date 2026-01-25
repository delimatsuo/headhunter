import React from 'react';
import { Tooltip } from '@mui/material';
import './SkillChip.css';

export interface SkillChipProps {
  skill: string;
  type: 'explicit' | 'inferred';
  confidence?: number;        // 0-1 for inferred skills
  evidence?: string;          // Reasoning for inferred skill
  isMatched?: boolean;        // Highlight if matched search requirement
}

export const SkillChip: React.FC<SkillChipProps> = ({
  skill,
  type,
  confidence = 1,
  evidence,
  isMatched = false,
}) => {
  // Confidence thresholds (from research: TRNS-04)
  // High: >= 0.8, Medium: 0.5-0.79, Low: < 0.5
  const getConfidenceLevel = (conf: number): 'high' | 'medium' | 'low' => {
    if (conf >= 0.8) return 'high';
    if (conf >= 0.5) return 'medium';
    return 'low';
  };

  const confidenceLevel = type === 'inferred' ? getConfidenceLevel(confidence) : null;
  const confidenceLabels = {
    high: 'High',
    medium: 'Likely',
    low: 'Possible'
  };

  const chipContent = (
    <span className={`skill-chip ${type} ${confidenceLevel || ''} ${isMatched ? 'matched' : ''}`}>
      {skill}
      {type === 'inferred' && confidenceLevel && (
        <span className={`confidence-badge ${confidenceLevel}`}>
          {confidenceLabels[confidenceLevel]}
        </span>
      )}
    </span>
  );

  // Wrap in tooltip if there's evidence for inferred skill
  if (type === 'inferred' && evidence) {
    return (
      <Tooltip title={evidence} arrow placement="top">
        {chipContent}
      </Tooltip>
    );
  }

  return chipContent;
};
