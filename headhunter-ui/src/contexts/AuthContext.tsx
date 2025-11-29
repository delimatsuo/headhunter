import React, { createContext, useContext, useState, useEffect } from 'react';
import {
  User,
  onAuthStateChanged,
  signInWithPopup,
  signOut as firebaseSignOut,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
} from 'firebase/auth';
import { doc, getDoc } from 'firebase/firestore';
import { auth, googleProvider, completeOnboarding, db } from '../config/firebase';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signInWithGoogle: () => Promise<void>;
  signUp: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Allowed email domains for authentication
const ALLOWED_DOMAINS = ['ella.com.br', 'ellaexecutivesearch.com'];

/**
 * Validates if the email domain is in the allowed list
 */
const isAllowedDomain = (email: string | null): boolean => {
  if (!email) return false;
  const domain = email.split('@')[1]?.toLowerCase();
  return ALLOWED_DOMAINS.includes(domain);
};

/**
 * Checks if user exists in the allowed_users collection
 */
const isUserAllowed = async (email: string): Promise<boolean> => {
  try {
    const userDoc = await getDoc(doc(db, 'allowed_users', email.toLowerCase()));
    return userDoc.exists();
  } catch (error) {
    console.error('Error checking allowed users:', error);
    return false;
  }
};

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
    const unsubscribe = onAuthStateChanged(auth, async (user) => {
      if (user) {
        try {
          // Check for custom claims
          const token = await user.getIdTokenResult();
          const hasOrgId = !!token.claims.org_id;

          if (!hasOrgId) {
            console.log('User missing org_id claim, attempting auto-repair...');
            try {
              await completeOnboarding({
                displayName: user.displayName,
              });
              // Force token refresh
              await user.getIdToken(true);
              console.log('Auto-repair successful');
            } catch (repairError) {
              console.error('Auto-repair failed:', repairError);
            }
          }
        } catch (error) {
          console.error('Error checking user claims:', error);
        }
      }
      setUser(user);
      setLoading(false);
    });

    return unsubscribe;
  }, []);

  const signIn = async (email: string, password: string) => {
    let result: any = null;

    try {
      // Validate domain before attempting sign-in
      if (!isAllowedDomain(email)) {
        throw new Error(
          `Access denied: Only @ella.com.br and @ellaexecutivesearch.com email addresses are allowed. Your domain: @${email.split('@')[1] || 'unknown'}`
        );
      }

      result = await signInWithEmailAndPassword(auth, email, password);

      // Check if user is in allowed_users collection
      // const isAllowed = await isUserAllowed(email);
      // if (!isAllowed) {
      //   await firebaseSignOut(auth);
      //   throw new Error(
      //     'Access denied: Your email address is not authorized. Please contact your administrator to request access.'
      //   );
      // }

      // Complete onboarding for users without org access
      try {
        const token = await result.user.getIdToken(true);
        const decodedToken = JSON.parse(atob(token.split('.')[1]));

        // If user doesn't have org_id claim, complete onboarding
        // Force onboarding check to ensure permissions are up to date
        // if (!decodedToken.org_id) {
        console.log('Completing onboarding/repair for user...');
        const onboardingResult = await completeOnboarding({
          displayName: result.user.displayName,
        });
        console.log('Onboarding/repair completed:', onboardingResult.data);

        // Force token refresh to get new custom claims
        await result.user.getIdToken(true);
        // }
      } catch (onboardingError) {
        console.warn('Onboarding error:', onboardingError);
        // Don't throw here - user is still authenticated
      }

    } catch (error: any) {
      console.error('Error signing in:', error);
      // If user signed in but failed validation, ensure they're signed out
      if (result && error.message.includes('Access denied')) {
        try {
          await firebaseSignOut(auth);
        } catch (signOutError) {
          console.error('Error signing out unauthorized user:', signOutError);
        }
      }
      throw error;
    }
  };

  const signInWithGoogle = async () => {
    let userResult: any = null;

    try {
      userResult = await signInWithPopup(auth, googleProvider);
      const userEmail = userResult.user.email;
      console.log('User signed in:', userEmail);

      // Validate domain
      if (!isAllowedDomain(userEmail)) {
        await firebaseSignOut(auth);
        throw new Error(
          `Access denied: Only @ella.com.br and @ellaexecutivesearch.com email addresses are allowed. Your domain: @${userEmail?.split('@')[1] || 'unknown'}`
        );
      }

      // Check if user is in allowed_users collection
      if (userEmail) {
        // const isAllowed = await isUserAllowed(userEmail);
        // if (!isAllowed) {
        //   await firebaseSignOut(auth);
        //   throw new Error(
        //     'Access denied: Your email address is not authorized. Please contact your administrator to request access.'
        //   );
        // }
      }

      // Complete onboarding for new or existing users without org access
      try {
        const token = await userResult.user.getIdToken(true);
        const decodedToken = JSON.parse(atob(token.split('.')[1]));

        // If user doesn't have org_id claim, complete onboarding
        // Force onboarding check to ensure permissions are up to date
        // if (!decodedToken.org_id) {
        console.log('Completing onboarding/repair for authorized user...');
        const onboardingResult = await completeOnboarding({
          displayName: userResult.user.displayName,
        });
        console.log('Onboarding/repair completed:', onboardingResult.data);

        // Force token refresh to get new custom claims
        await userResult.user.getIdToken(true);
        // }
      } catch (onboardingError) {
        console.warn('Onboarding error:', onboardingError);
        // Don't throw here - user is still authenticated
      }

    } catch (error: any) {
      console.error('Error signing in with Google:', error);
      // If user signed in but failed validation, ensure they're signed out
      if (userResult && error.message.includes('Access denied')) {
        try {
          await firebaseSignOut(auth);
        } catch (signOutError) {
          console.error('Error signing out unauthorized user:', signOutError);
        }
      }
      throw error;
    }
  };

  const signUp = async (email: string, password: string) => {
    try {
      // Validate domain before attempting sign-up
      if (!isAllowedDomain(email)) {
        throw new Error(
          `Access denied: Only @ella.com.br and @ellaexecutivesearch.com email addresses are allowed for registration. Your domain: @${email.split('@')[1] || 'unknown'}`
        );
      }

      // Note: User must be added to allowed_users collection by an admin before they can actually sign in
      // This creates the Firebase Auth account, but they won't pass the allowed_users check until added
      await createUserWithEmailAndPassword(auth, email, password);

      // Sign out immediately after registration - they need admin approval
      await firebaseSignOut(auth);

      throw new Error(
        'Registration successful! However, your account needs administrator approval before you can sign in. Please contact your administrator.'
      );
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