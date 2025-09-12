import React, { useEffect, useState } from 'react';
import { apiService } from '../../services/api';
import { firestoreService } from '../../services/firestore-direct';
import { DashboardStats, CandidateProfile } from '../../types';
import { SimpleCandidateCard } from '../Candidate/SimpleCandidateCard';
import { useAuth } from '../../contexts/AuthContext';
import { AllowedUsersPanel } from '../Admin/AllowedUsersPanel';

export const Dashboard: React.FC = () => {
  const { user } = useAuth();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [recentCandidates, setRecentCandidates] = useState<CandidateProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>('');

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
      }
      
      if (candidatesResult && candidatesResult.length > 0) {
        setRecentCandidates(candidatesResult);
      } else {
        // Fallback to API if Firestore direct fails
        try {
          const apiCandidates = await apiService.getCandidates({ limit: 6, offset: 0 });
          if (apiCandidates.success && apiCandidates.data) {
            setRecentCandidates(apiCandidates.data);
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

  if (loading) {
    return (
      <div className="dashboard">
        <div className="loading-container">
          <div className="loading-spinner"></div>
          <p>Loading dashboard...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="dashboard">
        <div className="error-container">
          <div className="error-icon">⚠️</div>
          <h3>Dashboard Error</h3>
          <p>{error}</p>
          <button 
            onClick={loadDashboardData}
            className="btn btn-primary"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <h1>Dashboard</h1>
        <p>Overview of your candidate database and recent activity</p>
      </div>

      {/* Stats Grid */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon">👥</div>
          <div className="stat-content">
            <h3>{stats?.totalCandidates || 0}</h3>
            <p>Total Candidates</p>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon">📊</div>
          <div className="stat-content">
            <h3>{Math.round((stats?.avgMatchScore || 0) * 100)}%</h3>
            <p>Average Match Score</p>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon">🔍</div>
          <div className="stat-content">
            <h3>{stats?.activeSearches || 0}</h3>
            <p>Active Processing</p>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon">🚀</div>
          <div className="stat-content">
            <h3>{stats?.topSkills?.length || 0}</h3>
            <p>Top Skills Tracked</p>
          </div>
        </div>
      </div>

      {/* Top Skills */}
      {stats?.topSkills && stats.topSkills.length > 0 && (
        <div className="dashboard-section">
          <h2>Top Skills in Database</h2>
          <div className="skills-cloud">
            {stats.topSkills.slice(0, 15).map((item, index) => (
              <span key={index} className={`skill-bubble priority-${Math.min(3, Math.floor(index / 5))}`}>
                {item.skill} ({item.count})
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Recent Candidates */}
      <div className="dashboard-section">
        <div className="section-header">
          <h2>Recent Candidates</h2>
          <p>Latest additions to your candidate database</p>
        </div>
        
        {recentCandidates.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">📋</div>
            <h3>No candidates yet</h3>
            <p>Start by adding candidates to build your database</p>
          </div>
        ) : (
          <div className="candidates-grid">
            {recentCandidates.map((candidate, index) => (
              <SimpleCandidateCard
                key={candidate.id || candidate.candidate_id || index}
                candidate={candidate}
              />
            ))}
          </div>
        )}
      </div>

      {/* Quick Actions */}
      <div className="dashboard-section">
        <h2>Quick Actions</h2>
        <div className="quick-actions">
          <div className="action-card">
            <div className="action-icon">🔍</div>
            <h3>Search Candidates</h3>
            <p>Find the perfect match for your job requirements</p>
            <button className="btn btn-primary">Start Search</button>
          </div>

          <div className="action-card">
            <div className="action-icon">➕</div>
            <h3>Add Candidate</h3>
            <p>Upload a new resume to expand your database</p>
            <button className="btn btn-secondary">Add Candidate</button>
          </div>

          <div className="action-card">
            <div className="action-icon">📊</div>
            <h3>View Analytics</h3>
            <p>Analyze your candidate database and trends</p>
            <button className="btn btn-outline">View Reports</button>
          </div>
        </div>
      </div>

      {/* Admin Panel */}
      <AllowedUsersPanel />
    </div>
  );
};
