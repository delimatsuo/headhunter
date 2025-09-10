import React, { createContext, useContext, useState, useEffect } from 'react';
import {
  User,
  onAuthStateChanged,
  signInWithPopup,
  signOut as firebaseSignOut,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
} from 'firebase/auth';
import { auth, googleProvider, completeOnboarding } from '../config/firebase';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signInWithGoogle: () => Promise<void>;
  signUp: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (user) => {
      setUser(user);
      setLoading(false);
    });

    return unsubscribe;
  }, []);

  const signIn = async (email: string, password: string) => {
    try {
      const result = await signInWithEmailAndPassword(auth, email, password);
      
      // Complete onboarding for users without org access
      try {
        const token = await result.user.getIdToken(true);
        const decodedToken = JSON.parse(atob(token.split('.')[1]));
        
        // If user doesn't have org_id claim, complete onboarding
        if (!decodedToken.org_id) {
          console.log('Completing onboarding for existing user...');
          const onboardingResult = await completeOnboarding({
            displayName: result.user.displayName,
          });
          console.log('Onboarding completed:', onboardingResult.data);
          
          // Force token refresh to get new custom claims
          await result.user.getIdToken(true);
        }
      } catch (onboardingError) {
        console.warn('Onboarding error:', onboardingError);
        // Don't throw here - user is still authenticated
      }
      
    } catch (error) {
      console.error('Error signing in:', error);
      throw error;
    }
  };

  const signInWithGoogle = async () => {
    try {
      const result = await signInWithPopup(auth, googleProvider);
      console.log('User signed in:', result.user.email);
      
      // Complete onboarding for new or existing users without org access
      try {
        const token = await result.user.getIdToken(true);
        const decodedToken = JSON.parse(atob(token.split('.')[1]));
        
        // If user doesn't have org_id claim, complete onboarding
        if (!decodedToken.org_id) {
          console.log('Completing onboarding for new user...');
          const onboardingResult = await completeOnboarding({
            displayName: result.user.displayName,
          });
          console.log('Onboarding completed:', onboardingResult.data);
          
          // Force token refresh to get new custom claims
          await result.user.getIdToken(true);
        }
      } catch (onboardingError) {
        console.warn('Onboarding error:', onboardingError);
        // Don't throw here - user is still authenticated
      }
      
    } catch (error) {
      console.error('Error signing in with Google:', error);
      throw error;
    }
  };

  const signUp = async (email: string, password: string) => {
    try {
      await createUserWithEmailAndPassword(auth, email, password);
    } catch (error) {
      console.error('Error signing up:', error);
      throw error;
    }
  };

  const signOut = async () => {
    try {
      await firebaseSignOut(auth);
      console.log('User signed out');
    } catch (error) {
      console.error('Error signing out:', error);
      throw error;
    }
  };

  const value = {
    user,
    loading,
    signIn,
    signInWithGoogle,
    signUp,
    signOut
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};