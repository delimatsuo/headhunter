import { initializeApp } from 'firebase/app';
import { getFunctions, httpsCallable, connectFunctionsEmulator } from 'firebase/functions';
import { getAuth, GoogleAuthProvider, signInWithPopup, signOut, onAuthStateChanged, User } from 'firebase/auth';

const firebaseConfig = {
  apiKey: process.env.REACT_APP_FIREBASE_API_KEY,
  authDomain: "headhunter-ai-0088.firebaseapp.com",
  projectId: "headhunter-ai-0088",
  storageBucket: "headhunter-ai-0088-profiles",
  messagingSenderId: "1034162584026",
  appId: "1:1034162584026:web:9a8e7f6d5c4f3b2e1a9c8d"
};

if (!firebaseConfig.apiKey) {
  throw new Error('Firebase API key not configured. Please set REACT_APP_FIREBASE_API_KEY environment variable.');
}

// Initialize Firebase
const app = initializeApp(firebaseConfig);

// Initialize Auth
export const auth = getAuth(app);
export const googleProvider = new GoogleAuthProvider();

// Initialize Functions
export const functions = getFunctions(app, 'us-central1');

// Connect to emulator in development
if (process.env.NODE_ENV === 'development' && process.env.REACT_APP_USE_EMULATOR === 'true') {
  connectFunctionsEmulator(functions, 'localhost', 5001);
}

// Cloud Function references
export const searchJobCandidates = httpsCallable(functions, 'searchJobCandidates');
export const quickMatch = httpsCallable(functions, 'quickMatch');
export const healthCheck = httpsCallable(functions, 'healthCheck');

export default app;