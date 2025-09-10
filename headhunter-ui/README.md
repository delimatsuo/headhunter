# Headhunter AI - React Frontend

A modern React TypeScript application for AI-powered candidate search and recruitment analytics, integrated with Firebase and Google Cloud Platform.

## 🚀 Features

- **Modern React Architecture**: Built with React 19, TypeScript, and functional components
- **Firebase Integration**: Complete authentication system with email/password and Google Sign-In
- **AI-Powered Search**: Advanced candidate matching using job descriptions
- **Professional UI**: Clean, responsive design with comprehensive component library
- **File Upload**: Resume upload functionality with drag-and-drop support
- **Real-time Data**: Live candidate analytics and dashboard insights
- **Mobile-First**: Fully responsive design optimized for all devices

## 📱 Application Structure

```
src/
├── components/
│   ├── Auth/
│   │   ├── Login.tsx           # Email/password login
│   │   ├── Register.tsx        # User registration
│   │   └── AuthModal.tsx       # Authentication modal
│   ├── Candidate/
│   │   └── CandidateCard.tsx   # Candidate profile cards
│   ├── Dashboard/
│   │   └── Dashboard.tsx       # Analytics dashboard
│   ├── Navigation/
│   │   └── Navbar.tsx          # Main navigation
│   ├── Search/
│   │   ├── JobDescriptionForm.tsx  # Search form
│   │   ├── SearchResults.tsx       # Results display
│   │   └── SearchPage.tsx          # Complete search page
│   └── Upload/
│       ├── FileUpload.tsx          # File upload component
│       └── AddCandidateModal.tsx   # Add candidate modal
├── contexts/
│   └── AuthContext.tsx         # Authentication context
├── services/
│   └── api.ts                  # API service layer
├── types/
│   └── index.ts               # TypeScript definitions
├── config/
│   └── firebase.ts            # Firebase configuration
├── App.tsx                    # Main application
├── App.css                    # Application styles
└── index.tsx                  # React entry point
```

## 🎯 Core Components

### Authentication System
- **Login/Register**: Email/password and Google OAuth
- **AuthContext**: Global authentication state management
- **Protected Routes**: Automatic authentication flow

### Candidate Search
- **Job Description Form**: Comprehensive search interface with:
  - Job title and company fields
  - Detailed job description textarea
  - Required and nice-to-have skills management
  - Experience range selectors
  - Leadership requirement toggle
- **Search Results**: Advanced results display with:
  - Candidate ranking and scoring
  - Match rationale and insights
  - Market analysis and recommendations
  - Expandable candidate profiles

### Dashboard & Analytics
- **Statistics Overview**: Key metrics and KPIs
- **Skills Analytics**: Top skills in candidate database
- **Recent Activity**: Latest candidates and searches
- **Quick Actions**: Fast access to common tasks

### File Management
- **Resume Upload**: Drag-and-drop file upload with:
  - Multiple format support (PDF, DOC, DOCX, TXT)
  - Progress tracking and error handling
  - File size and type validation
- **Add Candidate Modal**: Complete candidate creation workflow

## 🔧 Firebase Integration

### Authentication
```typescript
// Email/password and Google Sign-In
const { signIn, signUp, signInWithGoogle, signOut, user } = useAuth();
```

### Cloud Functions
```typescript
// API endpoints integrated
- searchCandidates: AI-powered candidate matching
- getCandidates: Retrieve candidate database
- createCandidate: Add new candidates
- generateUploadUrl: File upload URLs
- healthCheck: System status
```

### Firestore Database
- Real-time candidate data
- Search history and analytics
- User preferences and settings

## 🎨 Design System

### CSS Architecture
- **CSS Custom Properties**: Consistent design tokens
- **Responsive Design**: Mobile-first approach
- **Component-Based Styling**: Modular CSS architecture
- **Accessibility**: WCAG compliant with focus management

### Color Palette
```css
Primary: #2563eb (Professional Blue)
Success: #10b981 (Green)
Warning: #f59e0b (Amber) 
Error: #ef4444 (Red)
Gray Scale: #f9fafb to #111827
```

