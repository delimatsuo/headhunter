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
    high: 'Inferred',
    medium: 'Likely',
    low: 'Possible'
  };

  // Generate tooltip text based on skill type and confidence
  const getTooltipText = (): string => {
    if (type === 'explicit') {
      return `Stated Skill: "${skill}" is explicitly mentioned in the candidate's profile`;
    }

    // Inferred skill tooltips
    const confidencePercent = Math.round(confidence * 100);
    const baseText = evidence || `AI-inferred from experience and context`;

    if (confidenceLevel === 'high') {
      return `AI Inferred (${confidencePercent}% confident): ${baseText}`;
    } else if (confidenceLevel === 'medium') {
      return `Likely Skill (${confidencePercent}% confident): ${baseText}`;
    } else {
      return `Possible Skill (${confidencePercent}% confident): ${baseText}`;
    }
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

  // Always wrap in tooltip for explanation
  return (
    <Tooltip title={getTooltipText()} arrow placement="top">
      {chipContent}
    </Tooltip>
  );
};
