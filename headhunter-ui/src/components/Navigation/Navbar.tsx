import React, { useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { NavItem } from '../../types';
import AppBar from '@mui/material/AppBar';
import Toolbar from '@mui/material/Toolbar';
import IconButton from '@mui/material/IconButton';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';
import Box from '@mui/material/Box';
import Avatar from '@mui/material/Avatar';
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';

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

  const baseItems: NavItem[] = [
    { name: 'Dashboard', path: 'dashboard', icon: '🏠' },
    { name: 'Search', path: 'search', icon: '🔍' },
    { name: 'Candidates', path: 'candidates', icon: '👥' },
    { name: 'Analytics', path: 'analytics', icon: '📊' }
  ];

  let role: string | undefined;
  try {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const token = (user as any)?.stsTokenManager?.accessToken || undefined;
    if (token) {
      const payload = JSON.parse(atob(token.split('.')[1]));
      role = payload.role || payload.custom_role;
    }
  } catch {}

  const navItems: NavItem[] = role === 'admin' || role === 'super_admin'
    ? [...baseItems, { name: 'Admin', path: 'admin', icon: '🛡️' }]
    : baseItems;

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
    <AppBar position="sticky" color="inherit" elevation={1}>
      <Toolbar sx={{ maxWidth: 1200, mx: 'auto', width: '100%' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', flexGrow: 1 }}>
          <Box component="img" src="/ella-logo.png" alt="Ella Executive Search" sx={{ height: 28, mr: 1, cursor: 'pointer' }} onClick={() => handleNavClick('dashboard')} />
          <Typography variant="h6" sx={{ fontWeight: 600, cursor: 'pointer' }} onClick={() => handleNavClick('dashboard')}>
            Ella Executive Search
          </Typography>
        </Box>

        {user ? (
          <Box sx={{ display: { xs: 'none', md: 'flex' }, gap: 1, mr: 2 }}>
            {navItems.map((item) => (
              <Button key={item.path} color={currentPage === item.path ? 'primary' : 'inherit'} onClick={() => handleNavClick(item.path)} startIcon={<span>{item.icon}</span>}>
                {item.name}
              </Button>
            ))}
          </Box>
        ) : (
          <Typography variant="body2" sx={{ color: 'text.secondary', mr: 2, display: { xs: 'none', md: 'block' } }}>
            Welcome to Ella Executive Search
          </Typography>
        )}

        {/* User Menu */}
        {user ? (
          <Box>
            <IconButton onClick={() => setShowUserMenu(!showUserMenu)} size="small">
              <Avatar src={user.photoURL || undefined} alt={user.displayName || user.email || 'User'}>
                {(user.displayName || user.email || 'U')[0].toUpperCase()}
              </Avatar>
            </IconButton>
            <Menu
              anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
              transformOrigin={{ vertical: 'top', horizontal: 'right' }}
              open={showUserMenu}
              onClose={() => setShowUserMenu(false)}
            >
              <MenuItem onClick={() => { handleNavClick('profile'); setShowUserMenu(false); }}>Profile</MenuItem>
              <MenuItem onClick={() => { handleNavClick('settings'); setShowUserMenu(false); }}>Settings</MenuItem>
              <MenuItem onClick={() => { handleSignOut(); setShowUserMenu(false); }}>Sign Out</MenuItem>
            </Menu>
          </Box>
        ) : (
          <Button variant="contained" color="primary" onClick={onShowAuth}>Sign In</Button>
        )}
      </Toolbar>
    </AppBar>
  );
};
