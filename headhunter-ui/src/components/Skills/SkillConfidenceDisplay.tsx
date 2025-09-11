import React, { useState } from 'react';
import { SkillWithEvidence, SkillAssessment, SkillMatchData } from '../../types';
import './SkillConfidenceDisplay.css';

interface SkillConfidenceDisplayProps {
  candidateId: string;
  skillAssessment?: SkillAssessment;
  skillMatches?: SkillMatchData[];
  searchSkills?: string[];
  title?: string;
  compact?: boolean;
  showEvidence?: boolean;
}

interface SkillBarProps {
  skill: SkillWithEvidence;
  isRequired?: boolean;
  matchScore?: number;
  showEvidence?: boolean;
}

const SkillBar: React.FC<SkillBarProps> = ({ 
  skill, 
  isRequired = false, 
  matchScore, 
  showEvidence = false 
}) => {
  const [showDetails, setShowDetails] = useState(false);

  const getConfidenceLevel = (confidence: number): string => {
    if (confidence >= 90) return 'expert';
    if (confidence >= 80) return 'advanced';
    if (confidence >= 70) return 'intermediate';
    if (confidence >= 60) return 'beginner';
    return 'limited';
  };

  const getConfidenceColor = (confidence: number): string => {
    if (confidence >= 90) return '#10B981'; // Green
    if (confidence >= 80) return '#3B82F6'; // Blue
    if (confidence >= 70) return '#F59E0B'; // Yellow
    if (confidence >= 60) return '#EF4444'; // Red
    return '#6B7280'; // Gray
  };

  const getCategoryIcon = (category: string): string => {
    switch (category?.toLowerCase()) {
      case 'technical': return '⚙️';
      case 'soft': return '🤝';
      case 'leadership': return '👑';
      case 'domain': return '🎯';
      default: return '📋';
    }
  };

  return (
    <div className={`skill-bar ${isRequired ? 'required' : ''} ${getConfidenceLevel(skill.confidence)}`}>
      <div className="skill-header" onClick={() => setShowDetails(!showDetails)}>
        <div className="skill-info">
          <span className="category-icon">{getCategoryIcon(skill.category || 'technical')}</span>
          <span className="skill-name">{skill.skill}</span>
          {isRequired && <span className="required-badge">Required</span>}
          {matchScore !== undefined && (
            <span className={`match-score ${matchScore >= 80 ? 'high' : matchScore >= 60 ? 'medium' : 'low'}`}>
              {Math.round(matchScore)}% match
            </span>
          )}
        </div>
        
        <div className="confidence-display">
          <div 
            className="confidence-bar"
            style={{ backgroundColor: getConfidenceColor(skill.confidence) }}
          >
            <div 
              className="confidence-fill"
              style={{ 
                width: `${skill.confidence}%`,
                backgroundColor: getConfidenceColor(skill.confidence)
              }}
            />
          </div>
          <span className="confidence-text">
            {skill.confidence}% <span className="confidence-level">({getConfidenceLevel(skill.confidence)})</span>
          </span>
        </div>
      </div>

      {showDetails && showEvidence && skill.evidence && skill.evidence.length > 0 && (
        <div className="skill-evidence">
          <h5>Evidence:</h5>
          <ul>
            {skill.evidence.map((evidence, index) => (
              <li key={index}>{evidence}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

interface SkillCategoryProps {
  title: string;
  icon: string;
  skills: SkillWithEvidence[];
  requiredSkills?: string[];
  skillMatches?: Record<string, SkillMatchData>;
  showEvidence?: boolean;
  expanded?: boolean;
}

const SkillCategory: React.FC<SkillCategoryProps> = ({
  title,
  icon,
  skills,
  requiredSkills = [],
  skillMatches = {},
  showEvidence = false,
  expanded: defaultExpanded = false
}) => {
  const [expanded, setExpanded] = useState(defaultExpanded);

  if (skills.length === 0) return null;

  const sortedSkills = [...skills].sort((a, b) => {
    // Prioritize required skills, then by confidence
    const aRequired = requiredSkills.includes(a.skill);
    const bRequired = requiredSkills.includes(b.skill);
    
    if (aRequired && !bRequired) return -1;
    if (!aRequired && bRequired) return 1;
    
    return b.confidence - a.confidence;
  });

  return (
    <div className="skill-category">
      <div className="category-header" onClick={() => setExpanded(!expanded)}>
        <span className="category-icon">{icon}</span>
        <h3>{title}</h3>
        <span className="skill-count">({skills.length})</span>
        <span className={`expand-icon ${expanded ? 'expanded' : ''}`}>▼</span>
      </div>
      
      {expanded && (
        <div className="skills-list">
          {sortedSkills.map((skill, index) => (
            <SkillBar
              key={index}
              skill={skill}
              isRequired={requiredSkills.includes(skill.skill)}
              matchScore={skillMatches[skill.skill]?.match_score}
              showEvidence={showEvidence}
            />
          ))}
        </div>
      )}
    </div>
  );
};

export const SkillConfidenceDisplay: React.FC<SkillConfidenceDisplayProps> = ({
  candidateId,
  skillAssessment,
  skillMatches = [],
  searchSkills = [],
  title = "Skill Assessment",
  compact = false,
  showEvidence = true
}) => {
  const [viewMode, setViewMode] = useState<'all' | 'required' | 'high-confidence'>('all');

  if (!skillAssessment) {
    return (
      <div className="skill-confidence-display loading">
        <div className="loading-placeholder">
          <h3>Loading skill assessment...</h3>
        </div>
      </div>
    );
  }

  // Convert skill matches array to lookup object
  const skillMatchLookup: Record<string, SkillMatchData> = {};
  skillMatches.forEach(match => {
    skillMatchLookup[match.skill] = match;
  });

  // Categorize skills
  const categorizedSkills: Record<string, SkillWithEvidence[]> = {
    technical: [],
    soft: [],
    leadership: [],
    domain: []
  };

  Object.values(skillAssessment.skills).forEach(skill => {
    const category = skill.category?.toLowerCase() || 'technical';
    if (categorizedSkills[category]) {
      categorizedSkills[category].push(skill);
    } else {
      categorizedSkills.technical.push(skill);
    }
  });

  // Filter skills based on view mode
  const filterSkills = (skills: SkillWithEvidence[]) => {
    switch (viewMode) {
      case 'required':
        return skills.filter(skill => searchSkills.includes(skill.skill));
      case 'high-confidence':
        return skills.filter(skill => skill.confidence >= 80);
      default:
        return skills;
    }
  };

  const getOverallAssessment = () => {
    const { average_confidence, total_skills } = skillAssessment;
    
    if (average_confidence >= 85) return { level: 'Excellent', color: '#10B981' };
    if (average_confidence >= 75) return { level: 'Strong', color: '#3B82F6' };
    if (average_confidence >= 65) return { level: 'Good', color: '#F59E0B' };
    return { level: 'Developing', color: '#EF4444' };
  };

  const assessment = getOverallAssessment();

  if (compact) {
    return (
      <div className="skill-confidence-display compact">
        <div className="compact-header">
          <h4>Skills Overview</h4>
          <div className="quick-stats">
            <span className="total-skills">{skillAssessment.total_skills} skills</span>
            <span 
              className="avg-confidence"
              style={{ color: assessment.color }}
            >
              {Math.round(skillAssessment.average_confidence)}% avg
            </span>
          </div>
        </div>
        
        <div className="skill-highlights">
          {skillAssessment.high_confidence_skills.slice(0, 6).map((skill, index) => (
            <span key={index} className="skill-tag high-confidence">{skill}</span>
          ))}
          {skillAssessment.high_confidence_skills.length > 6 && (
            <span className="skill-tag more">+{skillAssessment.high_confidence_skills.length - 6}</span>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="skill-confidence-display">
      <div className="display-header">
        <h2>{title}</h2>
        
        <div className="view-controls">
          <button 
            className={`view-btn ${viewMode === 'all' ? 'active' : ''}`}
            onClick={() => setViewMode('all')}
          >
            All Skills
          </button>
          <button 
            className={`view-btn ${viewMode === 'required' ? 'active' : ''}`}
            onClick={() => setViewMode('required')}
            disabled={searchSkills.length === 0}
          >
            Required ({searchSkills.length})
          </button>
          <button 
            className={`view-btn ${viewMode === 'high-confidence' ? 'active' : ''}`}
            onClick={() => setViewMode('high-confidence')}
          >
            High Confidence
          </button>
        </div>
      </div>

      <div className="assessment-summary">
        <div className="summary-card">
          <div className="summary-stat">
            <span className="stat-label">Total Skills</span>
            <span className="stat-value">{skillAssessment.total_skills}</span>
          </div>
          <div className="summary-stat">
            <span className="stat-label">Average Confidence</span>
            <span className="stat-value" style={{ color: assessment.color }}>
              {Math.round(skillAssessment.average_confidence)}%
            </span>
          </div>
          <div className="summary-stat">
            <span className="stat-label">Assessment</span>
            <span className="stat-value" style={{ color: assessment.color }}>
              {assessment.level}
            </span>
          </div>
        </div>

        <div className="confidence-distribution">
          <h4>Confidence Distribution</h4>
          <div className="distribution-bars">
            <div className="dist-bar">
              <span className="dist-label">High (80%+)</span>
              <div className="dist-bar-fill high" style={{ width: `${(skillAssessment.high_confidence_skills.length / skillAssessment.total_skills) * 100}%` }} />
              <span className="dist-count">{skillAssessment.high_confidence_skills.length}</span>
            </div>
            <div className="dist-bar">
              <span className="dist-label">Medium (60-79%)</span>
              <div className="dist-bar-fill medium" style={{ width: `${(skillAssessment.medium_confidence_skills.length / skillAssessment.total_skills) * 100}%` }} />
              <span className="dist-count">{skillAssessment.medium_confidence_skills.length}</span>
            </div>
            <div className="dist-bar">
              <span className="dist-label">Low (&lt;60%)</span>
              <div className="dist-bar-fill low" style={{ width: `${(skillAssessment.low_confidence_skills.length / skillAssessment.total_skills) * 100}%` }} />
              <span className="dist-count">{skillAssessment.low_confidence_skills.length}</span>
            </div>
          </div>
        </div>
      </div>

      <div className="skills-categories">
        <SkillCategory
          title="Technical Skills"
          icon="⚙️"
          skills={filterSkills(categorizedSkills.technical)}
          requiredSkills={searchSkills}
          skillMatches={skillMatchLookup}
          showEvidence={showEvidence}
          expanded={viewMode === 'required' && searchSkills.some(skill => 
            categorizedSkills.technical.some(s => s.skill === skill)
          )}
        />
        
        <SkillCategory
          title="Soft Skills"
          icon="🤝"
          skills={filterSkills(categorizedSkills.soft)}
          requiredSkills={searchSkills}
          skillMatches={skillMatchLookup}
          showEvidence={showEvidence}
        />
        
        <SkillCategory
          title="Leadership Skills"
          icon="👑"
          skills={filterSkills(categorizedSkills.leadership)}
          requiredSkills={searchSkills}
          skillMatches={skillMatchLookup}
          showEvidence={showEvidence}
        />
        
        <SkillCategory
          title="Domain Skills"
          icon="🎯"
          skills={filterSkills(categorizedSkills.domain)}
          requiredSkills={searchSkills}
          skillMatches={skillMatchLookup}
          showEvidence={showEvidence}
        />
      </div>

      {skillMatches.length > 0 && (
        <div className="skill-match-summary">
          <h3>Skill Match Analysis</h3>
          <div className="match-insights">
            <div className="insight">
              <span className="insight-label">Strong Matches:</span>
              <span className="insight-value">
                {skillMatches.filter(m => m.match_score >= 80).length}
              </span>
            </div>
            <div className="insight">
              <span className="insight-label">Partial Matches:</span>
              <span className="insight-value">
                {skillMatches.filter(m => m.match_score >= 60 && m.match_score < 80).length}
              </span>
            </div>
            <div className="insight">
              <span className="insight-label">Skill Gaps:</span>
              <span className="insight-value">
                {skillMatches.filter(m => m.match_score < 60).length}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};