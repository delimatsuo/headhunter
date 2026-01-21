import React, { useState } from 'react';
import { JobDescription } from '../../types';
import { apiService } from '../../services/api';

// Sourcing Strategy type from analyzeJob
export interface SourcingStrategy {
  target_companies?: string[];
  target_industries?: string[];
  tech_stack?: { core?: string[]; avoid?: string[] };
  title_variations?: string[];
}

// Analysis result type for passing to parent
export interface JobAnalysis {
  job_title: string;
  experience_level: string;
  summary: string;
  required_skills?: string[];
  preferred_skills?: string[];
  sourcing_strategy?: SourcingStrategy;
  synthetic_perfect_candidate_profile?: string;
}

interface JobDescriptionFormProps {
  onSearch: (jobDescription: JobDescription, sourcingStrategy?: SourcingStrategy, analysis?: JobAnalysis) => void;
  loading?: boolean;
  loadingPhase?: 'analyzing' | 'searching' | null;
}

export const JobDescriptionForm: React.FC<JobDescriptionFormProps> = ({
  onSearch,
  loading = false,
  loadingPhase = null
}) => {
  const [formData, setFormData] = useState<JobDescription>({
    title: '',
    company: '',
    description: '',
    required_skills: [],
    nice_to_have: [],
    min_experience: 0,
    max_experience: 15,
    leadership_required: false,
  });

  const [showAdvanced, setShowAdvanced] = useState(false);
  const [skillInput, setSkillInput] = useState('');

  const [analyzing, setAnalyzing] = useState(false);
  const [analysis, setAnalysis] = useState<any>(null);

  const handleDescriptionChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const text = e.target.value;
    setFormData(prev => ({ ...prev, description: text }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.description.trim()) {
      alert('Please provide a job description');
      return;
    }

    // One-Click Search Flow:
    // 1. Analyze (if not already done) -> shows "Analyzing requirements..."
    // 2. Search with enriched data -> shows "Searching candidates..."

    let currentAnalysis = analysis;
    let enrichedData = { ...formData };

    if (!currentAnalysis && formData.description.length > 50) {
      // Auto-Analyze Logic - parent will show "analyzing" phase
      setAnalyzing(true);
      try {
        currentAnalysis = await apiService.analyzeJob(formData.description);
        setAnalysis(currentAnalysis);

        // Apply analysis to data
        enrichedData = {
          ...enrichedData,
          title: enrichedData.title || currentAnalysis.job_title,
          required_skills: currentAnalysis.required_skills || [],
          nice_to_have: currentAnalysis.preferred_skills || [],
          min_experience: currentAnalysis.experience_level === 'executive' ? 10 :
            currentAnalysis.experience_level === 'senior' ? 5 :
              currentAnalysis.experience_level === 'mid' ? 3 : 0,
          seniority: currentAnalysis.experience_level // explicit seniority signal
        };

        // Update UI form state too so user sees it
        setFormData(enrichedData);

      } catch (err) {
        console.error("Auto-analysis failed, falling back to raw search", err);
      } finally {
        setAnalyzing(false);
      }
    }

    // Ensure title is set
    const finalData = {
      ...enrichedData,
      title: enrichedData.title || 'Untitled Position',
      // COGNITIVE ANCHOR: Use the 4 Structured Dimensions for the Embedding
      description: currentAnalysis?.synthetic_perfect_candidate_profile
        // HyDE STRATEGY: Use the AI-generated "Perfect Candidate Profile" as the anchor.
        // This automatically handles the balance of Strategy vs. Tech for each role type.
        // TECH STACK FIX: Include required_skills in embedding query for better vector matching
        ? `JOB TITLE: ${enrichedData.title || currentAnalysis.job_title}\n` +
          `REQUIRED SKILLS: ${(currentAnalysis.required_skills || []).slice(0, 10).join(', ')}\n` +
          `PROFILE: ${currentAnalysis.synthetic_perfect_candidate_profile}`
        : enrichedData.description
    };

    // DEBUG: Trace HyDE profile usage
    console.log('[HyDE Debug] Analysis object:', currentAnalysis);
    console.log('[HyDE Debug] Has synthetic_perfect_candidate_profile?', !!currentAnalysis?.synthetic_perfect_candidate_profile);
    console.log('[HyDE Debug] Final search description:', finalData.description?.substring(0, 500));
    console.log('[Wide Net] Passing sourcing_strategy:', currentAnalysis?.sourcing_strategy);

    // Pass sourcing_strategy AND analysis to parent for display in results
    onSearch(finalData, currentAnalysis?.sourcing_strategy, currentAnalysis as JobAnalysis);
  };

  const addSkill = () => {
    if (skillInput.trim() && !formData.required_skills?.includes(skillInput.trim())) {
      setFormData(prev => ({
        ...prev,
        required_skills: [...(prev.required_skills || []), skillInput.trim()]
      }));
      setSkillInput('');
    }
  };

  const removeSkill = (index: number) => {
    setFormData(prev => ({
      ...prev,
      required_skills: prev.required_skills?.filter((_, i) => i !== index) || []
    }));
  };

  return (
    <div className="job-description-form">
      <div className="form-header">
        <h2>Find Perfect Candidates</h2>
        <p>Paste your job description below. We'll extract the requirements automatically.</p>
      </div>

      <form onSubmit={handleSubmit} className="search-form">
        <div className="form-group">
          <label htmlFor="description">Job Description *</label>
          <textarea
            id="description"
            value={formData.description}
            onChange={handleDescriptionChange}
            placeholder="Paste the full job description here..."
            rows={10}
            disabled={loading}
            required
            className="description-input"
          />
        </div>

        <div className="extracted-skills-preview">
          <label>Detected Skills:</label>
          <div className="skill-tags">
            {formData.required_skills?.map((skill, index) => (
              <span key={index} className="skill-tag required">
                {skill}
                <button type="button" onClick={() => removeSkill(index)}>×</button>
              </span>
            ))}
            {(!formData.required_skills || formData.required_skills.length === 0) && !analyzing && !loading && (
              <span className="no-skills">Skills will be detected when you search</span>
            )}
            {(analyzing || loadingPhase === 'analyzing') && (
              <span className="analyzing-status">AI is analyzing requirements...</span>
            )}
          </div>
        </div>

        <button
          type="button"
          className="btn btn-text"
          onClick={() => setShowAdvanced(!showAdvanced)}
        >
          {showAdvanced ? 'Hide Advanced Options' : 'Show Advanced Options'}
        </button>

        {
          showAdvanced && (
            <div className="advanced-options">
              <div className="form-group">
                <label>Add Manual Skill</label>
                <div className="skill-input">
                  <input
                    type="text"
                    value={skillInput}
                    onChange={(e) => setSkillInput(e.target.value)}
                    placeholder="Add skill"
                  />
                  <button type="button" onClick={addSkill} className="btn btn-small">Add</button>
                </div>
              </div>
              {/* Add other advanced fields here if needed */}
            </div>
          )
        }

        <button
          type="submit"
          className="btn btn-primary btn-large"
          disabled={loading || analyzing}
          style={{ marginTop: '20px' }}
        >
          {analyzing || loadingPhase === 'analyzing'
            ? '🔍 Analyzing requirements...'
            : loadingPhase === 'searching'
              ? '⚡ Searching candidates...'
              : '🔍 Search Candidates'}
        </button>
      </form >
    </div >
  );
};