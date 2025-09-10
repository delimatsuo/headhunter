import React, { useState } from 'react';
import { FileUpload } from './FileUpload';
import { apiService } from '../../services/api';
import { CandidateProfile } from '../../types';

interface AddCandidateModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCandidateAdded?: (candidate: CandidateProfile) => void;
}

export const AddCandidateModal: React.FC<AddCandidateModalProps> = ({
  isOpen,
  onClose,
  onCandidateAdded
}) => {
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    resumeText: '',
    recruiterComments: ''
  });
  const [resumeUrl, setResumeUrl] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>('');
  const [uploadMethod, setUploadMethod] = useState<'file' | 'text'>('file');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!formData.name.trim()) {
      setError('Candidate name is required');
      return;
    }

    if (uploadMethod === 'file' && !resumeUrl) {
      setError('Please upload a resume file or switch to text input');
      return;
    }

    if (uploadMethod === 'text' && !formData.resumeText.trim()) {
      setError('Please enter resume text or upload a file');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const candidateData = {
        name: formData.name,
        email: formData.email || undefined,
        resumeText: uploadMethod === 'text' ? formData.resumeText : undefined,
        resumeUrl: uploadMethod === 'file' ? resumeUrl : undefined,
        recruiterComments: formData.recruiterComments || undefined
      };

      const result = await apiService.createCandidate(candidateData);

      if (result.success && result.data) {
        onCandidateAdded?.(result.data);
        handleClose();
      } else {
        setError(result.error || 'Failed to create candidate');
      }
    } catch (error: any) {
      setError(error.message || 'Failed to create candidate');
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    setFormData({ name: '', email: '', resumeText: '', recruiterComments: '' });
    setResumeUrl('');
    setError('');
    setLoading(false);
    setUploadMethod('file');
    onClose();
  };

  const handleUploadComplete = (fileUrl: string) => {
    setResumeUrl(fileUrl);
    setError('');
  };

  const handleUploadError = (error: string) => {
    setError(error);
  };

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={handleClose}>
      <div className="modal-content large" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Add New Candidate</h2>
          <button className="modal-close" onClick={handleClose}>
            ×
          </button>
        </div>

        <form onSubmit={handleSubmit} className="add-candidate-form">
          {error && (
            <div className="error-message">
              {error}
            </div>
          )}

          <div className="form-section">
            <h3>Candidate Information</h3>
            
            <div className="form-row">
              <div className="form-group">
                <label htmlFor="name">Full Name *</label>
                <input
                  type="text"
                  id="name"
                  value={formData.name}
                  onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                  placeholder="Enter candidate's full name"
                  disabled={loading}
                  required
                />
              </div>

              <div className="form-group">
                <label htmlFor="email">Email</label>
                <input
                  type="email"
                  id="email"
                  value={formData.email}
                  onChange={(e) => setFormData(prev => ({ ...prev, email: e.target.value }))}
                  placeholder="candidate@example.com"
                  disabled={loading}
                />
              </div>
            </div>
          </div>

          <div className="form-section">
            <h3>Resume</h3>
            
            <div className="upload-method-selector">
              <label className="radio-label">
                <input
                  type="radio"
                  name="uploadMethod"
                  value="file"
                  checked={uploadMethod === 'file'}
                  onChange={(e) => setUploadMethod(e.target.value as 'file')}
                  disabled={loading}
                />
                Upload resume file
              </label>
              <label className="radio-label">
                <input
                  type="radio"
                  name="uploadMethod"
                  value="text"
                  checked={uploadMethod === 'text'}
                  onChange={(e) => setUploadMethod(e.target.value as 'text')}
                  disabled={loading}
                />
                Paste resume text
              </label>
            </div>

            {uploadMethod === 'file' && (
              <FileUpload
                onUploadComplete={handleUploadComplete}
                onUploadError={handleUploadError}
                className="candidate-upload"
              />
            )}

            {uploadMethod === 'text' && (
              <div className="form-group">
                <label htmlFor="resumeText">Resume Text</label>
                <textarea
                  id="resumeText"
                  value={formData.resumeText}
                  onChange={(e) => setFormData(prev => ({ ...prev, resumeText: e.target.value }))}
                  placeholder="Paste the candidate's resume text here..."
                  rows={8}
                  disabled={loading}
                />
              </div>
            )}
          </div>

          <div className="form-section">
            <h3>Recruiter Notes (Optional)</h3>
            <div className="form-group">
              <label htmlFor="recruiterComments">Comments</label>
              <textarea
                id="recruiterComments"
                value={formData.recruiterComments}
                onChange={(e) => setFormData(prev => ({ ...prev, recruiterComments: e.target.value }))}
                placeholder="Add any recruiter insights, interview notes, or observations..."
                rows={4}
                disabled={loading}
              />
            </div>
          </div>

          <div className="form-actions">
            <button
              type="button"
              onClick={handleClose}
              className="btn btn-secondary"
              disabled={loading}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={loading}
            >
              {loading ? 'Processing...' : 'Add Candidate'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};