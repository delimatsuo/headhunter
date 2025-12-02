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
import Container from '@mui/material/Container';
import Divider from '@mui/material/Divider';
import ListItemIcon from '@mui/material/ListItemIcon';
import Tooltip from '@mui/material/Tooltip';
import Badge from '@mui/material/Badge';

// Icons
import DashboardIcon from '@mui/icons-material/DashboardRounded';
import SearchIcon from '@mui/icons-material/SearchRounded';
import PeopleIcon from '@mui/icons-material/PeopleRounded';
import AnalyticsIcon from '@mui/icons-material/BarChartRounded';
import AdminPanelSettingsIcon from '@mui/icons-material/AdminPanelSettingsRounded';
import NotificationsIcon from '@mui/icons-material/NotificationsNoneRounded';
import SettingsIcon from '@mui/icons-material/SettingsRounded';
import LogoutIcon from '@mui/icons-material/LogoutRounded';
import PersonIcon from '@mui/icons-material/PersonRounded';

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
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);

  // Icon mapping
  const getIcon = (name: string) => {
    switch (name) {
      case 'Dashboard': return <DashboardIcon fontSize="small" />;
      case 'Search': return <SearchIcon fontSize="small" />;
      case 'Candidates': return <PeopleIcon fontSize="small" />;
      case 'Analytics': return <AnalyticsIcon fontSize="small" />;
      case 'Admin': return <AdminPanelSettingsIcon fontSize="small" />;
      default: return <DashboardIcon fontSize="small" />;
    }
  };

  const baseItems: NavItem[] = [
    { name: 'Dashboard', path: 'dashboard', icon: '🏠' },
    { name: 'Search', path: 'search', icon: '🔍' }
  ];

  let role: string | undefined;
  try {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const token = (user as any)?.stsTokenManager?.accessToken || undefined;
    if (token) {
      const payload = JSON.parse(atob(token.split('.')[1]));
      role = payload.role || payload.custom_role;
    }
  } catch { }

  const navItems: NavItem[] = role === 'admin' || role === 'super_admin'
    ? [...baseItems, { name: 'Admin', path: 'admin', icon: '🛡️' }]
    : baseItems;

  const handleSignOut = async () => {
    try {
      await signOut();
      setAnchorEl(null);
    } catch (error) {
      console.error('Error signing out:', error);
    }
  };

  return (
    <AppBar position="sticky" color="default" elevation={0} sx={{ borderBottom: '1px solid', borderColor: 'divider', bgcolor: 'background.paper' }}>
      <Container maxWidth="xl">
        <Toolbar disableGutters sx={{ height: 70 }}>
          {/* Logo Section */}
          <Box sx={{ display: 'flex', alignItems: 'center', mr: 4, cursor: 'pointer' }} onClick={() => onNavigate('dashboard')}>
            <Typography variant="h5" noWrap sx={{
              fontWeight: 800,
              letterSpacing: '-0.5px',
              background: 'linear-gradient(45deg, #0F172A 30%, #10B981 90%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              display: 'flex',
              alignItems: 'center'
            }}>
              Ella
            </Typography>
          </Box>

          {/* Navigation Links */}
          {user && (
            <Box sx={{ flexGrow: 1, display: { xs: 'none', md: 'flex' }, gap: 1 }}>
              {navItems.map((item) => {
                const isActive = currentPage === item.path;
                return (
                  <Button
                    key={item.path}
                    onClick={() => onNavigate(item.path)}
                    startIcon={getIcon(item.name)}
                    sx={{
                      my: 2,
                      color: isActive ? 'primary.main' : 'text.secondary',
                      bgcolor: isActive ? 'primary.50' : 'transparent',
                      fontWeight: isActive ? 600 : 500,
                      px: 2,
                      '&:hover': {
                        bgcolor: isActive ? 'primary.100' : 'action.hover',
                        color: 'primary.main',
                      },
                    }}
                  >
                    {item.name}
                  </Button>
                );
              })}
            </Box>
          )}

          {/* Right Side Actions */}
          <Box sx={{ flexGrow: 0, display: 'flex', alignItems: 'center', gap: 2 }}>
            {user ? (
              <>
                <Tooltip title="Notifications">
                  <IconButton size="small" sx={{ color: 'text.secondary' }}>
                    <Badge badgeContent={3} color="error" variant="dot">
                      <NotificationsIcon />
                    </Badge>
                  </IconButton>
                </Tooltip>

                <Box sx={{ height: 24, width: 1, bgcolor: 'divider' }} />

                <Tooltip title="Account settings">
                  <IconButton
                    onClick={(e) => setAnchorEl(e.currentTarget)}
                    size="small"
                    sx={{
                      ml: 0.5,
                      border: '2px solid',
                      borderColor: 'primary.light',
                      p: 0.5
                    }}
                  >
                    <Avatar
                      src={user.photoURL || undefined}
                      alt={user.displayName || user.email || 'User'}
                      sx={{ width: 32, height: 32 }}
                    >
                      {(user.displayName || user.email || 'U')[0].toUpperCase()}
                    </Avatar>
                  </IconButton>
                </Tooltip>

                <Menu
                  anchorEl={anchorEl}
                  id="account-menu"
                  open={Boolean(anchorEl)}
                  onClose={() => setAnchorEl(null)}
                  onClick={() => setAnchorEl(null)}
                  PaperProps={{
                    elevation: 0,
                    sx: {
                      overflow: 'visible',
                      filter: 'drop-shadow(0px 2px 8px rgba(0,0,0,0.32))',
                      mt: 1.5,
                      width: 220,
                      '& .MuiAvatar-root': {
                        width: 32,
                        height: 32,
                        ml: -0.5,
                        mr: 1,
                      },
                      '&:before': {
                        content: '""',
                        display: 'block',
                        position: 'absolute',
                        top: 0,
                        right: 14,
                        width: 10,
                        height: 10,
                        bgcolor: 'background.paper',
                        transform: 'translateY(-50%) rotate(45deg)',
                        zIndex: 0,
                      },
                    },
                  }}
                  transformOrigin={{ horizontal: 'right', vertical: 'top' }}
                  anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
                >
                  <Box sx={{ px: 2, py: 1.5 }}>
                    <Typography variant="subtitle2" noWrap>
                      {user.displayName || 'User'}
                    </Typography>
                    <Typography variant="body2" color="text.secondary" noWrap sx={{ fontSize: '0.75rem' }}>
                      {user.email}
                    </Typography>
                  </Box>
                  <Divider />
                  <MenuItem onClick={() => onNavigate('profile')}>
                    <ListItemIcon>
                      <PersonIcon fontSize="small" />
                    </ListItemIcon>
                    Profile
                  </MenuItem>
                  <MenuItem onClick={() => onNavigate('settings')}>
                    <ListItemIcon>
                      <SettingsIcon fontSize="small" />
                    </ListItemIcon>
                    Settings
                  </MenuItem>
                  <Divider />
                  <MenuItem onClick={handleSignOut} sx={{ color: 'error.main' }}>
                    <ListItemIcon>
                      <LogoutIcon fontSize="small" color="error" />
                    </ListItemIcon>
                    Sign Out
                  </MenuItem>
                </Menu>
              </>
            ) : (
              <Button
                variant="contained"
                color="primary"
                onClick={onShowAuth}
                sx={{ borderRadius: 20, px: 3 }}
              >
                Sign In
              </Button>
            )}
          </Box>
        </Toolbar>
      </Container>
    </AppBar >
  );
};
