import React, { useState, useEffect } from 'react';
import { CandidateProfile } from '../../types';

// MUI Components
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import DialogActions from '@mui/material/DialogActions';
import Button from '@mui/material/Button';
import TextField from '@mui/material/TextField';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import IconButton from '@mui/material/IconButton';
import CloseIcon from '@mui/icons-material/Close';
import Divider from '@mui/material/Divider';
import CircularProgress from '@mui/material/CircularProgress';
import { doc, updateDoc, getFirestore } from 'firebase/firestore';

interface EditCandidateModalProps {
    isOpen: boolean;
    onClose: () => void;
    candidate: CandidateProfile | null;
    onCandidateUpdated?: (candidate: CandidateProfile) => void;
}

export const EditCandidateModal: React.FC<EditCandidateModalProps> = ({
    isOpen,
    onClose,
    candidate,
    onCandidateUpdated
}) => {
    const [formData, setFormData] = useState({
        name: '',
        email: '',
        linkedInUrl: '',
        notes: ''
    });
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string>('');
    const [success, setSuccess] = useState(false);

    // Initialize form data when candidate changes
    useEffect(() => {
        if (candidate) {
            const candidateAny = candidate as any; // Handle dynamic properties
            setFormData({
                name: candidate.name || '',
                email: candidate.personal?.email || candidateAny.email || '',
                linkedInUrl: candidate.linkedin_url || candidate.personal?.linkedin || '',
                notes: candidateAny.notes || candidateAny.recruiter_notes || ''
            });
            setError('');
            setSuccess(false);
        }
    }, [candidate]);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();

        if (!candidate?.candidate_id) {
            setError('No candidate selected');
            return;
        }

        if (!formData.name.trim()) {
            setError('Name is required');
            return;
        }

        setLoading(true);
        setError('');
        setSuccess(false);

        try {
            const db = getFirestore();
            const candidateRef = doc(db, 'candidates', candidate.candidate_id);

            const updateData: any = {
                name: formData.name.trim(),
                updated_at: new Date()
            };

            if (formData.email.trim()) {
                updateData['personal.email'] = formData.email.trim();
            }

            if (formData.linkedInUrl.trim()) {
                updateData.linkedin_url = formData.linkedInUrl.trim();
                updateData['personal.linkedin'] = formData.linkedInUrl.trim();
            }

            if (formData.notes.trim()) {
                updateData.notes = formData.notes.trim();
                updateData.recruiter_notes = formData.notes.trim();
            }

            await updateDoc(candidateRef, updateData);

            setSuccess(true);

            // Notify parent with updated candidate
            const updatedCandidate = {
                ...candidate,
                name: formData.name.trim(),
                linkedin_url: formData.linkedInUrl.trim(),
                personal: {
                    ...candidate.personal,
                    name: formData.name.trim(),
                    email: formData.email.trim(),
                    linkedin: formData.linkedInUrl.trim()
                }
            } as CandidateProfile;

            onCandidateUpdated?.(updatedCandidate);

            // Close after a brief delay to show success
            setTimeout(() => {
                handleClose();
            }, 1000);

        } catch (error: any) {
            console.error('Error updating candidate:', error);
            setError(error.message || 'Failed to update candidate');
        } finally {
            setLoading(false);
        }
    };

    const handleClose = () => {
        setError('');
        setSuccess(false);
        onClose();
    };

    if (!candidate) return null;

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
                <Typography variant="h6" fontWeight="bold">Edit Candidate</Typography>
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

                    {success && (
                        <Alert severity="success" sx={{ mb: 3 }}>
                            ✓ Candidate updated successfully!
                        </Alert>
                    )}

                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
                        <TextField
                            label="Full Name"
                            fullWidth
                            required
                            value={formData.name}
                            onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                            disabled={loading}
                            variant="outlined"
                            autoFocus
                        />

                        <TextField
                            label="Email"
                            type="email"
                            fullWidth
                            value={formData.email}
                            onChange={(e) => setFormData(prev => ({ ...prev, email: e.target.value }))}
                            disabled={loading}
                            variant="outlined"
                            placeholder="candidate@example.com"
                        />

                        <TextField
                            label="LinkedIn URL"
                            fullWidth
                            value={formData.linkedInUrl}
                            onChange={(e) => setFormData(prev => ({ ...prev, linkedInUrl: e.target.value }))}
                            disabled={loading}
                            variant="outlined"
                            placeholder="https://linkedin.com/in/..."
                        />

                        <TextField
                            label="Recruiter Notes"
                            multiline
                            rows={3}
                            fullWidth
                            value={formData.notes}
                            onChange={(e) => setFormData(prev => ({ ...prev, notes: e.target.value }))}
                            disabled={loading}
                            variant="outlined"
                            placeholder="Add context, interview notes, impressions..."
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
                        disabled={loading || success}
                        sx={{ px: 4, minWidth: 120 }}
                    >
                        {loading ? (
                            <CircularProgress size={20} color="inherit" />
                        ) : success ? (
                            '✓ Saved'
                        ) : (
                            'Save Changes'
                        )}
                    </Button>
                </DialogActions>
            </form>
        </Dialog>
    );
};
