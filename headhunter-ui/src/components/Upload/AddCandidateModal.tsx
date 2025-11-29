import React, { useState } from 'react';
import { FileUpload } from './FileUpload';
import { apiService } from '../../services/api';
import { CandidateProfile } from '../../types';

// MUI Components
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import DialogActions from '@mui/material/DialogActions';
import Button from '@mui/material/Button';
import TextField from '@mui/material/TextField';
import FormControl from '@mui/material/FormControl';
import FormLabel from '@mui/material/FormLabel';
import RadioGroup from '@mui/material/RadioGroup';
import FormControlLabel from '@mui/material/FormControlLabel';
import Radio from '@mui/material/Radio';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import IconButton from '@mui/material/IconButton';
import CloseIcon from '@mui/icons-material/Close';
import Divider from '@mui/material/Divider';

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
  const [candidateId] = useState(`cand_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`);
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
        candidate_id: candidateId, // Pass the pre-generated ID
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

  return (
    <Dialog
      open={isOpen}
      onClose={handleClose}
      maxWidth="md"
      fullWidth
      PaperProps={{
        sx: { borderRadius: 3 }
      }}
    >
      <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', pb: 1 }}>
        <Typography variant="h6" fontWeight="bold">Add New Candidate</Typography>
        <IconButton onClick={handleClose} size="small">
          <CloseIcon />
        </IconButton>
      </DialogTitle>

      <Divider />

      <form onSubmit={handleSubmit}>
        <DialogContent sx={{ py: 3 }}>
          {error && (
            <Alert severity="error" sx={{ mb: 3 }}>
              {error}
            </Alert>
          )}

          <Box sx={{ mb: 4 }}>
            <Typography variant="subtitle2" color="primary" fontWeight="bold" gutterBottom textTransform="uppercase" sx={{ fontSize: '0.75rem', letterSpacing: 1 }}>
              Candidate Information
            </Typography>
            <Box sx={{ display: 'flex', gap: 2, flexDirection: { xs: 'column', sm: 'row' } }}>
              <TextField
                autoFocus
                label="Full Name"
                fullWidth
                required
                value={formData.name}
                onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                disabled={loading}
                variant="outlined"
              />
              <TextField
                label="Email"
                type="email"
                fullWidth
                value={formData.email}
                onChange={(e) => setFormData(prev => ({ ...prev, email: e.target.value }))}
                disabled={loading}
                variant="outlined"
              />
            </Box>
          </Box>

          <Box sx={{ mb: 4 }}>
            <Typography variant="subtitle2" color="primary" fontWeight="bold" gutterBottom textTransform="uppercase" sx={{ fontSize: '0.75rem', letterSpacing: 1 }}>
              Resume
            </Typography>

            <FormControl component="fieldset" sx={{ mb: 2, width: '100%' }}>
              <RadioGroup
                row
                value={uploadMethod}
                onChange={(e) => setUploadMethod(e.target.value as 'file' | 'text')}
              >
                <FormControlLabel value="file" control={<Radio />} label="Upload resume file" />
                <FormControlLabel value="text" control={<Radio />} label="Paste resume text" />
              </RadioGroup>
            </FormControl>

            {uploadMethod === 'file' ? (
              <Box sx={{ border: '1px dashed', borderColor: 'divider', borderRadius: 2, p: 3, bgcolor: 'background.default' }}>
                <FileUpload
                  candidateId={candidateId}
                  onUploadComplete={handleUploadComplete}
                  onUploadError={handleUploadError}
                  className="candidate-upload"
                />
              </Box>
            ) : (
              <TextField
                label="Resume Text"
                multiline
                rows={8}
                fullWidth
                value={formData.resumeText}
                onChange={(e) => setFormData(prev => ({ ...prev, resumeText: e.target.value }))}
                placeholder="Paste the candidate's resume text here..."
                disabled={loading}
                variant="outlined"
              />
            )}
          </Box>

          <Box>
            <Typography variant="subtitle2" color="primary" fontWeight="bold" gutterBottom textTransform="uppercase" sx={{ fontSize: '0.75rem', letterSpacing: 1 }}>
              Recruiter Notes (Optional)
            </Typography>
            <TextField
              label="Comments"
              multiline
              rows={4}
              fullWidth
              value={formData.recruiterComments}
              onChange={(e) => setFormData(prev => ({ ...prev, recruiterComments: e.target.value }))}
              placeholder="Add any recruiter insights, interview notes, or observations..."
              disabled={loading}
              variant="outlined"
            />
          </Box>
        </DialogContent>

        <Divider />

        <DialogActions sx={{ px: 3, py: 2 }}>
          <Button onClick={handleClose} color="inherit" disabled={loading}>
            Cancel
          </Button>
          <Button
            type="submit"
            variant="contained"
            disabled={loading}
            sx={{ px: 4 }}
          >
            {loading ? 'Adding...' : 'Add Candidate'}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
};