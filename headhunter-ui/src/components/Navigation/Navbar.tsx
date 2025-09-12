import React, { useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { NavItem } from '../../types';

interface NavbarProps {
  currentPage: string;
  onNavigate: (page: string) => void;
  onShowAuth?: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({ 
  currentPage, 
  onNavigate, 
  onShowAuth 
}) => {
  const { user, signOut } = useAuth();
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const navItems: NavItem[] = [
    { name: 'Dashboard', path: 'dashboard', icon: '🏠' },
    { name: 'Search', path: 'search', icon: '🔍' },
    { name: 'Candidates', path: 'candidates', icon: '👥' },
    { name: 'Analytics', path: 'analytics', icon: '📊' }
  ];

  const handleSignOut = async () => {
    try {
      await signOut();
      setShowUserMenu(false);
    } catch (error) {
      console.error('Error signing out:', error);
    }
  };

  const handleNavClick = (page: string) => {
    onNavigate(page);
    setMobileMenuOpen(false);
  };

  return (
    <nav className="navbar">
      <div className="nav-container">
        <div className="nav-brand">
          <div className="brand-logo" onClick={() => handleNavClick('dashboard')}>
            <img src="/ella-logo.png" alt="Ella Executive Search" className="logo-img" />
            <span className="logo-text">Ella Executive Search</span>
          </div>
        </div>

        {/* Desktop Navigation */}
        <div className="nav-menu desktop">
          {user ? (
            <>
              {navItems.map((item) => (
                <button
                  key={item.path}
                  onClick={() => handleNavClick(item.path)}
                  className={`nav-link ${
                    currentPage === item.path ? 'active' : ''
                  }`}
                >
                  <span className="nav-icon">{item.icon}</span>
                  <span className="nav-text">{item.name}</span>
                </button>
              ))}
            </>
          ) : (
            <div className="nav-guest">
              <span className="nav-welcome">Welcome to Ella Executive Search</span>
            </div>
          )}
        </div>

        {/* User Menu */}
        <div className="nav-user">
          {user ? (
            <div className="user-menu">
              <button
                className="user-button"
                onClick={() => setShowUserMenu(!showUserMenu)}
              >
                {user.photoURL ? (
                  <img 
                    src={user.photoURL} 
                    alt={user.displayName || user.email || 'User'}
                    className="user-avatar"
                  />
                ) : (
                  <div className="user-avatar default">
                    {(user.displayName || user.email || 'U')[0].toUpperCase()}
                  </div>
                )}
                <span className="user-name">
                  {user.displayName || user.email}
                </span>
                <span className="dropdown-arrow">▼</span>
              </button>

              {showUserMenu && (
                <div className="user-dropdown">
                  <div className="user-info">
                    <div className="user-details">
                      <span className="user-display-name">
                        {user.displayName || 'User'}
                      </span>
                      <span className="user-email">{user.email}</span>
                    </div>
                  </div>
                  <div className="dropdown-divider"></div>
                  <button 
                    className="dropdown-item"
                    onClick={() => {
                      handleNavClick('profile');
                      setShowUserMenu(false);
                    }}
                  >
                    <span className="item-icon">👤</span>
                    Profile
                  </button>
                  <button 
                    className="dropdown-item"
                    onClick={() => {
                      handleNavClick('settings');
                      setShowUserMenu(false);
                    }}
                  >
                    <span className="item-icon">⚙️</span>
                    Settings
                  </button>
                  <div className="dropdown-divider"></div>
                  <button className="dropdown-item danger" onClick={handleSignOut}>
                    <span className="item-icon">🚪</span>
                    Sign Out
                  </button>
                </div>
              )}
            </div>
          ) : (
            <button 
              className="btn btn-primary"
              onClick={onShowAuth}
            >
              Sign In
            </button>
          )}
        </div>

        {/* Mobile Menu Button */}
        <button 
          className="mobile-menu-button"
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
        >
          <span className="hamburger"></span>
          <span className="hamburger"></span>
          <span className="hamburger"></span>
        </button>
      </div>

      {/* Mobile Navigation */}
      {mobileMenuOpen && (
        <div className="nav-menu mobile">
          {user ? (
            <>
              {navItems.map((item) => (
                <button
                  key={item.path}
                  onClick={() => handleNavClick(item.path)}
                  className={`nav-link mobile ${
                    currentPage === item.path ? 'active' : ''
                  }`}
                >
                  <span className="nav-icon">{item.icon}</span>
                  <span className="nav-text">{item.name}</span>
                </button>
              ))}
              <div className="mobile-divider"></div>
              <button 
                className="nav-link mobile"
                onClick={() => handleNavClick('profile')}
              >
                <span className="nav-icon">👤</span>
                <span className="nav-text">Profile</span>
              </button>
              <button 
                className="nav-link mobile"
                onClick={() => handleNavClick('settings')}
              >
                <span className="nav-icon">⚙️</span>
                <span className="nav-text">Settings</span>
              </button>
              <button className="nav-link mobile danger" onClick={handleSignOut}>
                <span className="nav-icon">🚪</span>
                <span className="nav-text">Sign Out</span>
              </button>
            </>
          ) : (
            <button 
              className="nav-link mobile"
              onClick={() => {
                onShowAuth?.();
                setMobileMenuOpen(false);
              }}
            >
              <span className="nav-icon">🔐</span>
              <span className="nav-text">Sign In</span>
            </button>
          )}
        </div>
      )}

      {/* Overlay to close mobile menu */}
      {mobileMenuOpen && (
        <div 
          className="mobile-overlay"
          onClick={() => setMobileMenuOpen(false)}
        ></div>
      )}
    </nav>
  );
};
