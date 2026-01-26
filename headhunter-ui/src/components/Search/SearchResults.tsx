import React, { useState, useEffect, useMemo } from 'react';
import { SearchResponse, CandidateProfile, SignalScores, CandidateMatch, SlateDiversityAnalysis, AnonymizedCandidate } from '../../types';
import { SkillAwareCandidateCard } from '../Candidate/SkillAwareCandidateCard';
import { AnonymizedCandidateCard } from '../Candidate/AnonymizedCandidateCard';
import { EditCandidateModal } from '../Candidate/EditCandidateModal';
import { JobAnalysis } from './JobDescriptionForm';
import { SearchControls } from './SearchControls';
import { DiversityIndicator } from './DiversityIndicator';

// Sort options type
type SortOption = 'overall' | 'skills' | 'trajectory' | 'recency' | 'seniority';

interface SearchResultsProps {
  results: SearchResponse | null;
  loading: boolean;
  error: string | null;
  onFindSimilar?: (candidateId: string) => void;
  displayLimit?: number;
  onLoadMore?: () => void;
  onShowAll?: () => void;
  analysis?: JobAnalysis | null;
}

export const SearchResults: React.FC<SearchResultsProps> = ({
  results,
  loading,
  error,
  onFindSimilar,
  displayLimit = 20,
  onLoadMore,
  onShowAll,
  analysis
}) => {
  const [editingCandidate, setEditingCandidate] = useState<CandidateProfile | null>(null);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [analysisExpanded, setAnalysisExpanded] = useState(false);

  // Sort and filter state with localStorage persistence
  const [sortBy, setSortBy] = useState<SortOption>(() => {
    const saved = localStorage.getItem('hh_search_sortBy');
    return (saved as SortOption) || 'overall';
  });

  const [minSkillScore, setMinSkillScore] = useState<number>(() => {
    const saved = localStorage.getItem('hh_search_minSkillScore');
    return saved ? parseInt(saved, 10) : 0;
  });

  // Anonymized view state with localStorage persistence (BIAS-01)
  const [anonymizedView, setAnonymizedView] = useState<boolean>(() => {
    const saved = localStorage.getItem('hh_search_anonymizedView');
    return saved === 'true';
  });

  // Persist sort preference to localStorage
  useEffect(() => {
    localStorage.setItem('hh_search_sortBy', sortBy);
  }, [sortBy]);

  // Persist filter preference to localStorage
  useEffect(() => {
    localStorage.setItem('hh_search_minSkillScore', minSkillScore.toString());
  }, [minSkillScore]);

  // Persist anonymized view preference to localStorage
  useEffect(() => {
    localStorage.setItem('hh_search_anonymizedView', anonymizedView.toString());
  }, [anonymizedView]);

  /**
   * Convert a CandidateMatch to AnonymizedCandidate for blind hiring view.
   * Removes personally identifying information while preserving match-relevant data.
   */
  const convertToAnonymizedCandidate = (match: CandidateMatch): AnonymizedCandidate => {
    const candidate = match.candidate;
    const candidateAny = candidate as any;

    // Extract skills from various possible locations
    const technicalSkills = candidate.intelligent_analysis?.explicit_skills?.technical_skills || [];
    const softSkills = candidate.intelligent_analysis?.explicit_skills?.soft_skills || [];
    const allSkills = [
      ...technicalSkills.map(s => ({
        name: typeof s === 'string' ? s : s.skill,
        weight: typeof s === 'string' ? 1 : (s.confidence || 1)
      })),
      ...softSkills.map(s => ({
        name: typeof s === 'string' ? s : s.skill,
        weight: typeof s === 'string' ? 0.8 : (s.confidence || 0.8)
      }))
    ];

    // Extract years of experience
    const yearsExperience =
      candidateAny.years_experience ||
      candidate.intelligent_analysis?.career_trajectory_analysis?.years_experience ||
      candidate.resume_analysis?.years_experience ||
      undefined;

    // Extract industries (these don't identify individuals)
    const industries = candidateAny.industries || [];

    // Filter match reasons to remove company/school mentions
    const matchReasons = (candidate.matchReasons || []).filter(reason => {
      const lower = reason.toLowerCase();
      // Remove reasons that mention specific companies or schools
      return !lower.includes('company') && !lower.includes('school') && !lower.includes('university');
    });

    // Exclude company pedigree signals from signal scores
    const filteredSignalScores = match.signalScores ? {
      ...match.signalScores,
      companyPedigree: undefined,
      companyRelevance: undefined
    } : undefined;

    return {
      candidateId: candidate.candidate_id || candidate.id || `anon-${Math.random().toString(36).slice(2, 8)}`,
      score: match.score || 0,
      vectorScore: match.similarity || 0,
      textScore: 0,
      confidence: 0.8,
      yearsExperience,
      skills: allSkills.slice(0, 20),
      industries,
      matchReasons,
      signalScores: filteredSignalScores as any,
      weightsApplied: match.weightsApplied as any,
      mlTrajectory: candidate.mlTrajectory ? {
        nextRole: candidate.mlTrajectory.nextRole,
        nextRoleConfidence: candidate.mlTrajectory.nextRoleConfidence,
        tenureMonths: candidate.mlTrajectory.tenureMonths,
        hireability: candidate.mlTrajectory.hireability,
        lowConfidence: candidate.mlTrajectory.lowConfidence,
        uncertaintyReason: candidate.mlTrajectory.uncertaintyReason
      } : undefined,
      anonymized: true
    };
  };

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

  const { matches = [], insights = {
    total_candidates: 0,
    avg_match_score: 0,
    top_skills_matched: [],
    common_gaps: [],
    market_analysis: '',
    recommendations: []
  } } = results || {};

  // Sorted and filtered matches computation
  const sortedAndFilteredMatches = useMemo(() => {
    if (!matches || matches.length === 0) return [];

    // Type-safe helper to get signal score from CandidateMatch
    const getSignalScore = (match: CandidateMatch, signal: keyof SignalScores): number => {
      return match.signalScores?.[signal] ?? 0.5; // neutral if missing
    };

    // Filter by minimum skill score
    // NOTE: signalScores is at result level per CandidateMatch interface
    let filtered = matches.filter((m: CandidateMatch) => {
      const skillScore = getSignalScore(m, 'skillsExactMatch');
      return skillScore * 100 >= minSkillScore;
    });

    // Sort based on selection
    return filtered.sort((a: CandidateMatch, b: CandidateMatch) => {
      switch (sortBy) {
        case 'skills':
          return getSignalScore(b, 'skillsExactMatch') - getSignalScore(a, 'skillsExactMatch');
        case 'trajectory':
          return getSignalScore(b, 'trajectoryFit') - getSignalScore(a, 'trajectoryFit');
        case 'recency':
          return getSignalScore(b, 'recencyBoost') - getSignalScore(a, 'recencyBoost');
        case 'seniority':
          return getSignalScore(b, 'seniorityAlignment') - getSignalScore(a, 'seniorityAlignment');
        case 'overall':
        default:
          return (b.score ?? 0) - (a.score ?? 0);
      }
    });
  }, [matches, sortBy, minSkillScore]);

  // Show full screen loading only if we have no results yet
  if (loading && (!matches || matches.length === 0)) {
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



  const totalMatches = matches?.length || 0;
  const filteredCount = sortedAndFilteredMatches.length;
  const displayedMatches = sortedAndFilteredMatches.slice(0, displayLimit);
  const hasMore = filteredCount > displayLimit;

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

      {/* Sort and Filter Controls */}
      <div className="results-controls">
        <div className="sort-control">
          <label htmlFor="sort-select">Sort by:</label>
          <select
            id="sort-select"
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as SortOption)}
            className="sort-select"
          >
            <option value="overall">Best Match</option>
            <option value="skills">Skills Match</option>
            <option value="trajectory">Career Trajectory</option>
            <option value="recency">Skill Recency</option>
            <option value="seniority">Seniority Fit</option>
          </select>
        </div>

        <div className="filter-control">
          <label htmlFor="skill-filter">
            Min Skill Score: {minSkillScore}%
          </label>
          <input
            id="skill-filter"
            type="range"
            min="0"
            max="100"
            step="10"
            value={minSkillScore}
            onChange={(e) => setMinSkillScore(parseInt(e.target.value, 10))}
            className="filter-slider"
          />
        </div>

        {minSkillScore > 0 && (
          <button
            className="clear-filters"
            onClick={() => setMinSkillScore(0)}
          >
            Clear filter
          </button>
        )}

        {/* Show filtered count when filter is active */}
        {minSkillScore > 0 && filteredCount !== totalMatches && (
          <span className="filter-count">
            ({filteredCount} of {totalMatches} shown)
          </span>
        )}
      </div>

      {/* Anonymization Toggle (BIAS-01) */}
      <SearchControls
        anonymizedView={anonymizedView}
        onToggleAnonymized={setAnonymizedView}
        disabled={loading}
      />

      {/* Diversity Indicator (BIAS-05) */}
      {(results as any)?.diversityAnalysis && (
        <DiversityIndicator analysis={(results as any).diversityAnalysis as SlateDiversityAnalysis} />
      )}

      {/* Collapsible AI Analysis Summary */}
      {analysis && (
        <div style={{
          marginBottom: '16px',
          background: '#F8FAFC',
          border: '1px solid #E2E8F0',
          borderRadius: '8px',
          overflow: 'hidden'
        }}>
          <button
            onClick={() => setAnalysisExpanded(!analysisExpanded)}
            style={{
              width: '100%',
              padding: '12px 16px',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              background: 'transparent',
              border: 'none',
              cursor: 'pointer',
              fontSize: '14px',
              fontWeight: '600',
              color: '#475569'
            }}
          >
            <span>
              AI Analysis: {analysis.job_title || 'Untitled Role'}
              {analysis.experience_level && ` (${analysis.experience_level})`}
              {analysis.required_skills && analysis.required_skills.length > 0 &&
                ` - ${analysis.required_skills.length} skills detected`}
            </span>
            <span style={{ fontSize: '12px', color: '#94A3B8' }}>
              {analysisExpanded ? '▲ Hide' : '▼ Show details'}
            </span>
          </button>

          {analysisExpanded && (
            <div style={{ padding: '0 16px 16px 16px', borderTop: '1px solid #E2E8F0' }}>
              <div style={{ display: 'grid', gap: '12px', marginTop: '12px' }}>
                {analysis.summary && (
                  <div>
                    <strong style={{ color: '#64748B', fontSize: '12px', textTransform: 'uppercase' }}>Summary</strong>
                    <p style={{ margin: '4px 0 0 0', color: '#334155', fontSize: '14px' }}>{analysis.summary}</p>
                  </div>
                )}

                {analysis.required_skills && analysis.required_skills.length > 0 && (
                  <div>
                    <strong style={{ color: '#64748B', fontSize: '12px', textTransform: 'uppercase' }}>Required Skills</strong>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '6px' }}>
                      {analysis.required_skills.map((skill, idx) => (
                        <span key={idx} style={{
                          padding: '4px 8px',
                          background: '#DBEAFE',
                          color: '#1E40AF',
                          borderRadius: '4px',
                          fontSize: '12px',
                          fontWeight: '500'
                        }}>{skill}</span>
                      ))}
                    </div>
                  </div>
                )}

                {analysis.preferred_skills && analysis.preferred_skills.length > 0 && (
                  <div>
                    <strong style={{ color: '#64748B', fontSize: '12px', textTransform: 'uppercase' }}>Nice to Have</strong>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '6px' }}>
                      {analysis.preferred_skills.map((skill, idx) => (
                        <span key={idx} style={{
                          padding: '4px 8px',
                          background: '#F1F5F9',
                          color: '#475569',
                          borderRadius: '4px',
                          fontSize: '12px',
                          fontWeight: '500'
                        }}>{skill}</span>
                      ))}
                    </div>
                  </div>
                )}

                {analysis.sourcing_strategy?.target_companies && analysis.sourcing_strategy.target_companies.length > 0 && (
                  <div style={{
                    padding: '10px',
                    background: '#EEF2FF',
                    borderRadius: '6px',
                    border: '1px solid #C7D2FE'
                  }}>
                    <strong style={{ color: '#4338CA', fontSize: '12px' }}>Target Companies</strong>
                    <p style={{ margin: '4px 0 0 0', color: '#4F46E5', fontSize: '13px' }}>
                      {analysis.sourcing_strategy.target_companies.slice(0, 8).join(', ')}
                      {analysis.sourcing_strategy.target_companies.length > 8 &&
                        ` +${analysis.sourcing_strategy.target_companies.length - 8} more`}
                    </p>
                    {analysis.sourcing_strategy.target_industries && analysis.sourcing_strategy.target_industries.length > 0 && (
                      <p style={{ margin: '6px 0 0 0', color: '#6366F1', fontSize: '12px' }}>
                        Industries: {analysis.sourcing_strategy.target_industries.join(', ')}
                      </p>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Fallback Warning Banner */}
      {matches?.some((m: any) => m.candidate?.usedFallback || m.usedFallback) && (
        <div className="fallback-warning" style={{
          backgroundColor: '#fff3cd',
          border: '1px solid #ffc107',
          borderRadius: '8px',
          padding: '12px 16px',
          marginBottom: '16px',
          display: 'flex',
          alignItems: 'center',
          gap: '12px'
        }}>
          <span style={{ fontSize: '20px' }}>⚠️</span>
          <div>
            <strong style={{ color: '#856404' }}>AI Ranking Unavailable</strong>
            <p style={{ margin: '4px 0 0 0', color: '#856404', fontSize: '14px' }}>
              Results are sorted using keyword-based matching. For best results, please try your search again.
            </p>
          </div>
        </div>
      )}

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
                anonymizedView ? (
                  <AnonymizedCandidateCard
                    key={match.candidate?.candidate_id || index}
                    candidate={convertToAnonymizedCandidate(match)}
                    rank={index + 1}
                    searchSkills={[]}
                  />
                ) : (
                  <SkillAwareCandidateCard
                    key={match.candidate?.candidate_id || index}
                    candidate={match.candidate}
                    matchScore={match.score}
                    similarityScore={match.similarity}
                    rank={index + 1}
                    searchSkills={[]}
                    signalScores={match.signalScores}
                    weightsApplied={match.weightsApplied}
                    matchRationale={match.matchRationale}
                    onFindSimilar={onFindSimilar ? () => onFindSimilar(match.candidate?.candidate_id || '') : undefined}
                    onEdit={match.candidate ? () => handleEditClick(match.candidate) : undefined}
                  />
                )
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
                {onLoadMore && !loading && (
                  <button
                    onClick={onLoadMore}
                    disabled={loading}
                    style={{
                      padding: '12px 24px',
                      fontSize: '14px',
                      fontWeight: '600',
                      color: '#3B82F6',
                      background: 'white',
                      border: '2px solid #3B82F6',
                      borderRadius: '8px',
                      cursor: 'pointer',
                      transition: 'all 0.2s',
                      opacity: loading ? 0.5 : 1
                    }}
                    onMouseOver={(e) => {
                      if (!loading) e.currentTarget.style.background = '#EFF6FF';
                    }}
                    onMouseOut={(e) => {
                      if (!loading) e.currentTarget.style.background = 'white';
                    }}
                  >
                    Load More (+20)
                  </button>
                )}

                {loading && matches.length > 0 && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', color: '#666' }}>
                    <div className="loading-spinner" style={{ width: '20px', height: '20px', borderWidth: '2px' }}></div>
                    <span>Loading more...</span>
                  </div>
                )}

                {onShowAll && !loading && (
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