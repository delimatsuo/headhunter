import React, { useState } from 'react';
import './App.css';
import JobDescriptionForm from './components/JobDescriptionForm';
import CandidateResults from './components/CandidateResults';
import { searchJobCandidates, quickMatch } from './config/firebase';
import { JobDescription, SearchResponse, CandidateMatch } from './types';

function App() {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchResults, setSearchResults] = useState<{
    matches: CandidateMatch[];
    insights?: any;
    queryTime?: number;
  } | null>(null);
  const [quickMode, setQuickMode] = useState(false);

  const handleSearch = async (jobDesc: JobDescription) => {
    setIsLoading(true);
    setError(null);
    setSearchResults(null);

    try {
      const startTime = Date.now();
      
      if (quickMode) {
        // Quick match mode
        const quickDescription = `${jobDesc.title} at ${jobDesc.company}. ${jobDesc.description}`;
        const result = await quickMatch({ 
          description: quickDescription,
          limit: 10 
        });
        
        const data = result.data as any;
        
        // Convert quick match results to full match format
        const matches: CandidateMatch[] = data.matches.map((match: any) => ({
          candidate: {
            candidate_id: match.candidate_id,
            name: match.name,
            resume_analysis: {
              career_trajectory: {
                current_level: 'N/A',
                progression_speed: 'N/A',
                trajectory_type: 'N/A',
                domain_expertise: []
              },
              company_pedigree: {
                tier_level: 'N/A',
                company_types: [],
                recent_companies: []
              },
              years_experience: 0,
              technical_skills: [],
              soft_skills: [],
              education: {
                highest_degree: 'N/A',
                institutions: []
              }
            },
            overall_score: match.score
          },
          score: match.score,
          similarity: match.score / 100,
          rationale: {
            strengths: [match.summary],
            gaps: [],
            risk_factors: [],
            overall_assessment: match.summary
          }
        }));
        
        setSearchResults({
          matches,
          queryTime: Date.now() - startTime
        });
      } else {
        // Full search mode
        const result = await searchJobCandidates({ 
          jobDescription: jobDesc,
          limit: 20 
        });
        
        const data = result.data as SearchResponse;
        
        if (data.success) {
          setSearchResults({
            matches: data.matches,
            insights: data.insights,
            queryTime: data.query_time_ms || (Date.now() - startTime)
          });
        } else {
          throw new Error('Search failed');
        }
      }
    } catch (err: any) {
      console.error('Search error:', err);
      setError(err.message || 'Failed to search candidates. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="App">
      <header className="app-header">
        <div className="header-content">
          <div className="logo-section">
            <h1>🎯 Headhunter AI</h1>
            <p>AI-Powered Candidate Matching</p>
          </div>
          <div className="header-actions">
            <label className="mode-toggle">
              <input
                type="checkbox"
                checked={quickMode}
                onChange={(e) => setQuickMode(e.target.checked)}
              />
              <span>Quick Mode</span>
            </label>
          </div>
        </div>
      </header>

      <main className="app-main">
        <div className="container">
          <JobDescriptionForm 
            onSubmit={handleSearch}
            isLoading={isLoading}
          />
          
          {error && (
            <div className="error-message">
              <h3>Error</h3>
              <p>{error}</p>
            </div>
          )}
          
          {isLoading && (
            <div className="loading-container">
              <div className="loading-spinner"></div>
              <p>Searching for matching candidates...</p>
            </div>
          )}
          
          {searchResults && !isLoading && (
            <CandidateResults 
              matches={searchResults.matches}
              insights={searchResults.insights}
              queryTime={searchResults.queryTime}
            />
          )}
        </div>
      </main>

      <footer className="app-footer">
        <p>© 2025 Headhunter AI • Powered by Vertex AI & Cloud Functions</p>
      </footer>
    </div>
  );
}

export default App;
