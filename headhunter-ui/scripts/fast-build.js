#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const srcDir = path.join(__dirname, '..', 'src');
const buildDir = path.join(__dirname, '..', 'build');
const publicDir = path.join(__dirname, '..', 'public');

console.log('🚀 Starting fast build process...');

// Clean build directory
if (fs.existsSync(buildDir)) {
  fs.rmSync(buildDir, { recursive: true });
}
fs.mkdirSync(buildDir, { recursive: true });

// Copy public assets
console.log('📁 Copying public assets...');
execSync(`cp -r "${publicDir}"/* "${buildDir}"/`, { stdio: 'inherit' });

// Create a simple index.html with inline styles and scripts
const indexTemplate = `<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <link rel="icon" href="/favicon.ico" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta name="theme-color" content="#000000" />
    <meta name="description" content="Headhunter AI - Recruitment Analytics" />
    <title>Headhunter AI</title>
    <style>
      /* Critical CSS inline */
      * { margin: 0; padding: 0; box-sizing: border-box; }
      body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }
      .loading { display: flex; justify-content: center; align-items: center; height: 100vh; }
    </style>
  </head>
  <body>
    <noscript>You need to enable JavaScript to run this app.</noscript>
    <div id="root">
      <div class="loading">Loading Headhunter AI...</div>
    </div>
    <script src="/static/js/bundle.js"></script>
  </body>
</html>`;

fs.writeFileSync(path.join(buildDir, 'index.html'), indexTemplate);

// Create static directories
const staticDir = path.join(buildDir, 'static');
const jsDir = path.join(staticDir, 'js');
const cssDir = path.join(staticDir, 'css');

fs.mkdirSync(staticDir, { recursive: true });
fs.mkdirSync(jsDir, { recursive: true });
fs.mkdirSync(cssDir, { recursive: true });

console.log('⚡ Building JavaScript bundle...');

// Simple webpack config for fast build
const webpackConfig = `
const path = require('path');

module.exports = {
  mode: 'development',
  entry: './src/index.tsx',
  output: {
    path: path.resolve(__dirname, 'build/static/js'),
    filename: 'bundle.js',
    publicPath: '/static/js/',
  },
  resolve: {
    extensions: ['.tsx', '.ts', '.js', '.jsx'],
  },
  module: {
    rules: [
      {
        test: /\.(ts|tsx)$/,
        use: [
          {
            loader: 'ts-loader',
            options: {
              transpileOnly: true,
              compilerOptions: {
                jsx: 'react-jsx',
                target: 'es2015',
                lib: ['dom', 'es2015'],
                allowSyntheticDefaultImports: true,
                esModuleInterop: true,
                skipLibCheck: true,
              },
            },
          },
        ],
        exclude: /node_modules/,
      },
      {
        test: /\.css$/,
        use: ['style-loader', 'css-loader'],
      },
      {
        test: /\.(png|jpe?g|gif|svg)$/,
        type: 'asset/resource',
      },
    ],
  },
  devtool: 'source-map',
  stats: 'minimal',
};
`;

fs.writeFileSync(path.join(__dirname, '..', 'webpack.fast.js'), webpackConfig);

// Run webpack
try {
  execSync('npx webpack --config webpack.fast.js', { 
    cwd: path.join(__dirname, '..'),
    stdio: 'inherit' 
  });
  console.log('✅ Fast build completed successfully!');
} catch (error) {
  console.error('❌ Build failed:', error.message);
  process.exit(1);
}