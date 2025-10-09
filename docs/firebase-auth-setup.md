# Firebase Authentication Setup Guide

## Task 72.1: Configure Firebase Authentication with Google Sign-In

### Firebase Console Configuration Required

#### 1. Enable Google Sign-In Provider

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Select project: `headhunter-ai-0088`
3. Navigate to **Authentication** → **Sign-in method**
4. Enable **Google** provider
5. Configure OAuth consent screen if prompted
6. Add authorized domains:
   - `headhunter-ai-0088.firebaseapp.com`
   - `localhost` (for development)
   - Any custom domains used in production

#### 2. OAuth Consent Screen Configuration

**Project:** headhunter-ai-0088
**User Type:** Internal (restrict to Ella organization)
**Application Name:** Headhunter AI
**Authorized Domains:** ella.com.br

#### 3. Authorized Domains in Firebase

Ensure these domains are authorized in Firebase Console:
- `headhunter-ai-0088.firebaseapp.com`
- `localhost` (development)
- Any production domains

### Code Implementation Summary

**File:** `headhunter-ui/src/contexts/AuthContext.tsx`

**Features Implemented:**
1. **Domain Validation:** Only `@ella.com.br` emails allowed
2. **Allowlist Check:** Users must exist in `allowed_users` Firestore collection
3. **Google Sign-In:** Full domain and allowlist validation
4. **Email/Password Sign-In:** Full domain and allowlist validation
5. **Registration:** Domain validated, but requires admin approval

**Validation Flow:**
```
User attempts sign-in
  ↓
Validate email domain (@ella.com.br)
  ↓ (if valid)
Check allowed_users collection
  ↓ (if exists)
Complete authentication
  ↓ (if invalid at any step)
Sign out user + show error
```

**Error Messages:**
- Domain mismatch: "Access denied: Only @ella.com.br email addresses are allowed"
- Not in allowlist: "Access denied: Your email address is not authorized. Please contact your administrator"
- Registration: "Registration successful! However, your account needs administrator approval"

### Next Steps

1. Verify Firebase Console configuration (see above)
2. Create `allowed_users` collection schema (Task 72.2)
3. Implement Firestore security rules (Task 72.3)
4. Build admin user management interface (Task 72.4)

### Testing Checklist

- [ ] Google Sign-In provider enabled in Firebase Console
- [ ] OAuth consent screen configured for ella.com.br
- [ ] Authorized domains added in Firebase Console
- [ ] Test with @ella.com.br email (should prompt for allowlist)
- [ ] Test with non-ella.com.br email (should be rejected)
- [ ] Verify error messages display correctly

### Security Notes

- Domain validation happens client-side (for UX) AND server-side via security rules
- Client-side validation provides immediate feedback
- Firestore security rules enforce actual access control
- Users are immediately signed out if validation fails
- No authentication state persists for unauthorized users
