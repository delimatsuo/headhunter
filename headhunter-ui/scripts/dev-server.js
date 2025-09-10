#!/usr/bin/env node

const express = require('express');
const path = require('path');
const { execSync } = require('child_process');
const fs = require('fs');

const app = express();
const PORT = process.env.PORT || 3000;

console.log('🚀 Starting development server...');

// Serve static files
app.use('/static', express.static(path.join(__dirname, '..', 'build', 'static')));
app.use(express.static(path.join(__dirname, '..', 'build')));

// Handle React routing
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, '..', 'build', 'index.html'));
});

// Auto-rebuild on file changes (simple file watcher)
if (process.argv.includes('--watch')) {
  const chokidar = require('chokidar');
  const watcher = chokidar.watch(path.join(__dirname, '..', 'src'), {
    ignored: /node_modules/,
    persistent: true
  });
  
  watcher.on('change', () => {
    console.log('📝 File changed, rebuilding...');
    try {
      execSync('node scripts/fast-build.js', { 
        cwd: path.join(__dirname, '..'),
        stdio: 'inherit' 
      });
    } catch (error) {
      console.error('❌ Rebuild failed:', error.message);
    }
  });
}

app.listen(PORT, () => {
  console.log(`✅ Server running at http://localhost:${PORT}`);
  console.log('🔥 Hot reload: Use --watch flag for auto-rebuild');
});