### Typography
- **Font Stack**: System fonts for optimal performance
- **Hierarchy**: Clear heading structure (h1-h6)
- **Responsive**: Scales appropriately across devices

## 📊 API Integration

### Service Layer
The application includes a comprehensive API service layer (`src/services/api.ts`) that:
- Handles all Cloud Functions communication
- Provides error handling and retry logic
- Manages request/response transformation
- Includes TypeScript interfaces for all endpoints

### Error Handling
- Global error boundaries
- User-friendly error messages
- Retry mechanisms for transient failures
- Loading states for all async operations

## 🚀 Getting Started

### Prerequisites
- Node.js 16+ and npm
- Firebase project with authentication enabled
- Google Cloud Platform project with required APIs

### Installation

1. **Install Dependencies**
```bash
cd headhunter-ui
npm install
```

2. **Environment Configuration**
```bash
# Copy environment template
cp .env.example .env

# Add your Firebase API key
REACT_APP_FIREBASE_API_KEY=your_actual_api_key_here
```

3. **Start Development Server**
```bash
npm start
```

The application will open at `http://localhost:3000`

### Build for Production
```bash
npm run build
```

## 🔐 Environment Variables

```bash
# Required
REACT_APP_FIREBASE_API_KEY=your_firebase_api_key

# Optional Development Settings
REACT_APP_USE_EMULATOR=false  # Use Firebase emulators
NODE_ENV=development          # Environment mode
```

## 🧪 Testing

```bash
# Run all tests
npm test

# Run tests with coverage
npm test -- --coverage

# Run tests in watch mode
npm test -- --watch
```

## Available Scripts

In the project directory, you can run:

### `npm start`

Runs the app in the development mode.\
Open [http://localhost:3000](http://localhost:3000) to view it in the browser.

The page will reload if you make edits.\
You will also see any lint errors in the console.

### `npm test`

Launches the test runner in the interactive watch mode.\
See the section about [running tests](https://facebook.github.io/create-react-app/docs/running-tests) for more information.

### `npm run build`

Builds the app for production to the `build` folder.\
It correctly bundles React in production mode and optimizes the build for the best performance.

The build is minified and the filenames include the hashes.\
Your app is ready to be deployed!

### `npm run eject`

**Note: this is a one-way operation. Once you `eject`, you can't go back!**

## 🏗️ Architecture Decisions

### State Management
- **Context API**: Authentication and global state
- **Local State**: Component-specific state with useState
- **No Redux**: Simplified state management approach

### TypeScript Integration
- **Strict Mode**: Full type safety enabled
- **Interface-First**: All API responses typed
- **Component Props**: Comprehensive prop typing

### Performance Optimizations
- **Code Splitting**: Lazy loading for large components
- **Memoization**: Prevent unnecessary re-renders
- **Optimized Images**: Responsive image handling
- **Bundle Optimization**: Tree shaking and minification

## 📱 Responsive Design

### Breakpoints
- **Mobile**: < 480px
- **Tablet**: 481px - 768px
- **Desktop**: 769px - 1024px
- **Large Desktop**: > 1024px

### Mobile Features
- Touch-optimized interfaces
- Simplified navigation
- Optimized form layouts
- Swipe gestures where appropriate

## 🔒 Security Features

- **Input Validation**: All user inputs sanitized
- **XSS Protection**: DOMPurify integration for content safety
- **CSRF Protection**: Firebase built-in protections
- **Secure Storage**: No sensitive data in localStorage

## 🌐 Browser Support

- **Modern Browsers**: Chrome 88+, Firefox 85+, Safari 14+, Edge 88+
- **ES2020 Features**: Full modern JavaScript support
- **CSS Grid/Flexbox**: Modern layout techniques
- **Web Standards**: Progressive enhancement approach

## 📄 Learn More

You can learn more in the [Create React App documentation](https://facebook.github.io/create-react-app/docs/getting-started).

To learn React, check out the [React documentation](https://reactjs.org/).

For Firebase integration, see the [Firebase documentation](https://firebase.google.com/docs).

## 📄 License

This project is part of the Headhunter AI system. All rights reserved.