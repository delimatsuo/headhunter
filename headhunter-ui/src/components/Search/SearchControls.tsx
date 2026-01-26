import React from 'react';
import { Tooltip, Switch, FormControlLabel } from '@mui/material';
import './SearchControls.css';

interface SearchControlsProps {
  anonymizedView: boolean;
  onToggleAnonymized: (enabled: boolean) => void;
  disabled?: boolean;
}

/**
 * SearchControls Component (BIAS-01)
 *
 * Provides controls for the search results view, including:
 * - Anonymization toggle for blind hiring workflow
 *
 * The anonymization toggle enables recruiters to view candidates
 * without personally identifying information to reduce unconscious bias.
 */
export const SearchControls: React.FC<SearchControlsProps> = ({
  anonymizedView,
  onToggleAnonymized,
  disabled = false,
}) => {
  return (
    <div className="search-controls">
      <div className="control-group anonymized-toggle-group">
        <Tooltip
          title="Enable blind hiring mode to reduce unconscious bias. Hides candidate names, photos, company names, and school names."
          arrow
          placement="bottom"
        >
          <FormControlLabel
            control={
              <Switch
                checked={anonymizedView}
                onChange={(e) => onToggleAnonymized(e.target.checked)}
                disabled={disabled}
                color="primary"
              />
            }
            label={
              <span className="toggle-label">
                <span className="toggle-icon">&#128100;</span>
                <span className="toggle-text">Anonymized View</span>
                {anonymizedView && <span className="toggle-badge">Active</span>}
              </span>
            }
          />
        </Tooltip>
        {anonymizedView && (
          <p className="anonymized-description">
            Blind hiring mode active. Candidate identities hidden to reduce bias.
          </p>
        )}
      </div>
    </div>
  );
};
