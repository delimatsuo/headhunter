import React, { useState, useEffect } from 'react';
import { JobDescription } from '../../types';
import { apiService } from '../../services/api';

// Sourcing Strategy type from analyzeJob
export interface SourcingStrategy {
  target_companies?: string[];
  target_industries?: string[];
  tech_stack?: { core?: string[]; avoid?: string[] };
  title_variations?: string[];
}

interface JobDescriptionFormProps {
  onSearch: (jobDescription: JobDescription, sourcingStrategy?: SourcingStrategy) => void;
  loading?: boolean;
  loadingStatus?: string;
}

export const JobDescriptionForm: React.FC<JobDescriptionFormProps> = ({
  onSearch,
  loading = false,
  loadingStatus = 'Analyzing...'
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

  const handleAnalyze = async () => {
    if (!formData.description || formData.description.length < 50) return;

    setAnalyzing(true);
    setAnalysis(null);

    try {
      const result = await apiService.analyzeJob(formData.description);
      setAnalysis(result);

      // Auto-populate form
      setFormData(prev => ({
        ...prev,
        title: prev.title || result.job_title,
        required_skills: result.required_skills || [],
        nice_to_have: result.preferred_skills || [],
        min_experience: result.experience_level === 'executive' ? 10 :
          result.experience_level === 'senior' ? 5 :
            result.experience_level === 'mid' ? 3 : 0
      }));
    } catch (error) {
      console.error("Analysis failed", error);
    } finally {
      setAnalyzing(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.description.trim()) {
      alert('Please provide a job description');
      return;
    }

    // Neural Search Strategy:
    // If analysis is missing, run it first (One-Click Search).
    // Then, inject the High-Quality AI Summary into the search query for better Embeddings.

    let currentAnalysis = analysis;
    let enrichedData = { ...formData };

    if (!currentAnalysis && formData.description.length > 50) {
      // Auto-Analyze Logic
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
        ? `JOB TITLE: ${enrichedData.title || currentAnalysis.job_title}\n` +
        `PROFILE: ${currentAnalysis.synthetic_perfect_candidate_profile}`
        : enrichedData.description
    };

    // DEBUG: Trace HyDE profile usage
    console.log('[HyDE Debug] Analysis object:', currentAnalysis);
    console.log('[HyDE Debug] Has synthetic_perfect_candidate_profile?', !!currentAnalysis?.synthetic_perfect_candidate_profile);
    console.log('[HyDE Debug] Final search description:', finalData.description?.substring(0, 500));
    console.log('[Wide Net] Passing sourcing_strategy:', currentAnalysis?.sourcing_strategy);

    // Pass sourcing_strategy to parent for Wide Net search
    onSearch(finalData, currentAnalysis?.sourcing_strategy);
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
            {(!formData.required_skills || formData.required_skills.length === 0) && !analyzing && (
              <span className="no-skills">Analysis needed...</span>
            )}
            {analyzing && <span className="analyzing-status">AI is analyzing requirements...</span>}
          </div>

          <div style={{ marginTop: '10px' }}>
            <button
              type="button"
              onClick={handleAnalyze}
              disabled={analyzing || !formData.description}
              style={{
                background: '#8B5CF6', color: 'white', border: 'none',
                padding: '8px 16px', borderRadius: '6px', cursor: 'pointer'
              }}
            >
              {analyzing ? 'Processing...' : '✨ Analyze Requirements with AI'}
            </button>
          </div>

          {analysis && (
            <div className="analysis-results" style={{ marginTop: '15px', padding: '15px', background: '#F3F4F6', borderRadius: '8px' }}>
              <h4>AI Analysis Summary</h4>
              <p><strong>Role:</strong> {analysis.job_title}</p>
              <p><strong>Level:</strong> {analysis.experience_level}</p>
              <p><strong>Summary:</strong> {analysis.summary}</p>
              {analysis.sourcing_strategy?.target_companies && analysis.sourcing_strategy.target_companies.length > 0 && (
                <div style={{ marginTop: '10px', padding: '10px', background: '#EEF2FF', borderRadius: '6px', border: '1px solid #818CF8' }}>
                  <p style={{ margin: 0, color: '#4F46E5', fontWeight: 'bold' }}>🎯 AI Sourcing Strategy</p>
                  <p style={{ margin: '5px 0', fontSize: '14px' }}>
                    <strong>Target Companies:</strong> {analysis.sourcing_strategy.target_companies.slice(0, 5).join(', ')}
                  </p>
                  {analysis.sourcing_strategy.target_industries && (
                    <p style={{ margin: '5px 0', fontSize: '14px' }}>
                      <strong>Industries:</strong> {analysis.sourcing_strategy.target_industries.join(', ')}
                    </p>
                  )}
                </div>
              )}
            </div>
          )}
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
          disabled={loading}
          style={{ marginTop: '20px' }}
        >
          {loading ? (loadingStatus || 'Analyzing...') : 'Search Candidates'}
        </button>
      </form >
    </div >
  );
};