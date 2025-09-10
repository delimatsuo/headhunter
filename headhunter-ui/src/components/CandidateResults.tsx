import React, { useState } from 'react';
import DOMPurify from 'dompurify';
import { CandidateMatch, SearchInsights } from '../types';
import './CandidateResults.css';

interface CandidateResultsProps {
  matches: CandidateMatch[];
  insights?: SearchInsights;
  queryTime?: number;
}

const CandidateResults: React.FC<CandidateResultsProps> = ({ matches, insights, queryTime }) => {
  const [expandedCandidate, setExpandedCandidate] = useState<string | null>(null);

  const toggleExpand = (candidateId: string) => {
    setExpandedCandidate(prev => prev === candidateId ? null : candidateId);
  };

  const getScoreColor = (score: number) => {
    if (score >= 80) return '#10b981';
    if (score >= 60) return '#f59e0b';
    return '#ef4444';
  };

  const formatQueryTime = (ms?: number) => {
    if (!ms) return '';
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  };

  if (matches.length === 0) {
    return (
      <div className="no-results">
        <h3>No candidates found</h3>
        <p>Try adjusting your search criteria or job description.</p>
      </div>
    );
  }

  return (
    <div className="results-container">
      {insights && (
        <div className="insights-panel">
          <h3>Search Insights</h3>
          <div className="insights-grid">
            <div className="insight-item">
              <span className="insight-label">Total Candidates</span>
              <span className="insight-value">{insights.total_candidates}</span>
            </div>
            <div className="insight-item">
              <span className="insight-label">Avg Match Score</span>
              <span className="insight-value">{insights.avg_match_score.toFixed(1)}%</span>
            </div>
            {queryTime && (
              <div className="insight-item">
                <span className="insight-label">Query Time</span>
                <span className="insight-value">{formatQueryTime(queryTime)}</span>
              </div>
            )}
          </div>
          
          {insights.top_skills_matched.length > 0 && (
            <div className="insight-section">
              <h4>Top Skills Matched</h4>
              <div className="skill-tags">
                {insights.top_skills_matched.map((skill, idx) => (
                  <span key={idx} className="skill-tag" dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(skill) }} />
                ))}
              </div>
            </div>
          )}
          
          {insights.market_analysis && (
            <div className="insight-section">
              <h4>Market Analysis</h4>
              <p dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(insights.market_analysis) }} />
            </div>
          )}
          
          {insights.recommendations.length > 0 && (
            <div className="insight-section">
              <h4>Recommendations</h4>
              <ul>
                {insights.recommendations.map((rec, idx) => (
                  <li key={idx} dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(rec) }} />
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      <div className="candidates-list">
        <h3>Matched Candidates ({matches.length})</h3>
        
        {matches.map((match) => {
          const isExpanded = expandedCandidate === match.candidate.candidate_id;
          
          return (
            <div key={match.candidate.candidate_id} className="candidate-card">
              <div className="candidate-header" onClick={() => toggleExpand(match.candidate.candidate_id || '')}>
                <div className="candidate-main">
                  <h4 dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(match.candidate.name) }} />
                  <div className="candidate-info">
                    <span className="info-item">
                      {match.candidate.resume_analysis?.career_trajectory?.current_level || 'Not specified'}
                    </span>
                    <span className="info-item">
                      {match.candidate.resume_analysis?.years_experience || 0} years
                    </span>
                    <span className="info-item">
                      {match.candidate.resume_analysis?.company_pedigree?.recent_companies?.[0] || 'No company info'}
                    </span>
                  </div>
                </div>
                
                <div className="candidate-scores">
                  <div className="score-item">
                    <span className="score-label">Match</span>
                    <span 
                      className="score-value"
                      style={{ color: getScoreColor(match.score) }}
                    >
                      {match.score.toFixed(0)}%
                    </span>
                  </div>
                  <div className="score-item">
                    <span className="score-label">Similarity</span>
                    <span className="score-value">{(match.similarity * 100).toFixed(0)}%</span>
                  </div>
                  <button className="expand-btn">
                    {isExpanded ? '−' : '+'}
                  </button>
                </div>
              </div>
              
              {isExpanded && (
                <div className="candidate-details">
                  <div className="rationale-section">
                    <h5>Why They're a Match</h5>
                    <p className="assessment" dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(match.rationale.overall_assessment) }} />
                    
                    <div className="rationale-grid">
                      <div className="rationale-column">
                        <h6>✅ Strengths</h6>
                        <ul>
                          {match.rationale.strengths.map((strength, idx) => (
                            <li key={idx} dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(strength) }} />
                          ))}
                        </ul>
                      </div>
                      
                      {match.rationale.gaps.length > 0 && (
                        <div className="rationale-column">
                          <h6>⚠️ Gaps</h6>
                          <ul>
                            {match.rationale.gaps.map((gap, idx) => (
                              <li key={idx} dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(gap) }} />
                            ))}
                          </ul>
                        </div>
                      )}
                      
                      {match.rationale.risk_factors.length > 0 && (
                        <div className="rationale-column">
                          <h6>🚨 Risk Factors</h6>
                          <ul>
                            {match.rationale.risk_factors.map((risk, idx) => (
                              <li key={idx} dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(risk) }} />
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  </div>
                  
                  <div className="details-grid">
                    <div className="detail-section">
                      <h6>Technical Skills</h6>
                      <div className="skill-tags">
                        {(match.candidate.resume_analysis?.technical_skills || []).map((skill, idx) => (
                          <span key={idx} className="skill-tag" dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(skill) }} />
                        ))}
                      </div>
                    </div>
                    
                    <div className="detail-section">
                      <h6>Career Trajectory</h6>
                      <p>{match.candidate.resume_analysis?.career_trajectory?.trajectory_type || 'Not specified'}</p>
                      <p className="sub-text">
                        {match.candidate.resume_analysis?.career_trajectory?.progression_speed || 'Not specified'} progression
                      </p>
                    </div>
                    
                    {match.candidate.resume_analysis?.leadership_scope?.has_leadership && (
                      <div className="detail-section">
                        <h6>Leadership Experience</h6>
                        <p>{match.candidate.resume_analysis?.leadership_scope?.leadership_level || 'Not specified'}</p>
                        <p className="sub-text">
                          Team size: {match.candidate.resume_analysis?.leadership_scope?.team_size || 'Not specified'}
                        </p>
                      </div>
                    )}
                    
                    <div className="detail-section">
                      <h6>Education</h6>
                      <p>{match.candidate.resume_analysis?.education?.highest_degree || 'Not specified'}</p>
                      <p className="sub-text">
                        {match.candidate.resume_analysis?.education?.institutions?.[0] || 'Not specified'}
                      </p>
                    </div>
                  </div>
                  
                  {match.candidate.recruiter_insights && (
                    <div className="recruiter-insights">
                      <h6>Recruiter Insights</h6>
                      <div className="key-themes">
                        {match.candidate.recruiter_insights.key_themes.map((theme, idx) => (
                          <span key={idx} className="theme-tag" dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(theme) }} />
                        ))}
                      </div>
                      <p className="recommendation">
                        Recommendation: <strong>{match.candidate.recruiter_insights.recommendation}</strong>
                      </p>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default CandidateResults;