import React, { useEffect, useState } from 'react';
import { apiService } from '../../services/api';
import { firestoreService } from '../../services/firestore-direct';
import { DashboardStats, CandidateProfile } from '../../types';
import { SimpleCandidateCard } from '../Candidate/SimpleCandidateCard';
import { useAuth } from '../../contexts/AuthContext';
import { AllowedUsersPanel } from '../Admin/AllowedUsersPanel';
import { AddCandidateModal } from '../Upload/AddCandidateModal';

// MUI Components
import Container from '@mui/material/Container';
import Grid from '@mui/material/Grid';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import Alert from '@mui/material/Alert';
import Chip from '@mui/material/Chip';
import Stack from '@mui/material/Stack';
import Paper from '@mui/material/Paper';
import Divider from '@mui/material/Divider';

// Icons
import PeopleIcon from '@mui/icons-material/PeopleRounded';
import BarChartIcon from '@mui/icons-material/BarChartRounded';
import SearchIcon from '@mui/icons-material/SearchRounded';
import TrendingUpIcon from '@mui/icons-material/TrendingUpRounded';
import AddIcon from '@mui/icons-material/AddRounded';
import AssessmentIcon from '@mui/icons-material/AssessmentRounded';

export const Dashboard: React.FC = () => {
  const { user } = useAuth();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [recentCandidates, setRecentCandidates] = useState<CandidateProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>('');
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);

  useEffect(() => {
    if (user) {
      loadDashboardData();
    } else {
      setLoading(false);
    }
  }, [user]);

  const loadDashboardData = async () => {
    setLoading(true);
    setError('');

    try {
      // Try direct Firestore first, fall back to API if needed
      const [statsResult, candidatesResult] = await Promise.all([
        firestoreService.getDashboardStats().catch(() => null),
        firestoreService.getCandidatesDirect(6).catch(() => [])
      ]);

      if (statsResult) {
        setStats(statsResult);
      } else {
        try {
          const apiStats = await apiService.getDashboardStats();
          setStats(apiStats);
        } catch (e) {
          console.error('Failed to load stats from API', e);
        }
      }

      if (candidatesResult && candidatesResult.length > 0) {
        setRecentCandidates(candidatesResult);
      } else {
        // Fallback to API if Firestore direct fails
        try {
          const apiCandidates = await apiService.getCandidates({ limit: 6, offset: 0 });
          if (apiCandidates.success && apiCandidates.data) {
            // Handle both array (legacy) and object with candidates property (new)
            const candidatesData = apiCandidates.data as any;
            setRecentCandidates(Array.isArray(candidatesData) ? candidatesData : (candidatesData.candidates || []));
          }
        } catch {
          // API also failed, show empty state
          setRecentCandidates([]);
        }
      }
    } catch (error: any) {
      setError(error.message || 'Failed to load dashboard data');
    } finally {
      setLoading(false);
    }
  };

  const handleCandidateAdded = (candidate: CandidateProfile) => {
    // Refresh dashboard data
    loadDashboardData();
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '80vh' }}>
        <CircularProgress />
        <Typography sx={{ ml: 2 }}>Loading dashboard...</Typography>
      </Box>
    );
  }

  if (error) {
    return (
      <Container maxWidth="md" sx={{ mt: 4 }}>
        <Alert severity="error" action={
          <Button color="inherit" size="small" onClick={loadDashboardData}>
            Retry
          </Button>
        }>
          {error}
        </Alert>
      </Container>
    );
  }

  const StatCard = ({ icon, value, label, color }: { icon: React.ReactNode, value: string | number, label: string, color: string }) => (
    <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
      <CardContent sx={{ display: 'flex', alignItems: 'center', p: 3 }}>
        <Box sx={{
          p: 1.5,
          borderRadius: 2,
          bgcolor: `${color}15`,
          color: color,
          mr: 2,
          display: 'flex'
        }}>
          {icon}
        </Box>
        <Box>
          <Typography variant="h4" fontWeight="bold" sx={{ color: 'text.primary', lineHeight: 1 }}>
            {value}
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            {label}
          </Typography>
        </Box>
      </CardContent>
    </Card>
  );

  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" component="h1" fontWeight="bold" gutterBottom>
          Dashboard
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Overview of your candidate database and recent activity
        </Typography>
      </Box>

      {/* Stats Grid */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            icon={<PeopleIcon fontSize="large" />}
            value={stats?.totalCandidates || 0}
            label="Total Candidates"
            color="#0F172A" // Primary
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            icon={<AssessmentIcon fontSize="large" />}
            value={`${Math.round((stats?.avgMatchScore || 0) * 100)}%`}
            label="Average Match Score"
            color="#10B981" // Secondary
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            icon={<SearchIcon fontSize="large" />}
            value={stats?.activeSearches || 0}
            label="Active Processing"
            color="#3B82F6" // Blue
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            icon={<TrendingUpIcon fontSize="large" />}
            value={stats?.topSkills?.length || 0}
            label="Top Skills Tracked"
            color="#8B5CF6" // Purple
          />
        </Grid>
      </Grid>

      <Grid container spacing={4}>
        {/* Left Column: Recent Candidates & Skills */}
        <Grid item xs={12} lg={8}>
          {/* Recent Candidates */}
          <Box sx={{ mb: 4 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography variant="h5" fontWeight="bold">
                Recent Candidates
              </Typography>
              <Button variant="text" endIcon={<PeopleIcon />}>
                View All
              </Button>
            </Box>

            {recentCandidates.length === 0 ? (
              <Paper sx={{ p: 4, textAlign: 'center', bgcolor: 'background.default', borderStyle: 'dashed' }}>
                <PeopleIcon sx={{ fontSize: 48, color: 'text.secondary', mb: 2, opacity: 0.5 }} />
                <Typography variant="h6" color="text.secondary">No candidates yet</Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                  Start by adding candidates to build your database
                </Typography>
                <Button variant="contained" startIcon={<AddIcon />} onClick={() => setIsAddModalOpen(true)}>
                  Add Candidate
                </Button>
              </Paper>
            ) : (
              <Grid container spacing={2}>
                {recentCandidates.map((candidate, index) => (
                  <Grid item xs={12} md={6} key={candidate.id || candidate.candidate_id || index}>
                    <SimpleCandidateCard candidate={candidate} />
                  </Grid>
                ))}
              </Grid>
            )}
          </Box>

          {/* Top Skills */}
          {stats?.topSkills && stats.topSkills.length > 0 && (
            <Box>
              <Typography variant="h5" fontWeight="bold" gutterBottom>
                Top Skills in Database
              </Typography>
              <Paper sx={{ p: 3 }}>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                  {stats.topSkills.slice(0, 15).map((item, index) => (
                    <Chip
                      key={index}
                      label={`${item.skill} (${item.count})`}
                      color={index < 5 ? "primary" : "default"}
                      variant={index < 5 ? "filled" : "outlined"}
                      sx={{ fontWeight: 500 }}
                    />
                  ))}
                </Box>
              </Paper>
            </Box>
          )}
        </Grid>

        {/* Right Column: Quick Actions & Admin */}
        <Grid item xs={12} lg={4}>
          <Box sx={{ mb: 4 }}>
            <Typography variant="h5" fontWeight="bold" gutterBottom>
              Quick Actions
            </Typography>
            <Stack spacing={2}>
              <Paper sx={{ p: 3, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Box>
                  <Typography variant="subtitle1" fontWeight="bold">Search Candidates</Typography>
                  <Typography variant="body2" color="text.secondary">Find the perfect match</Typography>
                </Box>
                <Button variant="contained" size="small" startIcon={<SearchIcon />}>
                  Search
                </Button>
              </Paper>

              <Paper sx={{ p: 3, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Box>
                  <Typography variant="subtitle1" fontWeight="bold">Add Candidate</Typography>
                  <Typography variant="body2" color="text.secondary">Upload new resume</Typography>
                </Box>
                <Button
                  variant="outlined"
                  size="small"
                  startIcon={<AddIcon />}
                  onClick={() => setIsAddModalOpen(true)}
                >
                  Add
                </Button>
              </Paper>

              <Paper sx={{ p: 3, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Box>
                  <Typography variant="subtitle1" fontWeight="bold">View Analytics</Typography>
                  <Typography variant="body2" color="text.secondary">Analyze trends</Typography>
                </Box>
                <Button variant="text" size="small" startIcon={<BarChartIcon />}>
                  View
                </Button>
              </Paper>
            </Stack>
          </Box>

          <Divider sx={{ my: 4 }} />

          {/* Admin Panel */}
          <AllowedUsersPanel />
        </Grid>
      </Grid>

      {/* Modals */}
      <AddCandidateModal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        onCandidateAdded={handleCandidateAdded}
      />
    </Container>
  );
};
