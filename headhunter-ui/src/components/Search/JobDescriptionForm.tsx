import React, { useState, useEffect } from 'react';
import { JobDescription } from '../../types';
import { apiService } from '../../services/api';

interface JobDescriptionFormProps {
  onSearch: (jobDescription: JobDescription) => void;
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
      description: currentAnalysis?.neural_dimensions
        ? `ROLE: ${currentAnalysis.neural_dimensions.role_identity}\n` +
        `DOMAIN: ${currentAnalysis.neural_dimensions.domain_expertise}\n` +
        `SCOPE: ${currentAnalysis.neural_dimensions.leadership_level}\n` +
        `TECH: ${currentAnalysis.neural_dimensions.technical_env}\n\n` +
        `CONTEXT: ${enrichedData.description}`
        : enrichedData.description
    };

    onSearch(finalData);
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

        <div className="form-row">
          <div className="form-group">
            <label htmlFor="title">Job Title (Optional)</label>
            <input
              type="text"
              id="title"
              value={formData.title}
              onChange={(e) => setFormData(prev => ({ ...prev, title: e.target.value }))}
              placeholder="e.g., Senior Software Engineer"
              disabled={loading}
            />
          </div>
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
              <p><strong>Key Focus:</strong> {(analysis.key_responsibilities || []).slice(0, 3).join(', ')}</p>
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