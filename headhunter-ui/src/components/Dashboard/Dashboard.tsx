import React, { useEffect, useState } from 'react';
import { apiService } from '../../services/api';
import { firestoreService } from '../../services/firestore-direct';
import { DashboardStats, CandidateProfile, JobDescription, SearchResponse } from '../../types';
import { SkillAwareCandidateCard } from '../Candidate/SkillAwareCandidateCard';
import { useAuth } from '../../contexts/AuthContext';
import { AllowedUsersPanel } from '../Admin/AllowedUsersPanel';
import { AddCandidateModal } from '../Upload/AddCandidateModal';
import { JobDescriptionForm } from '../Search/JobDescriptionForm';
import { SearchResults } from '../Search/SearchResults';

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
import Fade from '@mui/material/Fade';

// Icons
import PeopleIcon from '@mui/icons-material/PeopleRounded';
import BarChartIcon from '@mui/icons-material/BarChartRounded';
import SearchIcon from '@mui/icons-material/SearchRounded';
import TrendingUpIcon from '@mui/icons-material/TrendingUpRounded';
import AddIcon from '@mui/icons-material/AddRounded';
import AssessmentIcon from '@mui/icons-material/AssessmentRounded';
import HistoryIcon from '@mui/icons-material/HistoryRounded';

