#!/usr/bin/env node

const { execSync } = require('child_process');
const path = require('path');
const fs = require('fs');

const buildDir = path.join(__dirname, '..', 'build');

console.log('🚀 Starting deployment process...');

// Check if build exists
if (!fs.existsSync(buildDir)) {
  console.log('📦 Build directory not found, running fast build...');
  execSync('node scripts/fast-build.js', { 
    cwd: path.join(__dirname, '..'),
    stdio: 'inherit' 
  });
}

// Deployment options
const deploymentMethod = process.argv[2] || 'firebase';

switch (deploymentMethod) {
  case 'firebase':
    console.log('🔥 Deploying to Firebase Hosting...');
    try {
      // Initialize Firebase if needed
      if (!fs.existsSync(path.join(__dirname, '..', 'firebase.json'))) {
        console.log('🔧 Creating Firebase config...');
        const firebaseConfig = {
          hosting: {
            public: 'build',
            ignore: ['firebase.json', '**/.*', '**/node_modules/**'],
            rewrites: [
              {
                source: '**',
                destination: '/index.html'
              }
            ],
            headers: [
              {
                source: '/service-worker.js',
                headers: [
                  {
                    key: 'Cache-Control',
                    value: 'no-cache'
                  }
                ]
              }
            ]
          }
        };
        fs.writeFileSync(
          path.join(__dirname, '..', 'firebase.json'), 
          JSON.stringify(firebaseConfig, null, 2)
        );
      }
      
      execSync('firebase deploy --only hosting', { 
        cwd: path.join(__dirname, '..'),
        stdio: 'inherit' 
      });
      console.log('✅ Firebase deployment completed!');
    } catch (error) {
      console.error('❌ Firebase deployment failed:', error.message);
      process.exit(1);
    }
    break;

  case 'static':
    console.log('📁 Preparing static files for manual deployment...');
    const deployDir = path.join(__dirname, '..', 'deploy');
    
    if (fs.existsSync(deployDir)) {
      fs.rmSync(deployDir, { recursive: true });
    }
    
    execSync(`cp -r "${buildDir}" "${deployDir}"`, { stdio: 'inherit' });
    
    console.log('📋 Static deployment ready!');
    console.log(`   Upload the contents of: ${deployDir}`);
    console.log('   To your web server\'s document root');
    break;

  case 'serve':
    console.log('🌐 Starting local server for testing...');
    execSync('node scripts/dev-server.js', { 
      cwd: path.join(__dirname, '..'),
      stdio: 'inherit' 
    });
    break;

  default:
    console.log('❌ Unknown deployment method:', deploymentMethod);
    console.log('Usage: node deploy.js [firebase|static|serve]');
    process.exit(1);
}