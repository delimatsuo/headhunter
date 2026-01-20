import React, { useEffect, useState } from 'react';
import { apiService } from '../../services/api';
import { firestoreService } from '../../services/firestore-direct';
import { keywordSearch } from '../../config/firebase';
import { DashboardStats, CandidateProfile, JobDescription, SearchResponse } from '../../types';
import { SkillAwareCandidateCard } from '../Candidate/SkillAwareCandidateCard';
import { useAuth } from '../../contexts/AuthContext';

import { AddCandidateModal } from '../Upload/AddCandidateModal';
import { JobDescriptionForm, SourcingStrategy, JobAnalysis } from '../Search/JobDescriptionForm';
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
import LinearProgress from '@mui/material/LinearProgress';

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
  const [displayLimit, setDisplayLimit] = useState(20);

  // Search Mode State (Quick Find vs AI Match)
  const [searchMode, setSearchMode] = useState<'quickfind' | 'aimatch'>('quickfind');
  const [quickFindQuery, setQuickFindQuery] = useState('');

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
      // Get user's org_id from their Firebase token claims
      let orgId: string | undefined;
      if (user) {
        try {
          const tokenResult = await user.getIdTokenResult();
          orgId = tokenResult.claims.org_id as string | undefined;
          console.log('User org_id:', orgId);
        } catch (tokenError) {
          console.warn('Could not get user token claims:', tokenError);
        }
      }

      // Fetch data - use API for stats (unified Cloud SQL count), Firestore for candidates
      console.log('Starting data fetch (API stats + Firestore candidates)...');
      const [statsResult, candidatesResult] = await Promise.all([
        // Use API first for stats (returns unified Cloud SQL count of 35k+)
        apiService.getDashboardStats().catch((apiErr) => {
          console.warn('API getDashboardStats failed, falling back to Firestore:', apiErr);
          return firestoreService.getDashboardStats(orgId).catch((err) => { console.error('Firestore getDashboardStats error:', err); return null; });
        }),
        firestoreService.getCandidatesDirect(6, orgId).catch((err) => { console.error('getCandidatesDirect error:', err); return []; })
      ]);
      console.log('Data fetch complete. Stats:', statsResult?.totalCandidates, 'Candidates:', candidatesResult?.length);

      if (statsResult) {
        setStats(statsResult);
        console.log('Stats set successfully:', statsResult.totalCandidates);
      } else {
        console.error('Failed to load stats from both API and Firestore');
      }

      if (candidatesResult && candidatesResult.length > 0) {
        setRecentCandidates(candidatesResult);
        console.log('Candidates set successfully:', candidatesResult.length);
      } else {
        console.log('No candidatesResult, trying API fallback...');
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
      console.error('loadDashboardData error:', error);
      setDashboardError(error.message || 'Failed to load dashboard data');
    } finally {
      setDashboardLoading(false);
    }
  };

  const [searchStatus, setSearchStatus] = useState<string>(''); // For progress updates
  const [loadingPhase, setLoadingPhase] = useState<'analyzing' | 'searching' | null>(null);
  const [currentAnalysis, setCurrentAnalysis] = useState<JobAnalysis | null>(null);
  const [page, setPage] = useState(1);
  const [activeSearchParams, setActiveSearchParams] = useState<JobDescription | null>(null);

  // ... (existing state)

  const handleSearch = async (jobDescription: JobDescription, sourcingStrategy?: SourcingStrategy, analysis?: JobAnalysis) => {
    setSearchLoading(true);
    setLoadingPhase('searching');
    setSearchStatus('⚡ AI Search: Finding best matches...');
    if (analysis) {
      setCurrentAnalysis(analysis);
    }
    setSearchError('');
    setSearchResults(null);
    setShowSearchResults(true);
    setCurrentSearch(jobDescription);
    setDisplayLimit(20); // Reset pagination on new search

    try {
      // Step 1: Analyze the query with the Search Agent (for legacy engine)
      let searchParams = jobDescription;
      let agentAnalysis = null;

      if (jobDescription.title && !jobDescription.min_experience) {
        setSearchStatus('AI analyzing job requirements...');
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
              seniority: strategy.seniority, // CRITICAL: Pass seniority from Agent
              required_skills: strategy.key_requirements
            };

            console.log('Agent Strategy (seniority:', strategy.seniority, '):', strategy);
          }
        } catch (agentError) {
          console.warn('Agent analysis failed, falling back to raw search:', agentError);
        }
      }

      // Step 2: Execute the search using the selected engine
      setActiveSearchParams(searchParams);
      setPage(1);

      let results: SearchResponse;
      // Use Fast Match engine (with Vertex AI cross-encoder ranking)
      setSearchStatus('⚡ AI Search: Cross-encoder ranking...');
      results = await apiService.searchWithEngine(
        'legacy',
        searchParams,
        { limit: 50 }
      );

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
      setSearchStatus('');
      setLoadingPhase(null);
    }
  };
  const handleLoadMoreBackend = async () => {
    if (!activeSearchParams) return;

    setSearchLoading(true);

    try {
      const nextPage = page + 1;
      const response = await apiService.searchCandidates(activeSearchParams, undefined, nextPage);

      if (response && response.matches && response.matches.length > 0) {
        setSearchResults(prev => {
          if (!prev) return response;
          return {
            ...prev,
            matches: [...(prev.matches || []), ...response.matches],
            insights: {
              ...prev.insights,
              total_candidates: response.insights?.total_candidates || prev.insights?.total_candidates
            }
          };
        });
        setPage(nextPage);
        setDisplayLimit(prev => prev + 20);
      }
    } catch (error) {
      console.error('Error loading more:', error);
    } finally {
      setSearchLoading(false);
    }
  };

  // Quick Find: keyword search against PostgreSQL sourcing database (35k+ candidates)
  const handleQuickFind = async () => {
    if (!quickFindQuery.trim()) return;

    setSearchLoading(true);
    setSearchError('');
    setSearchResults(null);
    setShowSearchResults(true);
    setCurrentSearch(null);
    setDisplayLimit(50);

    try {
      console.log('Quick Find: calling keywordSearch Cloud Function with query:', quickFindQuery);

      // Call the new keywordSearch Cloud Function (PostgreSQL sourcing database)
      const response = await keywordSearch({
        query: quickFindQuery,
        limit: 50
      });

      const result = response.data as any;
      console.log('Quick Find: server returned', result?.candidates?.length, 'candidates');
      if (result?.candidates?.[0]) {
        console.log('Quick Find: first candidate structure:', JSON.stringify(result.candidates[0], null, 2));
      }

      if (result?.success && result?.candidates) {
        // Transform PostgreSQL sourcing candidates to SearchResponse format
        const matches = result.candidates.map((candidate: any) => {
          // Construct name from first_name and last_name
          const name = [candidate.first_name, candidate.last_name]
            .filter(Boolean)
            .join(' ')
            .trim() || 'Unknown';

          // Get analysis data if available
          const analysis = candidate.intelligent_analysis || {};

          // Extract skills from intelligent_analysis if present
          let skills: string[] = [];
          if (analysis.explicit_skills) {
            if (typeof analysis.explicit_skills === 'object' && !Array.isArray(analysis.explicit_skills)) {
              skills = Object.keys(analysis.explicit_skills).slice(0, 10);
            } else if (Array.isArray(analysis.explicit_skills)) {
              skills = analysis.explicit_skills.map((s: any) => typeof s === 'string' ? s : s.skill || s).slice(0, 10);
            }
          } else if (analysis.inferred_skills?.highly_probable_skills) {
            skills = analysis.inferred_skills.highly_probable_skills.map((s: any) => typeof s === 'string' ? s : s.skill || s).slice(0, 10);
          }

          // Extract experience from analysis
          const experience = analysis.career_trajectory_analysis?.years_experience ||
            analysis.personal_details?.years_of_experience ||
            '';

          // Extract summary from analysis
          const summary = analysis.recruiter_insights?.one_liner ||
            analysis.recruiter_insights?.summary ||
            candidate.headline ||
            '';

          // Extract role with multiple fallbacks
          // Priority: current_role from DB → analysis → headline parsing
          const extractRoleFromHeadline = (headline: string | null | undefined): string => {
            if (!headline) return '';
            // Try "Role at Company" pattern
            const atMatch = headline.split(' at ')[0]?.trim();
            if (atMatch && atMatch !== headline) return atMatch;
            // Try "Role @ Company" pattern
            const atSymbolMatch = headline.split(' @ ')[0]?.trim();
            if (atSymbolMatch && atSymbolMatch !== headline) return atSymbolMatch;
            // Try "Role | Company" pattern
            const pipeMatch = headline.split(' | ')[0]?.trim();
            if (pipeMatch && pipeMatch !== headline) return pipeMatch;
            // Return full headline if no pattern matched
            return headline;
          };

          const role = candidate.current_role ||
            analysis.career_trajectory_analysis?.current_role ||
            analysis.personal_details?.current_role ||
            extractRoleFromHeadline(candidate.headline) ||
            '';

          const company = candidate.current_company ||
            analysis.career_trajectory_analysis?.current_company ||
            '';

          return {
            candidate: {
              id: candidate.candidate_id,
              candidate_id: candidate.candidate_id,
              name,
              title: role,
              company: company,
              current_role: role,
              current_company: company,
              location: candidate.location || analysis.personal_details?.location || '',
              skills: skills,
              experience,
              summary,
              matchScore: 1,
              overall_score: 1,
              strengths: analysis.recruiter_insights?.strengths || [],
              fitReasons: [],
              availability: 'Unknown',
              desiredSalary: '',
              profileUrl: '#',
              lastUpdated: new Date().toISOString(),
              // Pass raw objects for CandidateCard to read directly
              intelligent_analysis: analysis,
              resume_analysis: null,
              original_data: null,
              linkedin_url: candidate.linkedin_url || '',
              headline: candidate.headline,
              personal: null,
              documents: null
            },
            score: 100,
            match_reasons: [`Matched keyword: "${quickFindQuery}"`],
            rationale: {
              overall_assessment: `Found via Quick Find for "${quickFindQuery}"`,
              strengths: analysis.recruiter_insights?.strengths || [],
              gaps: [],
              risk_factors: []
            }
          };
        });

        setSearchResults({
          success: true,
          matches,
          query_time_ms: 0,
          insights: {
            total_candidates: result.total || matches.length,
            avg_match_score: 100,
            top_skills_matched: [],
            common_gaps: [],
            market_analysis: `Found ${result.total || matches.length} candidates matching "${quickFindQuery}" in sourcing database`,
            recommendations: []
          }
        });
      } else {
        setSearchResults({
          success: true,
          matches: [],
          query_time_ms: 0,
          insights: { total_candidates: 0, avg_match_score: 0, top_skills_matched: [], common_gaps: [], market_analysis: 'No results', recommendations: [] }
        });
      }
    } catch (error: any) {
      console.error('Quick Find error:', error);
      setSearchError(error.message || 'Quick Find failed');
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
      console.log('Saving search:', saveSearchName, currentSearch);
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
            ...result, // Spread the full result first
            ...result.profile, // Then profile if it exists (though backend now flattens it)
            // Ensure essential fields are present, prioritizing top-level fields
            name: result.name || result.profile?.name || 'Unknown Candidate',
            current_role: result.current_role || result.profile?.current_role || 'Role not specified',
            current_company: result.current_company || result.profile?.current_company || 'Company not specified',
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
            Search {stats?.totalCandidates ? stats.totalCandidates.toLocaleString() : 'thousands of'} candidates by name, company, or skills.
          </Typography>
        </Box>

        <Paper elevation={3} sx={{ p: 0, overflow: 'hidden', borderRadius: 3, border: '1px solid rgba(0,0,0,0.08)' }}>
          {/* Search Mode Tabs */}
          <Box sx={{ display: 'flex', borderBottom: '1px solid rgba(0,0,0,0.08)' }}>
            <Button
              onClick={() => setSearchMode('quickfind')}
              sx={{
                flex: 1,
                py: 1.5,
                borderRadius: 0,
                borderBottom: searchMode === 'quickfind' ? '3px solid #3B82F6' : '3px solid transparent',
                bgcolor: searchMode === 'quickfind' ? '#f8fafc' : 'white',
                fontWeight: searchMode === 'quickfind' ? 700 : 500,
                color: searchMode === 'quickfind' ? '#3B82F6' : 'text.secondary',
              }}
            >
              🔍 Quick Find
            </Button>
            <Button
              onClick={() => setSearchMode('aimatch')}
              sx={{
                flex: 1,
                py: 1.5,
                borderRadius: 0,
                borderBottom: searchMode === 'aimatch' ? '3px solid #3B82F6' : '3px solid transparent',
                bgcolor: searchMode === 'aimatch' ? '#f8fafc' : 'white',
                fontWeight: searchMode === 'aimatch' ? 700 : 500,
                color: searchMode === 'aimatch' ? '#3B82F6' : 'text.secondary',
              }}
            >
              ✨ AI Match
            </Button>
          </Box>

          {/* Quick Find Mode */}
          {searchMode === 'quickfind' && (
            <Box sx={{ p: 3, bgcolor: '#f8fafc' }}>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Search by candidate name, company, title, or skills
              </Typography>
              <Box sx={{ display: 'flex', gap: 2 }}>
                <input
                  type="text"
                  value={quickFindQuery}
                  onChange={(e) => setQuickFindQuery(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleQuickFind()}
                  placeholder="Name, company, title, or skills..."
                  style={{
                    flex: 1,
                    padding: '12px 16px',
                    fontSize: '16px',
                    border: '1px solid #e2e8f0',
                    borderRadius: '8px',
                    outline: 'none',
                  }}
                />
                <Button
                  variant="contained"
                  onClick={handleQuickFind}
                  disabled={searchLoading || !quickFindQuery.trim()}
                  sx={{ px: 4, fontWeight: 600 }}
                >
                  {searchLoading ? 'Searching...' : 'Search'}
                </Button>
              </Box>
            </Box>
          )}

          {/* AI Match Mode (existing job description form) */}
          {searchMode === 'aimatch' && (
            <Box sx={{ p: 3, bgcolor: '#f8fafc' }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                <Typography variant="body2" color="text.secondary">
                  Paste a job description for AI-powered candidate matching
                </Typography>
              </Box>
              <JobDescriptionForm
                onSearch={handleSearch}
                loading={searchLoading}
                loadingPhase={loadingPhase}
              />
            </Box>
          )}
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
                {searchResults && searchResults.matches && searchResults.matches.length > 0 && (
                  <Button
                    variant="outlined"
                    startIcon={<Box component="span">📥</Box>}
                    onClick={() => {
                      // Generate CSV content
                      const csvRows: string[] = [];

                      // Header row
                      csvRows.push(['Name', 'Role', 'Level', 'Experience (Years)', 'Match Score (%)', 'Similarity (%)', 'LinkedIn URL', 'Top Skills', 'AI Summary'].join(','));

                      // Data rows
                      searchResults.matches.forEach((match: any) => {
                        const candidate = match.candidate || {};
                        const name = (candidate.name || 'Unknown').replace(/,/g, ' ');
                        const role = (candidate.current_role || candidate.title || 'Not specified').replace(/,/g, ' ');
                        const level = (candidate.intelligent_analysis?.career_trajectory_analysis?.current_level ||
                          candidate.resume_analysis?.career_trajectory?.current_level || 'Not specified').replace(/,/g, ' ');
                        const experience = candidate.intelligent_analysis?.career_trajectory_analysis?.years_experience ||
                          candidate.resume_analysis?.years_experience || 0;
                        const matchScore = Math.round((match.score <= 1 ? match.score * 100 : match.score) || 0);
                        const similarity = Math.round((match.similarity <= 1 ? match.similarity * 100 : match.similarity) || 0);
                        const linkedInUrl = candidate.linkedin_url || candidate.personal?.linkedin || '';

                        // Get top 5 technical skills
                        const technicalSkills = candidate.intelligent_analysis?.explicit_skills?.technical_skills?.slice(0, 5).map((s: any) =>
                          typeof s === 'string' ? s : s.skill
                        ) || candidate.resume_analysis?.technical_skills?.slice(0, 5) || [];
                        const skillsStr = technicalSkills.join('; ').replace(/,/g, ';');

                        // AI summary (from rationale or match reasons)
                        const aiSummary = (candidate.rationale?.overall_assessment ||
                          candidate.matchReasons?.join('. ') ||
                          candidate.intelligent_analysis?.executive_summary?.one_line_pitch ||
                          '').replace(/,/g, ' ').replace(/"/g, "'").substring(0, 200);

                        csvRows.push([
                          `"${name}"`,
                          `"${role}"`,
                          `"${level}"`,
                          experience,
                          matchScore,
                          similarity,
                          linkedInUrl,
                          `"${skillsStr}"`,
                          `"${aiSummary}"`
                        ].join(','));
                      });

                      // Create and download CSV file
                      const csvContent = csvRows.join('\n');
                      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
                      const url = URL.createObjectURL(blob);
                      const link = document.createElement('a');
                      link.href = url;
                      const timestamp = new Date().toISOString().split('T')[0];
                      link.download = `candidate-search-results-${timestamp}.csv`;
                      document.body.appendChild(link);
                      link.click();
                      document.body.removeChild(link);
                      URL.revokeObjectURL(url);
                    }}
                    sx={{ mr: 2 }}
                  >
                    Export CSV
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
              displayLimit={displayLimit}
              onLoadMore={() => {
                const currentCount = searchResults?.matches?.length || 0;
                // If we're near the end of the list, or the user asks for more than we have
                if (displayLimit + 20 >= currentCount) {
                  // Fetch next batch from backend
                  handleLoadMoreBackend();
                } else {
                  // Just show more local results
                  setDisplayLimit(prev => prev + 20);
                }
              }}
              onShowAll={() => setDisplayLimit(searchResults?.matches?.length || 1000)}
              analysis={currentAnalysis}
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

              {/* Right Column: Analytics & Insights */}
              <Grid item xs={12} md={4}>
                <Box sx={{ mb: 4 }}>
                  <Typography variant="h6" fontWeight="bold" gutterBottom>
                    Talent Insights
                  </Typography>

                  <Stack spacing={3}>
                    {/* Skill Heatmap */}
                    <Paper sx={{ p: 3 }}>
                      <Typography variant="subtitle2" fontWeight="bold" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <TrendingUpIcon fontSize="small" color="primary" /> Top Skills
                      </Typography>
                      <Stack spacing={2} sx={{ mt: 2 }}>
                        {stats?.topSkills?.slice(0, 5).map((item, index) => (
                          <Box key={index}>
                            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                              <Typography variant="body2">{item.skill}</Typography>
                              <Typography variant="caption" color="text.secondary">{item.count}</Typography>
                            </Box>
                            <LinearProgress
                              variant="determinate"
                              value={Math.min((item.count / (stats.topSkills[0]?.count || 1)) * 100, 100)}
                              sx={{ height: 6, borderRadius: 3, bgcolor: 'rgba(0,0,0,0.05)' }}
                            />
                          </Box>
                        ))}
                      </Stack>
                    </Paper>

                    {/* Experience Distribution */}
                    {stats?.experienceLevels && (
                      <Paper sx={{ p: 3 }}>
                        <Typography variant="subtitle2" fontWeight="bold" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <HistoryIcon fontSize="small" color="secondary" /> Experience Level
                        </Typography>
                        <Stack spacing={2} sx={{ mt: 2 }}>
                          {Object.entries(stats.experienceLevels).map(([level, count]) => (
                            <Box key={level}>
                              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                                <Typography variant="body2" sx={{ textTransform: 'capitalize' }}>{level}</Typography>
                                <Typography variant="caption" color="text.secondary">{count}</Typography>
                              </Box>
                              <LinearProgress
                                variant="determinate"
                                value={Math.min((count / (stats.totalCandidates || 1)) * 100, 100)}
                                color="secondary"
                                sx={{ height: 6, borderRadius: 3, bgcolor: 'rgba(0,0,0,0.05)' }}
                              />
                            </Box>
                          ))}
                        </Stack>
                      </Paper>
                    )}

                    {/* Company Pedigree */}
                    {stats?.companyTiers && (
                      <Paper sx={{ p: 3 }}>
                        <Typography variant="subtitle2" fontWeight="bold" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <AssessmentIcon fontSize="small" color="success" /> Company Pedigree
                        </Typography>
                        <Stack spacing={2} sx={{ mt: 2 }}>
                          {Object.entries(stats.companyTiers).map(([tier, count]) => (
                            <Box key={tier}>
                              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                                <Typography variant="body2" sx={{ textTransform: 'capitalize' }}>{tier.replace('_', ' ')}</Typography>
                                <Typography variant="caption" color="text.secondary">{count}</Typography>
                              </Box>
                              <LinearProgress
                                variant="determinate"
                                value={Math.min((count / (stats.totalCandidates || 1)) * 100, 100)}
                                color="success"
                                sx={{ height: 6, borderRadius: 3, bgcolor: 'rgba(0,0,0,0.05)' }}
                              />
                            </Box>
                          ))}
                        </Stack>
                      </Paper>
                    )}

                    {/* Quick Actions */}
                    <Paper sx={{ p: 2, display: 'flex', alignItems: 'center', justifyContent: 'space-between', bgcolor: 'primary.main', color: 'white' }}>
                      <Box>
                        <Typography variant="subtitle2" fontWeight="bold">Add Candidate</Typography>
                        <Typography variant="caption" sx={{ opacity: 0.8 }}>Upload new resume</Typography>
                      </Box>
                      <Button
                        variant="contained"
                        size="small"
                        startIcon={<AddIcon />}
                        onClick={() => setIsAddModalOpen(true)}
                        sx={{ bgcolor: 'white', color: 'primary.main', '&:hover': { bgcolor: 'rgba(255,255,255,0.9)' } }}
                      >
                        Add
                      </Button>
                    </Paper>
                  </Stack>
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
