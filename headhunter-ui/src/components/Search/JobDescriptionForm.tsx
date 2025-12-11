import React, { useState, useEffect } from 'react';
import { JobDescription } from '../../types';

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

  // Simple keyword extraction from description
  const extractSkills = (text: string) => {
    const commonSkills = [
      // Languages
      'java', 'python', 'javascript', 'typescript', 'c#', 'c++', 'go', 'ruby', 'php', 'swift', 'kotlin', 'scala', 'rust',
      // Frontend
      'react', 'angular', 'vue', 'node', 'html', 'css', 'sass', 'less', 'jquery', 'jsp', 'thymeleaf',
      // Backend & Frameworks
      'spring', 'spring boot', 'spring mvc', 'hibernate', 'jpa', 'django', 'flask', 'fastapi', 'express', 'nestjs', '.net', 'asp.net',
      // Database
      'sql', 'nosql', 'mysql', 'postgresql', 'oracle', 'mongodb', 'redis', 'cassandra', 'elasticsearch', 'dynamodb',
      // Cloud & DevOps
      'aws', 'azure', 'gcp', 'cloud', 'docker', 'kubernetes', 'jenkins', 'gitlab ci', 'github actions', 'terraform', 'ansible', 'circleci',
      // Architecture & Concepts
      'rest', 'restful', 'soap', 'graphql', 'microservices', 'distributed systems', 'agile', 'scrum', 'kanban',
      'leadership', 'management', 'communication', 'problem solving', 'teamwork',
      // Tools & Testing
      'git', 'jira', 'junit', 'mockito', 'selenium', 'cypress', 'jest', 'cobertura', 'maven', 'gradle',
      // AI/ML
      'machine learning', 'ai', 'deep learning', 'nlp', 'tensorflow', 'pytorch', 'pandas', 'numpy'
    ];

    const foundSkills = commonSkills.filter(skill =>
      text.toLowerCase().includes(skill.toLowerCase())
    );

    return Array.from(new Set(foundSkills));
  };

  const handleDescriptionChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const text = e.target.value;
    setFormData(prev => ({ ...prev, description: text }));

    // Auto-extract if description is long enough
    if (text.length > 50) {
      const extracted = extractSkills(text);
      setFormData(prev => ({
        ...prev,
        required_skills: extracted
      }));
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.description.trim()) {
      alert('Please provide a job description');
      return;
    }
    // Ensure title is set
    const finalData = {
      ...formData,
      title: formData.title || 'Untitled Position'
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
            {(!formData.required_skills || formData.required_skills.length === 0) && (
              <span className="no-skills">Type description to detect skills...</span>
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

        {showAdvanced && (
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
        )}

        <button
          type="submit"
          className="btn btn-primary btn-large"
          disabled={loading}
          style={{ marginTop: '20px' }}
        >
          {loading ? (loadingStatus || 'Analyzing...') : 'Search Candidates'}
        </button>
      </form>
    </div>
  );
};