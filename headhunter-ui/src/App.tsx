import React, { useState, useEffect } from 'react';
import './App.css';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { Navbar } from './components/Navigation/Navbar';
import { AuthModal } from './components/Auth/AuthModal';
import { Dashboard } from './components/Dashboard/Dashboard';
import { SearchPage } from './components/Search/SearchPage';
import { AdminPage } from './components/Admin/AdminPage';
import { LandingPage } from './components/Landing/LandingPage';

type PageType = 'dashboard' | 'search' | 'candidates' | 'analytics' | 'profile' | 'settings' | 'admin';

function AppContent() {
  const { user, loading } = useAuth();
  const [currentPage, setCurrentPage] = useState<PageType>('dashboard');
  const [showAuth, setShowAuth] = useState(false);

  // Close auth modal when user signs in
  useEffect(() => {
    if (user && showAuth) {
      setShowAuth(false);
    }
  }, [user, showAuth]);

  // Show loading screen while checking auth
  if (loading) {
    return (
      <div className="app">
        <div className="loading-container">
          <div className="loading-spinner"></div>
          <p>Loading Headhunter AI...</p>
        </div>
      </div>
    );
  }

  const handleShowAuth = () => {
    if (!user) {
      setShowAuth(true);
    }
  };

  const handleNavigation = (page: string) => {
    // If user tries to navigate while not authenticated, show auth modal
    if (!user) {
      setShowAuth(true);
      return;
    }

    setCurrentPage(page as PageType);
  };

  const renderCurrentPage = () => {
    // Show landing page for unauthenticated users
    if (!user) {
      return <LandingPage onGetStarted={() => setShowAuth(true)} />;
    }

    // Decode role claim for admin gating
    let role: string | undefined;
    try {
      const token = (user as any)?.stsTokenManager?.accessToken || undefined;
      if (token) {
        const payload = JSON.parse(atob(token.split('.')[1]));
        role = payload.role || payload.custom_role;
      }
    } catch { }

    switch (currentPage) {
      case 'dashboard':
        return <Dashboard />;
      case 'search':
        return <SearchPage />;

      case 'profile':
        return (
          <div className="page-placeholder">
            <div className="empty-state">
              <div className="empty-icon">👤</div>
              <h2>Profile Settings</h2>
              <p>Manage your account and preferences</p>
              <div className="user-info-card">
                <h3>Current User</h3>
                <p><strong>Email:</strong> {user?.email}</p>
                <p><strong>Display Name:</strong> {user?.displayName || 'Not set'}</p>
                <p><strong>Account ID:</strong> {user?.uid}</p>
              </div>
            </div>
          </div>
        );
      case 'settings':
        return (
          <div className="page-placeholder">
            <div className="empty-state">
              <div className="empty-icon">⚙️</div>
              <h2>Application Settings</h2>
              <p>Configure your Headhunter AI experience</p>
              <p className="text-muted">Settings panel coming soon...</p>
            </div>
          </div>
        );
      case 'admin':
        if (role === 'admin' || role === 'super_admin') {
          return <AdminPage />;
        }
        return (
          <div className="page-placeholder">
            <div className="empty-state">
              <div className="empty-icon">🔒</div>
              <h2>Admin Only</h2>
              <p>You do not have permission to view this page.</p>
            </div>
          </div>
        );
      default:
        return <Dashboard />;
    }
  };

  // For landing page, render without navbar wrapper
  if (!user) {
    return (
      <div className="app app-landing">
        {renderCurrentPage()}
        <AuthModal
          isOpen={showAuth}
          onClose={() => setShowAuth(false)}
          initialMode="login"
        />
      </div>
    );
  }

  return (
    <div className="app">
      <Navbar
        currentPage={currentPage}
        onNavigate={handleNavigation}
        onShowAuth={handleShowAuth}
      />

      <main className="main-content">
        {renderCurrentPage()}
      </main>

      <AuthModal
        isOpen={showAuth}
        onClose={() => setShowAuth(false)}
        initialMode="login"
      />
    </div>
  );
}

function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}

export default App;