export const Dashboard: React.FC = () => {
  const { user } = useAuth();

  // Dashboard Data State
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [recentCandidates, setRecentCandidates] = useState<CandidateProfile[]>([]);
  const [dashboardLoading, setDashboardLoading] = useState(true);
  const [dashboardError, setDashboardError] = useState<string>('');
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);

  // Search State
  const [searchResults, setSearchResults] = useState<SearchResponse | null>(null);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState<string>('');
  const [searchHistory, setSearchHistory] = useState<JobDescription[]>([]);
  const [showSearchResults, setShowSearchResults] = useState(false);
  const [currentSearch, setCurrentSearch] = useState<JobDescription | null>(null);

  // Saved Searches State
  const [savedSearches, setSavedSearches] = useState<any[]>([]);
  const [isSaveSearchOpen, setIsSaveSearchOpen] = useState(false);
  const [saveSearchName, setSaveSearchName] = useState('');

  useEffect(() => {
    if (user) {
      loadDashboardData();
      loadSavedSearches();
    } else {
      setDashboardLoading(false);
    }
  }, [user]);

  const loadSavedSearches = async () => {
    try {
      const response = await apiService.getSavedSearches();
      if (response.success && response.data) {
        setSavedSearches(response.data.searches);
      }
    } catch (error) {
      console.error('Failed to load saved searches', error);
    }
  };

  const loadDashboardData = async () => {
    setDashboardLoading(true);
    setDashboardError('');

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
            const candidatesData = apiCandidates.data as any;
            setRecentCandidates(Array.isArray(candidatesData) ? candidatesData : (candidatesData.candidates || []));
          }
        } catch {
          setRecentCandidates([]);
        }
      }
    } catch (error: any) {
      setDashboardError(error.message || 'Failed to load dashboard data');
    } finally {
      setDashboardLoading(false);
    }
  };

  const handleSearch = async (jobDescription: JobDescription) => {
    setSearchLoading(true);
    setSearchError('');
    setSearchResults(null);
    setShowSearchResults(true);
    setCurrentSearch(jobDescription);

    try {
      // Step 1: Analyze the query with the Search Agent
      // We only do this if it's a raw text query (title/description) and not a re-run of a structured search
      let searchParams = jobDescription;
      let agentAnalysis = null;

      if (jobDescription.title && !jobDescription.min_experience) {
        // This looks like a raw query, let's analyze it
        try {
          const analysisResponse = await apiService.analyzeSearchQuery(jobDescription.title + ' ' + (jobDescription.description || ''));
          if (analysisResponse.success && analysisResponse.data) {
            const strategy = analysisResponse.data;
            agentAnalysis = strategy;

            // Update search params with Agent's strategy
            searchParams = {
              ...jobDescription,
              title: strategy.target_role, // Use standardized role
              description: strategy.search_query, // Use optimized vector query
              min_experience: strategy.filters?.min_years_experience || 0,
              // We could also map context/requirements to skills if needed
              required_skills: strategy.key_requirements
            };

            console.log('Agent Strategy:', strategy);
          }
        } catch (agentError) {
          console.warn('Agent analysis failed, falling back to raw search:', agentError);
        }
      }

      // Step 2: Execute the search
      const results = await apiService.searchCandidates(searchParams);

      // Attach agent reasoning to the results for display (optional, if UI supports it)
      if (agentAnalysis && results.success) {
        // We could inject a "Search Strategy" card into the results here
        // For now, we'll just log it.
      }

      setSearchResults(results);

      // Add to search history
      setSearchHistory(prev => {
        const updated = [searchParams, ...prev];
        return updated.slice(0, 5); // Keep only last 5 searches
      });
    } catch (error: any) {
      setSearchError(error.message || 'Search failed');
    } finally {
      setSearchLoading(false);
    }
  };

  const handleQuickSearch = (jobDesc: JobDescription) => {
    handleSearch(jobDesc);
    // Scroll to top to show search is happening
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleSaveSearch = async () => {
    if (!currentSearch || !saveSearchName.trim()) return;

    try {
      await apiService.saveSearch(saveSearchName, { job_description: currentSearch }, 'candidate');
      setIsSaveSearchOpen(false);
      setSaveSearchName('');
      loadSavedSearches();
    } catch (error) {
      console.error('Failed to save search', error);
      // TODO: Show error notification
    }
  };

  const handleDeleteSavedSearch = async (id: string) => {
    try {
      await apiService.deleteSavedSearch(id);
      loadSavedSearches();
    } catch (error) {
      console.error('Failed to delete search', error);
    }
  };

  const handleFindSimilar = async (candidateId: string) => {
    setSearchLoading(true);
    setSearchError('');
    setSearchResults(null);
    setShowSearchResults(true);
    // Clear current search since this is a similarity search, not a text search
    setCurrentSearch(null);
    window.scrollTo({ top: 0, behavior: 'smooth' });

    try {
      const response = await apiService.findSimilarCandidates(candidateId);
      if (response.success && response.data) {
        // Transform the similar candidates response into the SearchResponse format
        // The backend returns VectorSearchResult[] directly
        const similarCandidates = response.data || [];

        // Fetch full profiles for these candidates if needed, or if the backend already returns them
        // The current findSimilarCandidates implementation returns enriched results with 'profile'

        const matches = similarCandidates.map((result: any) => ({
          candidate: {
            candidate_id: result.candidate_id,
            ...result.profile,
            // Ensure essential fields are present
            name: result.profile?.name || 'Unknown Candidate',
            current_role: result.profile?.current_role || 'Role not specified',
            current_company: result.profile?.current_company || 'Company not specified',
            overall_score: result.overall_score || 0,
            matchReasons: result.match_reasons || []
          },
          score: result.overall_score || result.similarity_score || 0,
          similarity: result.similarity_score || 0,
          match_reasons: result.match_reasons || [],
          rationale: {
            overall_assessment: result.match_reasons?.[0] || 'Similar profile based on AI analysis.',
            strengths: [],
            gaps: [],
            risk_factors: []
          }
        }));

        setSearchResults({
          success: true,
          matches: matches,
          query_time_ms: 0, // Not available from this endpoint
          insights: {
            total_candidates: matches.length,
            avg_match_score: matches.reduce((acc: number, curr: any) => acc + (curr.score || 0), 0) / (matches.length || 1),
            top_skills_matched: [],
            common_gaps: [],
            market_analysis: 'Similar candidates found based on profile similarity.',
            recommendations: []
          }
        });
      }
    } catch (error: any) {
      setSearchError(error.message || 'Failed to find similar candidates');
    } finally {
      setSearchLoading(false);
    }
  };

  const handleCandidateAdded = (candidate: CandidateProfile) => {
    loadDashboardData();
  };

  const clearSearch = () => {
    setShowSearchResults(false);
    setSearchResults(null);
    setSearchError('');
    setCurrentSearch(null);
  };

  const StatCard = ({ icon, value, label, color }: { icon: React.ReactNode, value: string | number, label: string, color: string }) => (
    <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'center', boxShadow: 1 }}>
      <CardContent sx={{ display: 'flex', alignItems: 'center', p: 2, '&:last-child': { pb: 2 } }}>
        <Box sx={{
          p: 1,
          borderRadius: 2,
          bgcolor: `${color}15`,
          color: color,
          mr: 2,
          display: 'flex'
        }}>
          {icon}
        </Box>
        <Box>
          <Typography variant="h5" fontWeight="bold" sx={{ color: 'text.primary', lineHeight: 1 }}>
            {value}
          </Typography>
          <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
            {label}
          </Typography>
        </Box>
      </CardContent>
    </Card>
  );

  if (dashboardLoading && !stats) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '80vh' }}>
        <CircularProgress />
        <Typography sx={{ ml: 2 }}>Loading dashboard...</Typography>
      </Box>
    );
  }

  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
      {/* Hero Search Section */}
      <Box sx={{ mb: 6, maxWidth: '1000px', mx: 'auto' }}>
        <Box sx={{ textAlign: 'center', mb: 4 }}>
          <Typography variant="h3" component="h1" fontWeight="800" gutterBottom sx={{
            background: 'linear-gradient(45deg, #0F172A 30%, #3B82F6 90%)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent'
          }}>
            Find Your Next Hire
          </Typography>
          <Typography variant="h6" color="text.secondary" sx={{ maxWidth: '600px', mx: 'auto' }}>
            Paste a job description below to instantly match with {stats?.totalCandidates ? stats.totalCandidates.toLocaleString() : 'thousands of'} candidates using AI.
          </Typography>
        </Box>

        <Paper elevation={3} sx={{ p: 0, overflow: 'hidden', borderRadius: 3, border: '1px solid rgba(0,0,0,0.08)' }}>
          <Box sx={{ p: 3, bgcolor: '#f8fafc', borderBottom: '1px solid rgba(0,0,0,0.05)' }}>
            <JobDescriptionForm onSearch={handleSearch} loading={searchLoading} />
          </Box>
        </Paper>

        {/* Recent Searches (Quick Access) */}
        {searchHistory.length > 0 && !showSearchResults && (
          <Fade in={true}>
            <Box sx={{ mt: 3 }}>
              <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
                <HistoryIcon fontSize="small" /> Recent Searches:
              </Typography>
              <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', gap: 1 }}>
                {searchHistory.map((search, index) => (
                  <Chip
                    key={index}
                    label={search.title || (search.company ? `${search.company} Role` : 'Untitled Search')}
                    onClick={() => handleQuickSearch(search)}
                    variant="outlined"
                    sx={{ bgcolor: 'background.paper' }}
                  />
                ))}
              </Stack>
            </Box>
          </Fade>
        )}
      </Box>

      {/* Search Results View */}
      {showSearchResults ? (
        <Fade in={true}>
          <Box>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
              <Typography variant="h5" fontWeight="bold">Search Results</Typography>
              <Box>
                {currentSearch && (
                  <Button
                    variant="outlined"
                    startIcon={<Box component="span">💾</Box>}
                    onClick={() => setIsSaveSearchOpen(true)}
                    sx={{ mr: 2 }}
                  >
                    Save Search
                  </Button>
                )}
                <Button onClick={clearSearch} color="inherit">
                  Back to Dashboard
                </Button>
              </Box>
            </Box>
            <SearchResults
              results={searchResults}
              loading={searchLoading}
              error={searchError}
              onFindSimilar={handleFindSimilar}
            />
          </Box>
        </Fade>
      ) : (
        /* Default Dashboard View */
        <Fade in={true}>
          <Box>
            <Divider sx={{ mb: 6 }}>
              <Chip label="Database Overview" />
            </Divider>

            {/* Stats Grid (Secondary) */}
            <Grid container spacing={3} sx={{ mb: 6 }}>
              <Grid item xs={6} md={3}>
                <StatCard
                  icon={<PeopleIcon />}
                  value={stats?.totalCandidates || 0}
                  label="Total Candidates"
                  color="#0F172A"
                />
              </Grid>
              <Grid item xs={6} md={3}>
                <StatCard
                  icon={<AssessmentIcon />}
                  value={`${Math.round((stats?.avgMatchScore || 0) * 100)}%`}
                  label="Avg Match Score"
                  color="#10B981"
                />
              </Grid>
              <Grid item xs={6} md={3}>
                <StatCard
                  icon={<SearchIcon />}
                  value={stats?.activeSearches || 0}
                  label="Active Searches"
                  color="#3B82F6"
                />
              </Grid>
              <Grid item xs={6} md={3}>
                <StatCard
                  icon={<TrendingUpIcon />}
                  value={stats?.topSkills?.length || 0}
                  label="Skills Tracked"
                  color="#8B5CF6"
                />
              </Grid>
            </Grid>

            <Grid container spacing={4}>
              {/* Saved Searches Section */}
              <Grid item xs={12} md={8}>
                <Box sx={{ mb: 4 }}>
                  <Typography variant="h6" fontWeight="bold" gutterBottom>
                    Saved Searches
                  </Typography>
                  {savedSearches.length === 0 ? (
                    <Paper sx={{ p: 4, textAlign: 'center', color: 'text.secondary' }}>
                      <Typography>No saved searches yet.</Typography>
                    </Paper>
                  ) : (
                    <Grid container spacing={2}>
                      {savedSearches.map((search) => (
                        <Grid item xs={12} sm={6} key={search.id}>
                          <Paper sx={{ p: 2, position: 'relative' }}>
                            <Typography variant="subtitle1" fontWeight="bold">
                              {search.name}
                            </Typography>
                            <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 2 }}>
                              {new Date(search.createdAt).toLocaleDateString()}
                            </Typography>
                            <Box sx={{ display: 'flex', gap: 1 }}>
                              <Button
                                size="small"
                                variant="contained"
                                onClick={() => handleQuickSearch(search.query.job_description)}
                              >
                                Run Search
                              </Button>
                              <Button
                                size="small"
                                color="error"
                                onClick={() => handleDeleteSavedSearch(search.id)}
                              >
                                Delete
                              </Button>
                            </Box>
                          </Paper>
                        </Grid>
                      ))}
                    </Grid>
                  )}
                </Box>
              </Grid>

              {/* Right Column: Quick Actions */}
              <Grid item xs={12} md={4}>
                <Box sx={{ mb: 4 }}>
                  <Typography variant="h6" fontWeight="bold" gutterBottom>
                    Quick Actions
                  </Typography>
                  <Stack spacing={2}>
                    <Paper sx={{ p: 2, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <Box>
                        <Typography variant="subtitle2" fontWeight="bold">Add Candidate</Typography>
                        <Typography variant="caption" color="text.secondary">Upload new resume</Typography>
                      </Box>
                      <Button
                        variant="contained"
                        size="small"
                        startIcon={<AddIcon />}
                        onClick={() => setIsAddModalOpen(true)}
                      >
                        Add
                      </Button>
                    </Paper>
                    <Paper sx={{ p: 2, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <Box>
                        <Typography variant="subtitle2" fontWeight="bold">View Analytics</Typography>
                        <Typography variant="caption" color="text.secondary">Analyze trends</Typography>
                      </Box>
                      <Button variant="outlined" size="small" startIcon={<BarChartIcon />}>
                        View
                      </Button>
                    </Paper>
                  </Stack>
                </Box>

                {/* Top Skills (Compact) */}
                {stats?.topSkills && stats.topSkills.length > 0 && (
                  <Box sx={{ mt: 4 }}>
                    <Typography variant="h6" fontWeight="bold" gutterBottom>
                      Trending Skills
                    </Typography>
                    <Paper sx={{ p: 2 }}>
                      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                        {stats.topSkills.slice(0, 10).map((item, index) => (
                          <Chip
                            key={index}
                            label={item.skill}
                            size="small"
                            variant="outlined"
                          />
                        ))}
                      </Box>
                    </Paper>
                  </Box>
                )}

                <Box sx={{ mt: 4 }}>
                  <AllowedUsersPanel />
                </Box>
              </Grid>
            </Grid>
          </Box>
        </Fade>
      )}

      {/* Modals */}
      <AddCandidateModal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        onCandidateAdded={handleCandidateAdded}
      />

      {/* Save Search Dialog - Simple implementation */}
      {isSaveSearchOpen && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1300
        }}>
          <Paper sx={{ p: 3, width: '100%', maxWidth: 400 }}>
            <Typography variant="h6" gutterBottom>Save Search</Typography>
            <Box sx={{ mb: 2 }}>
              <input
                type="text"
                placeholder="Search Name (e.g., Senior React Dev)"
                value={saveSearchName}
                onChange={(e) => setSaveSearchName(e.target.value)}
                style={{
                  width: '100%',
                  padding: '8px',
                  borderRadius: '4px',
                  border: '1px solid #ccc',
                  fontSize: '16px'
                }}
              />
            </Box>
            <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1 }}>
              <Button onClick={() => setIsSaveSearchOpen(false)}>Cancel</Button>
              <Button variant="contained" onClick={handleSaveSearch} disabled={!saveSearchName.trim()}>
                Save
              </Button>
            </Box>
          </Paper>
        </div>
      )}
    </Container>
  );
};
