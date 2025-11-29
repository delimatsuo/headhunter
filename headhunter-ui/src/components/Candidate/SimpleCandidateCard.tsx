import React from 'react';
import { CandidateProfile } from '../../types';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Stack from '@mui/material/Stack';
import Avatar from '@mui/material/Avatar';
import Divider from '@mui/material/Divider';
import BusinessIcon from '@mui/icons-material/BusinessRounded';
import WorkIcon from '@mui/icons-material/WorkOutlineRounded';

interface SimpleCandidateCardProps {
  candidate: CandidateProfile;
  rank?: number;
}

export const SimpleCandidateCard: React.FC<SimpleCandidateCardProps> = ({
  candidate,
  rank
}) => {
  const formatScore = (score?: number) => {
    if (!score) return '0';
    return Math.round(score * 100);
  };

  const getScoreColor = (score?: number) => {
    if (!score) return 'default';
    if (score >= 0.8) return 'success';
    if (score >= 0.6) return 'warning';
    return 'error';
  };

  return (
    <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column', transition: 'transform 0.2s', '&:hover': { transform: 'translateY(-4px)' } }}>
      <CardContent sx={{ flexGrow: 1, p: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
          <Box sx={{ display: 'flex', gap: 2 }}>
            <Avatar
              sx={{
                width: 48,
                height: 48,
                bgcolor: 'primary.light',
                fontSize: '1.2rem',
                fontWeight: 'bold'
              }}
            >
              {(candidate.name || candidate.personal?.name || 'U')[0].toUpperCase()}
            </Avatar>
            <Box>
              <Typography variant="h6" fontWeight="bold" sx={{ lineHeight: 1.2, mb: 0.5 }}>
                {candidate.name || candidate.personal?.name || 'Unknown Candidate'}
              </Typography>
              <Stack direction="row" spacing={1} alignItems="center" sx={{ color: 'text.secondary' }}>
                <WorkIcon sx={{ fontSize: 16 }} />
                <Typography variant="body2">
                  {candidate.title || candidate.analysis?.current_role?.title || 'Position not specified'}
                </Typography>
              </Stack>
            </Box>
          </Box>

          {candidate.matchScore !== undefined && (
            <Box sx={{ textAlign: 'center' }}>
              <Box sx={{
                position: 'relative',
                display: 'inline-flex',
                bgcolor: `${getScoreColor(candidate.matchScore)}.light`,
                color: `${getScoreColor(candidate.matchScore)}.main`,
                p: 1,
                borderRadius: 2,
                minWidth: 48
              }}>
                <Typography variant="h6" fontWeight="bold" color="inherit">
                  {formatScore(candidate.matchScore)}%
                </Typography>
              </Box>
            </Box>
          )}
        </Box>

        <Box sx={{ mb: 2 }}>
          <Stack direction="row" spacing={1} alignItems="center" sx={{ color: 'text.secondary', mb: 1 }}>
            <BusinessIcon sx={{ fontSize: 16 }} />
            <Typography variant="body2">
              {candidate.company || candidate.analysis?.company_pedigree?.current_company || 'Company not specified'}
            </Typography>
          </Stack>
          <Typography variant="body2" color="text.secondary">
            {candidate.experience || candidate.analysis?.career_trajectory?.years_experience || '0'} years experience
          </Typography>
        </Box>

        {candidate.skills && candidate.skills.length > 0 && (
          <Box sx={{ mb: 2 }}>
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mt: 1 }}>
              {candidate.skills.slice(0, 4).map((skill, index) => (
                <Chip
                  key={index}
                  label={skill}
                  size="small"
                  variant="outlined"
                  sx={{ borderRadius: 1 }}
                />
              ))}
              {candidate.skills.length > 4 && (
                <Chip
                  label={`+${candidate.skills.length - 4}`}
                  size="small"
                  variant="outlined"
                  sx={{ borderRadius: 1, bgcolor: 'action.hover' }}
                />
              )}
            </Stack>
          </Box>
        )}

        {candidate.summary && (
          <Typography variant="body2" color="text.secondary" sx={{
            display: '-webkit-box',
            WebkitLineClamp: 2,
            WebkitBoxOrient: 'vertical',
            overflow: 'hidden'
          }}>
            {candidate.summary}
          </Typography>
        )}
      </CardContent>
    </Card>
  );
};