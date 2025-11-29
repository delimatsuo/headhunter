import React, { useState, useEffect } from 'react';
import { CandidateProfile, SkillAssessment, SkillMatchData } from '../../types';
import { SkillConfidenceDisplay } from '../Skills/SkillConfidenceDisplay';
import { api } from '../../services/api';
import './SkillAwareCandidateCard.css';

interface SkillAwareCandidateCardProps {
  candidate: CandidateProfile;
  matchScore?: number;
  similarity?: number;
  skillMatches?: SkillMatchData[];
  searchSkills?: string[];
  rank?: number;
  onClick?: () => void;
  showDetailedSkills?: boolean;
}

export const SkillAwareCandidateCard: React.FC<SkillAwareCandidateCardProps> = ({
  candidate,
  matchScore,
  similarity,
  skillMatches = [],
  searchSkills = [],
  rank,
  onClick,
  showDetailedSkills = false,
}) => {
  const [expanded, setExpanded] = useState(false);
  const [skillAssessment, setSkillAssessment] = useState<SkillAssessment | null>(null);
  const [loadingSkills, setLoadingSkills] = useState(false);
  const [skillsLoaded, setSkillsLoaded] = useState(false);

  const candidateId = candidate.candidate_id || candidate.id || '';

  useEffect(() => {
    if (expanded && showDetailedSkills && !skillsLoaded && candidateId) {
      loadSkillAssessment();
    }
  }, [expanded, showDetailedSkills, skillsLoaded, candidateId]);

  const loadSkillAssessment = async () => {
    if (!candidateId) return;

    setLoadingSkills(true);
    try {
      const response = await api.getCandidateSkillAssessment(candidateId);
      if (response.success && response.data) {
        setSkillAssessment(response.data.skill_assessment);
        setSkillsLoaded(true);
      }
    } catch (error) {
      console.error('Error loading skill assessment:', error);
    } finally {
      setLoadingSkills(false);
    }
  };

  const handleCardClick = () => {
    if (onClick) {
      onClick();
    } else {
      setExpanded(!expanded);
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'excellent';
    if (score >= 60) return 'good';
    if (score >= 40) return 'fair';
    return 'poor';
  };

  const formatScore = (score: number) => Math.round(score);

  const getOverallConfidence = () => {
    if (skillAssessment) {
      return skillAssessment.average_confidence;
    }
    // Fallback calculation from basic candidate data
    return candidate.overall_score ? candidate.overall_score * 100 : 0;
  };

  const getMatchedSkillsCount = () => {
    if (!searchSkills.length) return 0;

    const candidateSkills = [
      ...(candidate.resume_analysis?.technical_skills || []),
      ...(candidate.resume_analysis?.soft_skills || [])
    ].map(skill => skill.toLowerCase());

    return searchSkills.filter(skill =>
      candidateSkills.some(cSkill => cSkill.includes(skill.toLowerCase()))
    ).length;
  };

  const getSkillMatchPercentage = () => {
    if (!searchSkills.length) return 0;
    return Math.round((getMatchedSkillsCount() / searchSkills.length) * 100);
  };

  return (
    <div className={`skill-aware-candidate-card ${expanded ? 'expanded' : ''}`}>
      <div className="card-header" onClick={handleCardClick}>
        <div className="candidate-info">
          {rank && (
            <div className="rank-badge">
              #{rank}
            </div>
          )}
          <div className="candidate-details">
            <h3 className="candidate-name">{candidate.name}</h3>
            <p className="candidate-level">
              {candidate.resume_analysis?.career_trajectory?.current_level || 'Not specified'}
            </p>
            <p className="candidate-experience">
              {candidate.resume_analysis?.years_experience || 0} years experience
            </p>
          </div>
        </div>

        <div className="scores">
          {matchScore !== undefined && (
            <div className={`score-badge ${getScoreColor(matchScore)}`}>
              <span className="score-value">{formatScore(matchScore)}%</span>
              <span className="score-label">Match</span>
            </div>
          )}

          {similarity !== undefined && (
            <div className={`score-badge ${getScoreColor(similarity)}`}>
              <span className="score-value">{formatScore(similarity)}%</span>
              <span className="score-label">Similarity</span>
            </div>
          )}

          <div className={`score-badge ${getScoreColor(getOverallConfidence())}`}>
            <span className="score-value">{formatScore(getOverallConfidence())}%</span>
            <span className="score-label">Confidence</span>
          </div>

          {searchSkills.length > 0 && (
            <div className={`score-badge ${getScoreColor(getSkillMatchPercentage())}`}>
              <span className="score-value">{getMatchedSkillsCount()}/{searchSkills.length}</span>
              <span className="score-label">Skills</span>
            </div>
          )}
        </div>
      </div>

      <div className="card-content">
        <div className="quick-skills-overview">
          {skillAssessment ? (
            <SkillConfidenceDisplay
              candidateId={candidateId}
              skillAssessment={skillAssessment}
              skillMatches={skillMatches}
              searchSkills={searchSkills}
              compact={true}
              showEvidence={false}
            />
          ) : (
            <div className="basic-skills-preview">
              <div className="skill-category">
                <h4>Technical Skills</h4>
                <div className="skills-tags">
                  {(candidate.resume_analysis?.technical_skills || []).slice(0, 4).map((skill, index) => {
                    const isRequired = searchSkills.some(s => s.toLowerCase() === skill.toLowerCase());
                    return (
                      <span
                        key={index}
                        className={`skill-tag technical ${isRequired ? 'required' : ''}`}
                      >
                        {skill}
                      </span>
                    );
                  })}
                  {(candidate.resume_analysis?.technical_skills?.length || 0) > 4 && (
                    <span className="skill-tag more">
                      +{(candidate.resume_analysis?.technical_skills?.length || 0) - 4}
                    </span>
                  )}
                </div>
              </div>

              {(candidate.resume_analysis?.soft_skills?.length || 0) > 0 && (
                <div className="skill-category">
                  <h4>Soft Skills</h4>
                  <div className="skills-tags">
                    {(candidate.resume_analysis?.soft_skills || []).slice(0, 3).map((skill, index) => {
                      const isRequired = searchSkills.some(s => s.toLowerCase() === skill.toLowerCase());
                      return (
                        <span
                          key={index}
                          className={`skill-tag soft ${isRequired ? 'required' : ''}`}
                        >
                          {skill}
                        </span>
                      );
                    })}
                    {(candidate.resume_analysis?.soft_skills?.length || 0) > 3 && (
                      <span className="skill-tag more">
                        +{(candidate.resume_analysis?.soft_skills?.length || 0) - 3}
                      </span>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {searchSkills.length > 0 && (
          <div className="skill-match-summary">
            <h4>Required Skills Match</h4>
            <div className="skill-match-grid">
              {searchSkills.map((requiredSkill, index) => {
                const candidateSkills = [
                  ...(candidate.resume_analysis?.technical_skills || []),
                  ...(candidate.resume_analysis?.soft_skills || [])
                ];

                const hasSkill = candidateSkills.some(skill =>
                  skill.toLowerCase().includes(requiredSkill.toLowerCase())
                );

                const matchData = skillMatches.find(m =>
                  m.skill.toLowerCase() === requiredSkill.toLowerCase()
                );

                return (
                  <div key={index} className={`skill-match-item ${hasSkill ? 'matched' : 'missing'}`}>
                    <span className="skill-name">{requiredSkill}</span>
                    <span className="match-indicator">
                      {hasSkill ? '✓' : '✗'}
                    </span>
                    {matchData && (
                      <span className="match-confidence">
                        {Math.round(matchData.candidate_confidence)}%
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        <div className="company-info">
          <h4>Recent Companies</h4>
          <div className="companies">
            {(candidate.resume_analysis?.company_pedigree?.recent_companies || []).slice(0, 3).map((company, index) => (
              <span key={index} className="company-tag">{company}</span>
            ))}
          </div>
          <span className={`tier-badge ${(candidate.resume_analysis?.company_pedigree?.tier_level || 'unknown').toLowerCase()}`}>
            {candidate.resume_analysis?.company_pedigree?.tier_level || 'Unknown'} Tier
          </span>
        </div>
      </div>

      {expanded && (
        <div className="card-details">
          {showDetailedSkills && candidateId && (
            <div className="detailed-skills-section">
              {loadingSkills ? (
                <div className="loading-skills">
                  <p>Loading detailed skill assessment...</p>
                </div>
              ) : skillAssessment ? (
                <SkillConfidenceDisplay
                  candidateId={candidateId}
                  skillAssessment={skillAssessment}
                  skillMatches={skillMatches}
                  searchSkills={searchSkills}
                  title="Detailed Skill Assessment"
                  compact={false}
                  showEvidence={true}
                />
              ) : (
                <div className="skills-error">
                  <p>Could not load detailed skill assessment</p>
                  <button onClick={loadSkillAssessment} className="retry-btn">
                    Retry
                  </button>
                </div>
              )}
            </div>
          )}

          <div className="traditional-details">
            <div className="details-grid">
              <div className="detail-section">
                <h4>Career Trajectory</h4>
                <p><strong>Progression:</strong> {candidate.resume_analysis?.career_trajectory?.progression_speed || 'Not specified'}</p>
                <p><strong>Type:</strong> {candidate.resume_analysis?.career_trajectory?.trajectory_type || 'Not specified'}</p>
                <div className="domain-expertise">
                  <strong>Domain Expertise:</strong>
                  {(candidate.resume_analysis?.career_trajectory?.domain_expertise || []).map((domain, index) => (
                    <span key={index} className="domain-tag">{domain}</span>
                  ))}
                </div>
              </div>

              {candidate.resume_analysis?.leadership_scope && (
                <div className="detail-section">
                  <h4>Leadership</h4>
                  <p><strong>Has Leadership:</strong> {candidate.resume_analysis.leadership_scope.has_leadership ? 'Yes' : 'No'}</p>
                  {candidate.resume_analysis.leadership_scope.team_size && (
                    <p><strong>Team Size:</strong> {candidate.resume_analysis.leadership_scope.team_size}</p>
                  )}
                  {candidate.resume_analysis.leadership_scope.leadership_level && (
                    <p><strong>Level:</strong> {candidate.resume_analysis.leadership_scope.leadership_level}</p>
                  )}
                </div>
              )}

              <div className="detail-section">
                <h4>Education</h4>
                <p><strong>Highest Degree:</strong> {candidate.resume_analysis?.education?.highest_degree || 'Not specified'}</p>
                <div className="institutions">
                  <strong>Institutions:</strong>
                  {(candidate.resume_analysis?.education?.institutions || []).map((institution, index) => (
                    <span key={index} className="institution-tag">{institution}</span>
                  ))}
                </div>
              </div>

              {candidate.recruiter_insights && (
                <div className="detail-section">
                  <h4>Recruiter Insights</h4>
                  <div className="recruiter-strengths">
                    <strong>Strengths:</strong>
                    <ul>
                      {(candidate.recruiter_insights.strengths || []).map((strength, index) => (
                        <li key={index}>{strength}</li>
                      ))}
                    </ul>
                  </div>
                  <p><strong>Recommendation:</strong> {candidate.recruiter_insights.recommendation || 'Not specified'}</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      <div className="card-footer">
        <button className="expand-button">
          {expanded ? 'Show Less' : 'Show More'}
        </button>
        {showDetailedSkills && expanded && !skillsLoaded && (
          <button onClick={loadSkillAssessment} className="load-skills-button">
            Load Skill Details
          </button>
        )}
      </div>
    </div>
  );
};