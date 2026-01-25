import React, { useState } from 'react';
import { JobDescriptionForm, SourcingStrategy, JobAnalysis } from './JobDescriptionForm';
import { SearchResults } from './SearchResults';
import { AddCandidateModal } from '../Upload/AddCandidateModal';
import { EngineSelector, EngineType } from './EngineSelector';
import { apiService } from '../../services/api';
import { JobDescription, SearchResponse, CandidateProfile } from '../../types';

export const SearchPage: React.FC = () => {
  const [searchResults, setSearchResults] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingPhase, setLoadingPhase] = useState<'analyzing' | 'searching' | null>(null);
  const [error, setError] = useState<string>('');
  const [showAddCandidate, setShowAddCandidate] = useState(false);
  const [searchHistory, setSearchHistory] = useState<JobDescription[]>([]);
  const [displayLimit, setDisplayLimit] = useState(50); // Progressive loading: show 50 at a time
  const [selectedEngine, setSelectedEngine] = useState<EngineType>('legacy');
  const [currentAnalysis, setCurrentAnalysis] = useState<JobAnalysis | null>(null);

  const handleSearch = async (jobDescription: JobDescription, sourcingStrategy?: SourcingStrategy, analysis?: JobAnalysis) => {
    setLoading(true);
    setLoadingPhase('searching'); // Analysis happens in form, we start at 'searching'
    setError('');
    setSearchResults(null);
    setDisplayLimit(50); // Reset to 50 on new search

    // Store analysis for display in results
    if (analysis) {
      setCurrentAnalysis(analysis);
    }

    try {
      // Use the selected AI engine for the search
      const results = await apiService.searchWithEngine(
        selectedEngine,
        jobDescription,
        {
          limit: 50,
          includeMatchRationale: true,  // TRNS-03: Request LLM rationale for top 10 candidates
          sourcingStrategy: {
            target_companies: sourcingStrategy?.target_companies,
            target_industries: sourcingStrategy?.target_industries,
          }
        }
      );
      setSearchResults(results);

      // Add to search history
      setSearchHistory(prev => {
        const updated = [jobDescription, ...prev];
        return updated.slice(0, 5); // Keep only last 5 searches
      });
    } catch (error: any) {
      console.error('Search error:', error);
      setError(error.message || 'Search failed');
    } finally {
      setLoading(false);
      setLoadingPhase(null);
    }
  };

  const handleLoadMore = () => {
    setDisplayLimit(prev => prev + 50); // Load 50 more candidates
  };

  const handleCandidateAdded = (candidate: CandidateProfile) => {
    // Could refresh search results if there are any
    console.log('New candidate added:', candidate.name);
  };

  const handleQuickSearch = (jobDesc: JobDescription) => {
    handleSearch(jobDesc);
  };

  return (
    <div className="search-page">
      <div className="page-header">
        <div className="header-content">
          <h1>Candidate Search</h1>
          <p>Find the perfect candidates for your job requirements using AI-powered matching</p>
        </div>
        <button
          className="btn btn-secondary"
          onClick={() => setShowAddCandidate(true)}
        >
          <span className="btn-icon">➕</span>
          Add Candidate
        </button>
      </div>

      <div className="search-container">
        <div className="search-form-section">
          <EngineSelector
            selected={selectedEngine}
            onChange={setSelectedEngine}
            disabled={loading}
          />
          <JobDescriptionForm
            onSearch={handleSearch}
            loading={loading}
            loadingPhase={loadingPhase}
          />

          {/* Search History */}
          {searchHistory.length > 0 && (
            <div className="search-history">
              <h3>Recent Searches</h3>
              <div className="history-list">
                {searchHistory.map((search, index) => (
                  <div key={index} className="history-item">
                    <div className="history-content">
                      <h4>{search.title}</h4>
                      {search.company && <p className="history-company">{search.company}</p>}
                      <p className="history-preview">
                        {search.description.substring(0, 100)}...
                      </p>
                      <div className="history-meta">
                        <span className="skill-count">
                          {(search.required_skills?.length || 0) + (search.nice_to_have?.length || 0)} skills
                        </span>
                        <span className="experience-range">
                          {search.min_experience}-{search.max_experience} years
                        </span>
                      </div>
                    </div>
                    <button
                      className="btn btn-outline btn-small"
                      onClick={() => handleQuickSearch(search)}
                      disabled={loading}
                    >
                      Search Again
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="search-results-section">
          <SearchResults
            results={searchResults}
            loading={loading}
            error={error}
            displayLimit={displayLimit}
            onLoadMore={handleLoadMore}
            analysis={currentAnalysis}
          />

          {/* Tips for better results */}
          {!searchResults && !loading && (
            <div className="search-tips">
              <h3>Tips for Better Results</h3>
              <div className="tips-grid">
                <div className="tip-card">
                  <div className="tip-icon">💡</div>
                  <h4>Be Specific</h4>
                  <p>Include specific technologies, frameworks, and tools in your job description for more accurate matching.</p>
                </div>

                <div className="tip-card">
                  <div className="tip-icon">🎯</div>
                  <h4>Skills Matter</h4>
                  <p>Separate required skills from nice-to-have skills to help the AI understand your priorities.</p>
                </div>

                <div className="tip-card">
                  <div className="tip-icon">📊</div>
                  <h4>Experience Range</h4>
                  <p>Set realistic experience ranges to find candidates who match your seniority requirements.</p>
                </div>

                <div className="tip-card">
                  <div className="tip-icon">👥</div>
                  <h4>Leadership Needs</h4>
                  <p>Specify if leadership experience is required to filter for management candidates.</p>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      <AddCandidateModal
        isOpen={showAddCandidate}
        onClose={() => setShowAddCandidate(false)}
        onCandidateAdded={handleCandidateAdded}
      />
    </div>
  );
};
