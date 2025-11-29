import { createTheme, alpha } from '@mui/material/styles';

// Premium Color Palette
const palette = {
  primary: {
    main: '#0F172A', // Deep Navy (Slate 900)
    light: '#334155', // Slate 700
    dark: '#020617', // Slate 950
    contrastText: '#ffffff',
  },
  secondary: {
    main: '#10B981', // Emerald 500
    light: '#34D399', // Emerald 400
    dark: '#059669', // Emerald 600
    contrastText: '#ffffff',
  },
  background: {
    default: '#F8FAFC', // Slate 50
    paper: '#FFFFFF',
  },
  text: {
    primary: '#1E293B', // Slate 800
    secondary: '#64748B', // Slate 500
  },
  divider: '#E2E8F0', // Slate 200
};

const theme = createTheme({
  palette,
  typography: {
    fontFamily: '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
    h1: { fontWeight: 700, letterSpacing: '-0.025em' },
    h2: { fontWeight: 700, letterSpacing: '-0.025em' },
    h3: { fontWeight: 600, letterSpacing: '-0.025em' },
    h4: { fontWeight: 600, letterSpacing: '-0.025em' },
    h5: { fontWeight: 600 },
    h6: { fontWeight: 600 },
    button: { textTransform: 'none', fontWeight: 600 },
  },
  shape: {
    borderRadius: 12,
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          padding: '8px 16px',
          boxShadow: 'none',
          '&:hover': {
            boxShadow: 'none',
          },
        },
        containedPrimary: {
          '&:hover': {
            backgroundColor: palette.primary.light,
          },
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: 16,
          boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)',
          border: '1px solid',
          borderColor: palette.divider,
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        elevation1: {
          boxShadow: '0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)',
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          backgroundColor: '#ffffff',
          color: palette.text.primary,
          borderBottom: `1px solid ${palette.divider}`,
          boxShadow: 'none',
        },
      },
    },
    MuiTextField: {
      styleOverrides: {
        root: {
          '& .MuiOutlinedInput-root': {
            borderRadius: 8,
          },
        },
      },
    },
  },
});

export default theme;
