import { initializeApp } from 'firebase/app';
import { getFunctions, httpsCallable, connectFunctionsEmulator } from 'firebase/functions';
import { getAuth, GoogleAuthProvider } from 'firebase/auth';
import { getFirestore } from 'firebase/firestore';
import { getStorage } from 'firebase/storage';

const firebaseConfig = {
  apiKey: "AIzaSyCPov0DTRn0HEalOlZ8UJUUmMZjnSne8IU",
  authDomain: "headhunter-ai-0088.firebaseapp.com",
  projectId: "headhunter-ai-0088",
  storageBucket: "headhunter-ai-0088.firebasestorage.app",
  messagingSenderId: "1034162584026",
  appId: "1:1034162584026:web:28ef4ccc012c0de5d828e3"
};

// Firebase configuration is now hardcoded for production

// Initialize Firebase
const app = initializeApp(firebaseConfig);

// Initialize Firebase services
export const auth = getAuth(app);
export const db = getFirestore(app);
export const storage = getStorage(app);
// Configure Google Provider with additional settings
export const googleProvider = new GoogleAuthProvider();
googleProvider.addScope('email');
googleProvider.addScope('profile');
googleProvider.setCustomParameters({
  prompt: 'select_account'
});

// Initialize Functions
export const functions = getFunctions(app, 'us-central1');

// Connect to emulator in development
if (process.env.NODE_ENV === 'development' && process.env.REACT_APP_USE_EMULATOR === 'true') {
  connectFunctionsEmulator(functions, 'localhost', 5001);
}

// Cloud Function references
export const searchCandidates = httpsCallable(functions, 'searchCandidates');
export const getCandidates = httpsCallable(functions, 'getCandidates');
export const createCandidate = httpsCallable(functions, 'createCandidate');
export const generateUploadUrl = httpsCallable(functions, 'generateUploadUrl');
export const healthCheck = httpsCallable(functions, 'healthCheck');
export const completeOnboarding = httpsCallable(functions, 'completeOnboarding');

export default app;