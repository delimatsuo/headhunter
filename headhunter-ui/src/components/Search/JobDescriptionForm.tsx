import React, { useState } from 'react';
import { JobDescription } from '../../types';

interface JobDescriptionFormProps {
  onSearch: (jobDescription: JobDescription) => void;
  loading?: boolean;
}

export const JobDescriptionForm: React.FC<JobDescriptionFormProps> = ({ 
  onSearch, 
  loading = false 
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

  const [skillInput, setSkillInput] = useState('');
  const [niceToHaveInput, setNiceToHaveInput] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!formData.title.trim() || !formData.description.trim()) {
      alert('Please fill in at least the job title and description');
      return;
    }

    onSearch(formData);
  };

  const addSkill = (skillType: 'required_skills' | 'nice_to_have') => {
    const input = skillType === 'required_skills' ? skillInput : niceToHaveInput;
    const setInput = skillType === 'required_skills' ? setSkillInput : setNiceToHaveInput;
    
    if (input.trim() && !formData[skillType]?.includes(input.trim())) {
      setFormData(prev => ({
        ...prev,
        [skillType]: [...(prev[skillType] || []), input.trim()]
      }));
      setInput('');
    }
  };

  const removeSkill = (skillType: 'required_skills' | 'nice_to_have', index: number) => {
    setFormData(prev => ({
      ...prev,
      [skillType]: prev[skillType]?.filter((_, i) => i !== index) || []
    }));
  };

  const handleKeyPress = (e: React.KeyboardEvent, skillType: 'required_skills' | 'nice_to_have') => {
    if (e.key === 'Enter') {
      e.preventDefault();
      addSkill(skillType);
    }
  };

  return (
    <div className="job-description-form">
      <div className="form-header">
        <h2>Find Perfect Candidates</h2>
        <p>Describe the role and we'll find the best matching candidates</p>
      </div>

      <form onSubmit={handleSubmit} className="search-form">
        <div className="form-row">
          <div className="form-group">
            <label htmlFor="title">Job Title *</label>
            <input
              type="text"
              id="title"
              value={formData.title}
              onChange={(e) => setFormData(prev => ({ ...prev, title: e.target.value }))}
              placeholder="e.g., Senior Software Engineer"
              disabled={loading}
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="company">Company</label>
            <input
              type="text"
              id="company"
              value={formData.company}
              onChange={(e) => setFormData(prev => ({ ...prev, company: e.target.value }))}
              placeholder="e.g., TechCorp Inc."
              disabled={loading}
            />
          </div>
        </div>

        <div className="form-group">
          <label htmlFor="description">Job Description *</label>
          <textarea
            id="description"
            value={formData.description}
            onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
            placeholder="Paste the full job description here..."
            rows={6}
            disabled={loading}
            required
          />
        </div>

        <div className="form-row">
          <div className="form-group">
            <label>Required Skills</label>
            <div className="skill-input">
              <input
                type="text"
                value={skillInput}
                onChange={(e) => setSkillInput(e.target.value)}
                onKeyPress={(e) => handleKeyPress(e, 'required_skills')}
                placeholder="Add required skill"
                disabled={loading}
              />
              <button
                type="button"
                onClick={() => addSkill('required_skills')}
                disabled={loading || !skillInput.trim()}
                className="btn btn-small"
              >
                Add
              </button>
            </div>
            <div className="skill-tags">
              {formData.required_skills?.map((skill, index) => (
                <span key={index} className="skill-tag required">
                  {skill}
                  <button
                    type="button"
                    onClick={() => removeSkill('required_skills', index)}
                    disabled={loading}
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
          </div>

          <div className="form-group">
            <label>Nice to Have</label>
            <div className="skill-input">
              <input
                type="text"
                value={niceToHaveInput}
                onChange={(e) => setNiceToHaveInput(e.target.value)}
                onKeyPress={(e) => handleKeyPress(e, 'nice_to_have')}
                placeholder="Add nice-to-have skill"
                disabled={loading}
              />
              <button
                type="button"
                onClick={() => addSkill('nice_to_have')}
                disabled={loading || !niceToHaveInput.trim()}
                className="btn btn-small"
              >
                Add
              </button>
            </div>
            <div className="skill-tags">
              {formData.nice_to_have?.map((skill, index) => (
                <span key={index} className="skill-tag nice-to-have">
                  {skill}
                  <button
                    type="button"
                    onClick={() => removeSkill('nice_to_have', index)}
                    disabled={loading}
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
          </div>
        </div>

        <div className="form-row">
          <div className="form-group">
            <label htmlFor="minExperience">Min Experience (years)</label>
            <select
              id="minExperience"
              value={formData.min_experience}
              onChange={(e) => setFormData(prev => ({ 
                ...prev, 
                min_experience: parseInt(e.target.value) 
              }))}
              disabled={loading}
            >
              {[...Array(16)].map((_, i) => (
                <option key={i} value={i}>{i} years</option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="maxExperience">Max Experience (years)</label>
            <select
              id="maxExperience"
              value={formData.max_experience}
              onChange={(e) => setFormData(prev => ({ 
                ...prev, 
                max_experience: parseInt(e.target.value) 
              }))}
              disabled={loading}
            >
              {[...Array(21)].map((_, i) => (
                <option key={i} value={i}>{i === 20 ? '20+' : i} years</option>
              ))}
            </select>
          </div>
        </div>

        <div className="form-group">
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={formData.leadership_required || false}
              onChange={(e) => setFormData(prev => ({ 
                ...prev, 
                leadership_required: e.target.checked 
              }))}
              disabled={loading}
            />
            Leadership experience required
          </label>
        </div>

        <button
          type="submit"
          className="btn btn-primary btn-large"
          disabled={loading}
        >
          {loading ? 'Searching...' : 'Search Candidates'}
        </button>
      </form>
    </div>
  );
};