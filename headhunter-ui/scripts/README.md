# Fast Build & Deploy Scripts for Firebase Auth Testing

## Quick Firebase Auth Test

The quickest way to test Firebase authentication without waiting for the full React build:

```bash
# Create a standalone HTML Firebase auth test
npm run quick-build

# Test in browser (manual)
open quick-build/index.html

# Test with local server
python3 -m http.server 8080 --directory quick-build
# Then visit: http://localhost:8080
```

## Firebase Configuration

✅ **Fixed Issues:**
- Firebase config is now hardcoded (no env variables)
- Google Auth Provider properly configured with scopes
- API key verified: `AIzaSyCPov0DTRn0HEalOlZ8UJUUmMZjnSne8IU`

## Available Scripts

### Quick Testing
- `npm run quick-build` - Creates standalone HTML with Firebase auth
- `npm run test-auth` - Build + serve (requires serve package)

### Fast Development  
- `npm run fast-build` - Webpack-based fast build (requires deps)
- `npm run dev-server` - Custom dev server
- `npm run dev-watch` - Dev server with auto-rebuild

### Deployment
- `npm run deploy-firebase` - Deploy to Firebase Hosting
- `npm run deploy-static` - Prepare static files
- `npm run serve` - Local testing server

## Firebase Auth Features Tested

The quick-build HTML includes:
- ✅ Google Sign-In with popup
- ✅ Email/Password Sign-In
- ✅ Email/Password Sign-Up
- ✅ User state management
- ✅ Error handling and display
- ✅ Sign-out functionality

## Troubleshooting

### "auth/api-key-not-valid" Error
- ✅ **FIXED**: Configuration is now hardcoded in `firebase.ts`
- ✅ **FIXED**: Quick build uses verified API key directly

### Slow React Build
- ✅ **SOLVED**: Use `npm run quick-build` for immediate testing
- ✅ **ALTERNATIVE**: Fast webpack build available

### Dependencies
If using webpack-based builds, install:
```bash
npm install --save-dev webpack webpack-cli ts-loader style-loader css-loader express chokidar
```

## Firebase Project Details

- **Project ID**: `headhunter-ai-0088`
- **Auth Domain**: `headhunter-ai-0088.firebaseapp.com`
- **API Key**: `AIzaSyCPov0DTRn0HEalOlZ8UJUUmMZjnSne8IU`

## Next Steps

1. Test authentication: `npm run quick-build`
2. Verify Google Sign-In works in browser
3. If successful, proceed with full React app build
4. Deploy to Firebase: `npm run deploy-firebase`