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
    resumeText: '',
    recruiterNotes: ''
  });
  const [resumeUrl, setResumeUrl] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>('');
  const [uploadMethod, setUploadMethod] = useState<'file' | 'text'>('file');
  const [uploadComplete, setUploadComplete] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (uploadMethod === 'file' && !resumeUrl) {
      setError('Please upload a resume file');
      return;
    }

    if (uploadMethod === 'text' && !formData.resumeText.trim()) {
      setError('Please enter resume text');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const candidateData = {
        candidate_id: candidateId,
        name: 'Processing...', // Will be extracted by AI
        resume_text: uploadMethod === 'text' ? formData.resumeText : undefined,
        resume_url: uploadMethod === 'file' ? resumeUrl : undefined,
        notes: formData.recruiterNotes || undefined
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
    setFormData({ resumeText: '', recruiterNotes: '' });
    setResumeUrl('');
    setError('');
    setLoading(false);
    setUploadMethod('file');
    setUploadComplete(false);
    onClose();
  };

  const handleUploadComplete = (fileUrl: string) => {
    setResumeUrl(fileUrl);
    setUploadComplete(true);
    setError('');
  };

  const handleUploadError = (error: string) => {
    setError(error);
    setUploadComplete(false);
  };

  return (
    <Dialog
      open={isOpen}
      onClose={handleClose}
      maxWidth="sm"
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

          <Box sx={{ mb: 3 }}>
            <Alert severity="info" sx={{ mb: 2 }}>
              <Typography variant="body2">
                <strong>Just upload a resume!</strong> Our AI will automatically extract the candidate's name, email, LinkedIn, and skills.
              </Typography>
            </Alert>

            <FormControl component="fieldset" sx={{ mb: 2, width: '100%' }}>
              <RadioGroup
                row
                value={uploadMethod}
                onChange={(e) => {
                  setUploadMethod(e.target.value as 'file' | 'text');
                  setUploadComplete(false);
                  setResumeUrl('');
                }}
              >
                <FormControlLabel value="file" control={<Radio />} label="Upload file" />
                <FormControlLabel value="text" control={<Radio />} label="Paste text" />
              </RadioGroup>
            </FormControl>

            {uploadMethod === 'file' ? (
              <Box sx={{
                border: uploadComplete ? '2px solid #10B981' : '1px dashed',
                borderColor: uploadComplete ? '#10B981' : 'divider',
                borderRadius: 2,
                p: 2,
                bgcolor: uploadComplete ? 'rgba(16, 185, 129, 0.05)' : 'background.default'
              }}>
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
                rows={10}
                fullWidth
                value={formData.resumeText}
                onChange={(e) => setFormData(prev => ({ ...prev, resumeText: e.target.value }))}
                placeholder="Paste the candidate's resume or LinkedIn profile text here..."
                disabled={loading}
                variant="outlined"
              />
            )}
          </Box>

          <Box>
            <Typography variant="subtitle2" color="text.secondary" gutterBottom sx={{ fontSize: '0.75rem' }}>
              Recruiter Notes (Optional)
            </Typography>
            <TextField
              multiline
              rows={2}
              fullWidth
              value={formData.recruiterNotes}
              onChange={(e) => setFormData(prev => ({ ...prev, recruiterNotes: e.target.value }))}
              placeholder="Add context: where you found them, initial impressions..."
              disabled={loading}
              variant="outlined"
              size="small"
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
            disabled={loading || (uploadMethod === 'file' && !uploadComplete)}
            sx={{ px: 4 }}
          >
            {loading ? 'Processing...' : 'Add Candidate'}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
};