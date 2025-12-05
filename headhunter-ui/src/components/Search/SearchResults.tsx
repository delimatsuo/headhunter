import React, { useState } from 'react';
import { SearchResponse, CandidateMatch, CandidateProfile } from '../../types';
import { SkillAwareCandidateCard } from '../Candidate/SkillAwareCandidateCard';
import { EditCandidateModal } from '../Candidate/EditCandidateModal';

interface SearchResultsProps {
  results: SearchResponse | null;
  loading: boolean;
  error: string | null;
  onFindSimilar?: (candidateId: string) => void;
  displayLimit?: number;
  onLoadMore?: () => void;
  onShowAll?: () => void;
}

export const SearchResults: React.FC<SearchResultsProps> = ({
  results,
  loading,
  error,
  onFindSimilar,
  displayLimit = 20,
  onLoadMore,
  onShowAll
}) => {
  const [editingCandidate, setEditingCandidate] = useState<CandidateProfile | null>(null);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);

  const handleEditClick = (candidate: CandidateProfile) => {
    setEditingCandidate(candidate);
    setIsEditModalOpen(true);
  };

  const handleEditClose = () => {
    setIsEditModalOpen(false);
    setEditingCandidate(null);
  };

  const handleCandidateUpdated = (updatedCandidate: CandidateProfile) => {
    // The candidate data is updated in Firestore, 
    // refresh will show updated data on next search
    console.log('Candidate updated:', updatedCandidate.name);
  };

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

  const totalMatches = matches?.length || 0;
  const displayedMatches = matches?.slice(0, displayLimit) || [];
  const hasMore = totalMatches > displayLimit;

  return (
    <div className="search-results">
      <div className="results-header">
        <div className="results-summary">
          <h2>Search Results</h2>
          <p>
            {hasMore
              ? `Showing ${displayLimit} of ${totalMatches} matching candidates`
              : `Found ${totalMatches} matching candidates`
            }
            {results?.query_time_ms ? ` in ${results.query_time_ms}ms` : ''}
          </p>
        </div>

        <div className="results-stats">
          <div className="stat">
            <span className="stat-label">Total Candidates</span>
            <span className="stat-value">{insights?.total_candidates || totalMatches}</span>
          </div>
          <div className="stat">
            <span className="stat-label">Avg Match Score</span>
            <span className="stat-value">{Math.round((insights?.avg_match_score || 0) > 1 ? (insights?.avg_match_score || 0) : (insights?.avg_match_score || 0) * 100)}%</span>
          </div>
        </div>
      </div>

      <div className="candidates-list">
        <h3>Candidate Matches ({totalMatches})</h3>
        {(!matches || matches.length === 0) ? (
          <div className="no-results">
            <div className="no-results-icon">🔍</div>
            <h4>No matches found</h4>
            <p>Try adjusting your search criteria or requirements</p>
          </div>
        ) : (
          <>
            <div className="candidates-grid">
              {displayedMatches.map((match, index) => (
                <SkillAwareCandidateCard
                  key={match.candidate?.candidate_id || index}
                  candidate={match.candidate}
                  matchScore={match.score}
                  similarity={match.similarity}
                  rank={index + 1}
                  searchSkills={[]}
                  onFindSimilar={onFindSimilar ? () => onFindSimilar(match.candidate?.candidate_id || '') : undefined}
                  onEdit={match.candidate ? () => handleEditClick(match.candidate) : undefined}
                />
              ))}
            </div>

            {hasMore && (
              <div style={{
                display: 'flex',
                justifyContent: 'center',
                gap: '16px',
                marginTop: '24px',
                paddingBottom: '16px'
              }}>
                {onLoadMore && (
                  <button
                    onClick={onLoadMore}
                    style={{
                      padding: '12px 24px',
                      fontSize: '14px',
                      fontWeight: '600',
                      color: '#3B82F6',
                      background: 'white',
                      border: '2px solid #3B82F6',
                      borderRadius: '8px',
                      cursor: 'pointer',
                      transition: 'all 0.2s'
                    }}
                    onMouseOver={(e) => {
                      e.currentTarget.style.background = '#EFF6FF';
                    }}
                    onMouseOut={(e) => {
                      e.currentTarget.style.background = 'white';
                    }}
                  >
                    Load More (+20)
                  </button>
                )}
                {onShowAll && (
                  <button
                    onClick={onShowAll}
                    style={{
                      padding: '12px 24px',
                      fontSize: '14px',
                      fontWeight: '600',
                      color: 'white',
                      background: 'linear-gradient(135deg, #3B82F6 0%, #2563EB 100%)',
                      border: 'none',
                      borderRadius: '8px',
                      cursor: 'pointer',
                      transition: 'all 0.2s'
                    }}
                    onMouseOver={(e) => {
                      e.currentTarget.style.transform = 'translateY(-1px)';
                    }}
                    onMouseOut={(e) => {
                      e.currentTarget.style.transform = 'translateY(0)';
                    }}
                  >
                    Show All ({totalMatches})
                  </button>
                )}
              </div>
            )}
          </>
        )}
      </div>

      {/* Edit Candidate Modal */}
      <EditCandidateModal
        isOpen={isEditModalOpen}
        onClose={handleEditClose}
        candidate={editingCandidate}
        onCandidateUpdated={handleCandidateUpdated}
      />
    </div>
  );
};