import React from 'react';
import { SearchResponse, CandidateMatch } from '../../types';
import { CandidateCard } from '../Candidate/CandidateCard';

interface SearchResultsProps {
  results: SearchResponse | null;
  loading: boolean;
  error: string | null;
}

export const SearchResults: React.FC<SearchResultsProps> = ({ 
  results, 
  loading, 
  error 
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

  const { matches, insights } = results;

  return (
    <div className="search-results">
      <div className="results-header">
        <div className="results-summary">
          <h2>Search Results</h2>
          <p>Found {matches.length} matching candidates in {results.query_time_ms}ms</p>
        </div>

        <div className="results-stats">
          <div className="stat">
            <span className="stat-label">Total Candidates</span>
            <span className="stat-value">{insights.total_candidates}</span>
          </div>
          <div className="stat">
            <span className="stat-label">Avg Match Score</span>
            <span className="stat-value">{Math.round(insights.avg_match_score * 100)}%</span>
          </div>
        </div>
      </div>

      {insights && (
        <div className="search-insights">
          <h3>Market Insights</h3>
          <div className="insights-grid">
            <div className="insight-card">
              <h4>Top Skills Matched</h4>
              <div className="skill-list">
                {insights.top_skills_matched.map((skill, index) => (
                  <span key={index} className="skill-tag">{skill}</span>
                ))}
              </div>
            </div>

            <div className="insight-card">
              <h4>Common Gaps</h4>
              <div className="gap-list">
                {insights.common_gaps.map((gap, index) => (
                  <span key={index} className="gap-tag">{gap}</span>
                ))}
              </div>
            </div>

            <div className="insight-card full-width">
              <h4>Market Analysis</h4>
              <p>{insights.market_analysis}</p>
            </div>

            {insights.recommendations.length > 0 && (
              <div className="insight-card full-width">
                <h4>Recommendations</h4>
                <ul>
                  {insights.recommendations.map((rec, index) => (
                    <li key={index}>{rec}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      )}

      <div className="candidates-list">
        <h3>Candidate Matches ({matches.length})</h3>
        {matches.length === 0 ? (
          <div className="no-results">
            <div className="no-results-icon">🔍</div>
            <h4>No matches found</h4>
            <p>Try adjusting your search criteria or requirements</p>
          </div>
        ) : (
          <div className="candidates-grid">
            {matches.map((match, index) => (
              <CandidateCard
                key={match.candidate.candidate_id}
                candidate={match.candidate}
                matchScore={match.score}
                similarity={match.similarity}
                rationale={match.rationale}
                rank={index + 1}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};