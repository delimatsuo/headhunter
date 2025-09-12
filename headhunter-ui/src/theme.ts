import { createTheme } from '@mui/material/styles';

// Brand palette inspired by Ella Executive Search logo (green)
const theme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#22c55e',
    },
    secondary: {
      main: '#0ea5e9',
    },
    background: {
      default: '#f8fafc',
      paper: '#ffffff',
    },
  },
  shape: {
    borderRadius: 10,
  },
});

export default theme;

