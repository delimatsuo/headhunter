import React from 'react';
import { SearchResponse, CandidateMatch } from '../../types';
import { SkillAwareCandidateCard } from '../Candidate/SkillAwareCandidateCard';

interface SearchResultsProps {
  results: SearchResponse | null;
  loading: boolean;
  error: string | null;
  onFindSimilar?: (candidateId: string) => void;
}

export const SearchResults: React.FC<SearchResultsProps> = ({
  results,
  loading,
  error,
  onFindSimilar
}) => {
  if (loading) {
    return (
      <div className="search-results">
        <div className="loading-container">
          <div className="loading-spinner"></div>
          <p>Analyzing candidates...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="search-results">
        <div className="error-container">
          <div className="error-icon">⚠️</div>
          <h3>Search Failed</h3>
          <p>{error}</p>
        </div>
      </div>
    );
  }

  if (!results) {
    return null;
  }

  const { matches = [], insights = {
    total_candidates: 0,
    avg_match_score: 0,
    top_skills_matched: [],
    common_gaps: [],
    market_analysis: '',
    recommendations: []
  } } = results || {};

  return (
    <div className="search-results">
      <div className="results-header">
        <div className="results-summary">
          <h2>Search Results</h2>
          <p>Found {matches?.length || 0} matching candidates in {results?.query_time_ms || 0}ms</p>
        </div>

        <div className="results-stats">
          <div className="stat">
            <span className="stat-label">Total Candidates</span>
            <span className="stat-value">{insights?.total_candidates || 0}</span>
          </div>
          <div className="stat">
            <span className="stat-label">Avg Match Score</span>
            <span className="stat-value">{Math.round((insights?.avg_match_score || 0) > 1 ? (insights?.avg_match_score || 0) : (insights?.avg_match_score || 0) * 100)}%</span>
          </div>
        </div>
      </div>

      {/* Market Insights Hidden for MVP
      {insights && (
        <div className="search-insights">
          <h3>Market Insights</h3>
          ...
        </div>
      )}
      */}

      <div className="candidates-list">
        <h3>Candidate Matches ({matches?.length || 0})</h3>
        {(!matches || matches.length === 0) ? (
          <div className="no-results">
            <div className="no-results-icon">🔍</div>
            <h4>No matches found</h4>
            <p>Try adjusting your search criteria or requirements</p>
          </div>
        ) : (
          <div className="candidates-grid">
            {matches.map((match, index) => (
              <SkillAwareCandidateCard
                key={match.candidate?.candidate_id || index}
                candidate={match.candidate}
                matchScore={match.score}
                similarity={match.similarity}
                // rationale is handled inside candidate object in new component, but we can pass it if needed
                // The new component reads candidate.rationale or candidate.matchReasons
                rank={index + 1}
                searchSkills={[]} // TODO: Pass actual search skills from parent
                onFindSimilar={onFindSimilar ? () => onFindSimilar(match.candidate?.candidate_id || '') : undefined}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};