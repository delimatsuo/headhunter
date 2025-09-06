import React, { useState } from 'react';
import { JobDescription } from '../types';
import './JobDescriptionForm.css';

interface JobDescriptionFormProps {
  onSubmit: (jobDesc: JobDescription) => void;
  isLoading: boolean;
}

const JobDescriptionForm: React.FC<JobDescriptionFormProps> = ({ onSubmit, isLoading }) => {
  const [formData, setFormData] = useState<JobDescription>({
    title: '',
    company: '',
    description: '',
    min_experience: undefined,
    max_experience: undefined,
    leadership_required: false
  });

  const [skills, setSkills] = useState('');
  const [niceToHave, setNiceToHave] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    const jobDesc: JobDescription = {
      ...formData,
      required_skills: skills ? skills.split(',').map(s => s.trim()).filter(Boolean) : undefined,
      nice_to_have: niceToHave ? niceToHave.split(',').map(s => s.trim()).filter(Boolean) : undefined
    };
    
    onSubmit(jobDesc);
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value, type } = e.target;
    
    if (type === 'checkbox') {
      const target = e.target as HTMLInputElement;
      setFormData(prev => ({ ...prev, [name]: target.checked }));
    } else if (type === 'number') {
      setFormData(prev => ({ ...prev, [name]: value ? parseInt(value) : undefined }));
    } else {
      setFormData(prev => ({ ...prev, [name]: value }));
    }
  };

  // Sample job descriptions for quick testing
  const loadSampleJob = (type: string) => {
    const samples: { [key: string]: JobDescription } = {
      ml: {
        title: 'Senior Machine Learning Engineer',
        company: 'TechCorp AI',
        description: `We're looking for a Senior Machine Learning Engineer to join our AI team.
You'll be working on cutting-edge ML models and leading technical initiatives.

Requirements:
- 7+ years of experience in machine learning
- Strong Python and TensorFlow/PyTorch skills
- Experience with distributed systems and Kubernetes
- Leadership experience with 5+ person teams
- PhD in Computer Science or related field preferred
- Experience at top-tier tech companies`,
        min_experience: 7,
        leadership_required: true
      },
      frontend: {
        title: 'Frontend React Developer',
        company: 'StartupCo',
        description: `Fast-growing startup seeking a Frontend Developer with React expertise.
Build amazing user experiences in a fast-paced environment.

Requirements:
- 3-5 years of frontend development experience
- Expert in React, TypeScript, and modern JavaScript
- Experience with Node.js and full-stack development
- Startup experience preferred
- Strong problem-solving skills`,
        min_experience: 3,
        max_experience: 5,
        leadership_required: false
      },
      platform: {
        title: 'Principal Platform Engineer',
        company: 'CloudScale Inc',
        description: `Seeking a Principal Engineer to architect our next-gen platform.
Lead the design and implementation of distributed systems at scale.

Requirements:
- 10+ years building distributed systems
- Expert in Kubernetes, Docker, and cloud infrastructure
- Strong Go or Java programming skills
- Experience with AWS/GCP at scale
- Track record of leading 10+ person engineering teams
- Experience at FAANG or equivalent companies`,
        min_experience: 10,
        leadership_required: true
      }
    };

    const sample = samples[type];
    if (sample) {
      setFormData(sample);
      setSkills('');
      setNiceToHave('');
    }
  };

  return (
    <div className="job-form-container">
      <h2>Job Description</h2>
      
      <div className="sample-buttons">
        <span>Quick samples:</span>
        <button type="button" onClick={() => loadSampleJob('ml')} className="sample-btn">
          ML Engineer
        </button>
        <button type="button" onClick={() => loadSampleJob('frontend')} className="sample-btn">
          Frontend Dev
        </button>
        <button type="button" onClick={() => loadSampleJob('platform')} className="sample-btn">
          Platform Eng
        </button>
      </div>

      <form onSubmit={handleSubmit} className="job-form">
        <div className="form-row">
          <div className="form-group">
            <label htmlFor="title">Job Title *</label>
            <input
              type="text"
              id="title"
              name="title"
              value={formData.title}
              onChange={handleChange}
              required
              placeholder="e.g., Senior Software Engineer"
            />
          </div>
          
          <div className="form-group">
            <label htmlFor="company">Company *</label>
            <input
              type="text"
              id="company"
              name="company"
              value={formData.company}
              onChange={handleChange}
              required
              placeholder="e.g., TechCorp"
            />
          </div>
        </div>

        <div className="form-group">
          <label htmlFor="description">Job Description *</label>
          <textarea
            id="description"
            name="description"
            value={formData.description}
            onChange={handleChange}
            required
            rows={10}
            placeholder="Paste the full job description here..."
          />
        </div>

        <div className="form-row">
          <div className="form-group">
            <label htmlFor="skills">Required Skills</label>
            <input
              type="text"
              id="skills"
              value={skills}
              onChange={(e) => setSkills(e.target.value)}
              placeholder="Python, React, AWS (comma-separated)"
            />
          </div>
          
          <div className="form-group">
            <label htmlFor="niceToHave">Nice to Have</label>
            <input
              type="text"
              id="niceToHave"
              value={niceToHave}
              onChange={(e) => setNiceToHave(e.target.value)}
              placeholder="Docker, Kubernetes (comma-separated)"
            />
          </div>
        </div>

        <div className="form-row">
          <div className="form-group">
            <label htmlFor="min_experience">Min Experience (years)</label>
            <input
              type="number"
              id="min_experience"
              name="min_experience"
              value={formData.min_experience || ''}
              onChange={handleChange}
              min="0"
              max="30"
            />
          </div>
          
          <div className="form-group">
            <label htmlFor="max_experience">Max Experience (years)</label>
            <input
              type="number"
              id="max_experience"
              name="max_experience"
              value={formData.max_experience || ''}
              onChange={handleChange}
              min="0"
              max="30"
            />
          </div>
        </div>

        <div className="form-group checkbox-group">
          <label>
            <input
              type="checkbox"
              name="leadership_required"
              checked={formData.leadership_required}
              onChange={handleChange}
            />
            Leadership experience required
          </label>
        </div>

        <button type="submit" className="submit-btn" disabled={isLoading}>
          {isLoading ? 'Searching...' : 'Search Candidates'}
        </button>
      </form>
    </div>
  );
};

export default JobDescriptionForm;