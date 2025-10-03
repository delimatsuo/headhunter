#!/usr/bin/env python3
"""
Candidate Data CRUD Viewer
Visualize and analyze candidate data at different processing stages
"""

from flask import Flask, jsonify, render_template, request
import json
import csv
import os
from pathlib import Path
from typing import Any, Dict
from datetime import datetime

from data_paths import csv_dir, repo_root, resumes_dir

app = Flask(__name__)

# Data directories
REPO_ROOT = repo_root()
CSV_DIR = csv_dir()
RESUME_DIR = resumes_dir()
# Check both local and NAS for processed data
NAS_DIR = Path(os.getenv(
    "HEADHUNTER_NAS_DIR",
    "/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project",
))
PROCESSED_DIR = Path(os.getenv("HEADHUNTER_PROCESSED_DIR", str(NAS_DIR / "processed_candidates")))
LOCAL_PROCESSED_DIR = Path(os.getenv(
    "HEADHUNTER_LOCAL_PROCESSED_DIR",
    str(REPO_ROOT / "scripts" / "processed_candidates"),
))

class CandidateDataViewer:
    """CRUD operations for candidate data visualization"""
    
    def __init__(self):
        self.raw_candidates = {}
        self.merged_candidates = {}
        self.processed_candidates = {}
        self.load_all_data()
    
    def load_all_data(self):
        """Load data from all stages"""
        # Stage 1: Load raw CSV data
        self.load_raw_candidates()
        # Stage 2: Load merged data
        self.load_merged_candidates()
        # Stage 3: Load LLM-processed data
        self.load_processed_candidates()
    
    def load_raw_candidates(self):
        """Load raw candidate data - using comprehensive merged data as source"""
        # For simplicity, use the same merged data for raw view
        # This ensures consistency across views
        nas_merged_file = NAS_DIR / "comprehensive_merged_candidates.json"
        candidates = {}
        
        if nas_merged_file.exists():
            with open(nas_merged_file, 'r', encoding='utf-8') as f:
                candidates_list = json.load(f)
                for candidate in candidates_list:
                    cid = candidate.get('id', '')
                    if cid:
                        # Extract just the basic fields for "raw" view
                        candidates[cid] = {
                            'id': cid,
                            'name': candidate.get('name', ''),
                            'email': candidate.get('email', ''),
                            'phone': candidate.get('phone', ''),
                            'headline': candidate.get('headline', ''),
                            'source': candidate.get('source', '')
                        }
        
        self.raw_candidates = candidates
    
    def load_merged_candidates(self):
        """Load merged candidate data from NAS JSON file"""
        merged = {}
        
        # Use comprehensive merged file that includes orphaned candidates
        nas_merged_file = NAS_DIR / "comprehensive_merged_candidates.json"
        if nas_merged_file.exists():
            print(f"Loading merged data from NAS: {nas_merged_file}")
            with open(nas_merged_file, 'r', encoding='utf-8') as f:
                candidates_list = json.load(f)
                # Convert list to dict with ID as key
                for candidate in candidates_list:
                    cid = candidate.get('id', '')
                    if cid:
                        merged[cid] = candidate
            print(f"Loaded {len(merged)} merged candidates from NAS")
        else:
            # Fallback to loading from CSV files
            print("NAS merged file not found, loading from CSV files...")
            merged = self.raw_candidates.copy()
            
            # Add comments
            comments_files = [
                "Ella_Executive_Search_comments-1.csv",
                "Ella_Executive_Search_comments-3.csv",
                "Ella_Executive_Search_comments-4.csv",
                "Ella_Executive_Search_comments-7.csv"
            ]
            
            for comment_file in comments_files:
                file_path = CSV_DIR / comment_file
                if file_path.exists():
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            cid = row.get('candidate_id', '').strip()
                            if cid in merged:
                                if 'comments' not in merged[cid]:
                                    merged[cid]['comments'] = []
                                merged[cid]['comments'].append({
                                    'date': row.get('Date', ''),
                                    'author': row.get('Author', ''),
                                    'text': row.get('Comment', ''),
                                    'type': row.get('Type', '')
                                })
        
        self.merged_candidates = merged
    
    def load_processed_candidates(self):
        """Load LLM-processed candidate data from NAS or local"""
        processed = {}
        
        # Try NAS first, then local as fallback
        dirs_to_check = [PROCESSED_DIR, LOCAL_PROCESSED_DIR]
        
        for dir_path in dirs_to_check:
            if not dir_path.exists():
                continue
            
            # Load from batch files
            for batch_file in dir_path.glob("batch_*.json"):
                with open(batch_file, 'r', encoding='utf-8') as f:
                    batch_data = json.load(f)
                    for candidate in batch_data:
                        cid = candidate.get('id', '')
                        if cid:
                            processed[cid] = candidate
            
            # Load from master file if exists
            master_file = dir_path / "all_candidates_processed.json"
            if master_file.exists():
                with open(master_file, 'r', encoding='utf-8') as f:
                    all_data = json.load(f)
                    for candidate in all_data:
                        cid = candidate.get('id', '')
                        if cid:
                            processed[cid] = candidate
            
            # If we found data, stop checking
            if processed:
                print(f"Loaded {len(processed)} processed candidates from {dir_path}")
                break
        
        self.processed_candidates = processed
    
    def get_candidate_stages(self, candidate_id: str) -> Dict[str, Any]:
        """Get candidate data from all processing stages"""
        merged_candidate = self.merged_candidates.get(candidate_id, {})
        
        # Create processed stage from merged candidate if it has LLM analysis
        processed_stage = {}
        if merged_candidate.get('enhanced_analysis'):
            processed_stage = merged_candidate.copy()  # Include all merged data
            processed_stage['processing_stage'] = 'processed'  # Mark as processed
        
        return {
            'raw': self.raw_candidates.get(candidate_id, {}),
            'merged': merged_candidate,
            'processed': processed_stage
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about the data"""
        orphaned = sum(1 for c in self.merged_candidates.values() if c.get('data_status') == 'orphaned')
        normal = sum(1 for c in self.merged_candidates.values() if c.get('data_status') != 'orphaned')
        
        return {
            'total_raw': len(self.raw_candidates),
            'total_merged': len(self.merged_candidates),
            'normal_candidates': normal,
            'orphaned_candidates': orphaned,
            'total_processed': len(self.processed_candidates),
            'with_comments': sum(1 for c in self.merged_candidates.values() if c.get('comments')),
            'with_resumes': sum(1 for c in self.merged_candidates.values() if c.get('resume_files')),
            'with_enhanced_analysis': sum(1 for c in self.merged_candidates.values() if c.get('enhanced_analysis')),
            'processing_errors': sum(1 for c in self.processed_candidates.values() 
                                   if c.get('enhanced_analysis', {}).get('error'))
        }

# Initialize viewer
viewer = CandidateDataViewer()

@app.route('/')
def index():
    """Main dashboard"""
    return render_template('index.html', stats=viewer.get_statistics())

@app.route('/api/candidates')
def list_candidates():
    """List all candidates with basic info"""
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))
    stage = request.args.get('stage', 'merged')
    search = request.args.get('search', '').strip().lower()
    
    if stage == 'raw':
        candidates = viewer.raw_candidates
    elif stage == 'processed':
        # Filter merged candidates to only show those with LLM analysis
        candidates = {cid: c for cid, c in viewer.merged_candidates.items() if c.get('enhanced_analysis')}
    else:
        candidates = viewer.merged_candidates
    
    # Filter by search term if provided
    if search:
        filtered_candidates = {}
        for cid, candidate in candidates.items():
            name = candidate.get('name', '').lower()
            email = candidate.get('email', '').lower()
            company = candidate.get('company', '').lower()
            title = candidate.get('title', '').lower()
            
            # Search in name, email, company, title, and ID
            if (search in name or 
                search in email or 
                search in company or 
                search in title or
                search in cid.lower()):
                filtered_candidates[cid] = candidate
        candidates = filtered_candidates
    
    # Paginate
    ids = list(candidates.keys())
    start = (page - 1) * per_page
    end = start + per_page
    page_ids = ids[start:end]
    
    result = []
    for cid in page_ids:
        candidate = candidates[cid]
        # Handle orphaned candidates
        name = candidate.get('name', '')
        if not name and candidate.get('data_status') == 'orphaned':
            name = '[Orphaned - Comments Only]'
        elif not name:
            name = 'Unknown'
            
        result.append({
            'id': cid,
            'name': name,
            'title': candidate.get('title', ''),
            'company': candidate.get('company', ''),
            'data_status': candidate.get('data_status', 'normal'),
            'has_comments': bool(candidate.get('comments')),
            'has_resume': bool(candidate.get('resume_files')),
            'has_analysis': bool(candidate.get('enhanced_analysis'))
        })
    
    return jsonify({
        'candidates': result,
        'total': len(candidates),
        'page': page,
        'per_page': per_page,
        'total_pages': (len(candidates) + per_page - 1) // per_page,
        'search': search
    })

@app.route('/api/candidate/<candidate_id>')
def get_candidate(candidate_id):
    """Get detailed candidate data from all stages"""
    stages = viewer.get_candidate_stages(candidate_id)
    
    # Format for display
    result = {
        'id': candidate_id,
        'stages': {
            'raw': stages['raw'],
            'merged': stages['merged'],
            'processed': stages['processed']
        },
        'summary': {}
    }
    
    # Create summary from processed data if available
    if stages['processed'] and stages['processed'].get('enhanced_analysis'):
        analysis = stages['processed']['enhanced_analysis']['analysis']
        result['summary'] = {
            'career_level': analysis.get('career_trajectory', {}).get('trajectory_type'),
            'velocity': analysis.get('career_trajectory', {}).get('velocity'),
            'technical_skills': analysis.get('skill_assessment', {}).get('technical_skills', {}).get('core_competencies', [])[:5],
            'leadership': analysis.get('leadership_scope', {}).get('leadership_style'),
            'company_tiers': analysis.get('company_pedigree', {}).get('company_tiers', []),
            'strengths': analysis.get('cultural_signals', {}).get('strengths', [])[:3],
            'one_line_pitch': analysis.get('executive_summary', {}).get('one_line_pitch'),
            'overall_rating': analysis.get('executive_summary', {}).get('overall_rating')
        }
    
    return jsonify(result)

@app.route('/api/prompts')
def get_prompts():
    """Get all LLM prompts being used"""
    prompts = {
        'career_trajectory': '''Analyze the following resume and extract career trajectory information.
        
Please provide a JSON response with the following structure:
{
    "current_level": "entry|mid|senior|lead|executive",
    "progression_speed": "slow|average|fast|exceptional",
    "years_to_current": <number>,
    "role_changes": <number>,
    "industry_changes": <number>,
    "promotion_pattern": "linear|accelerated|lateral|mixed",
    "career_highlights": ["highlight1", "highlight2", ...]
}''',
        
        'leadership_scope': '''Analyze the following resume for leadership experience and scope.

Please provide a JSON response with the following structure:
{
    "has_leadership": true|false,
    "team_size_managed": <number or null>,
    "budget_managed": "<amount or null>",
    "leadership_roles": ["role1", "role2", ...],
    "leadership_style_indicators": ["indicator1", "indicator2", ...],
    "cross_functional": true|false,
    "global_experience": true|false
}''',
        
        'company_pedigree': '''Analyze the companies mentioned in this resume.

Please provide a JSON response with a list of companies:
[
    {
        "company_name": "Company Name",
        "tier": "startup|growth|enterprise|faang|fortune500",
        "industry": "Industry",
        "years_there": <number>,
        "notable": true|false
    },
    ...
]''',
        
        'skills_extraction': '''Extract skills from the following resume.

Please provide a JSON response:
{
    "technical_skills": ["skill1", "skill2", ...],
    "soft_skills": ["skill1", "skill2", ...],
    "tools_technologies": ["tool1", "tool2", ...],
    "certifications": ["cert1", "cert2", ...]
}''',
        
        'cultural_signals': '''Identify cultural signals and values from this resume.

Look for indicators of:
- Work style (collaborative, independent, etc.)
- Values (innovation, stability, growth, etc.)
- Environment preferences (startup, corporate, etc.)
- Communication style
- Problem-solving approach

Provide a JSON array of cultural signals:
["signal1", "signal2", "signal3", ...]''',

        'recruiter_comments': '''Analyze the following recruiter comments about a candidate.

Comments:
{comments}

Extract and summarize:
1. Key strengths mentioned
2. Concerns or red flags
3. Overall sentiment (positive/neutral/negative)
4. Recurring themes
5. Fit indicators

Provide a JSON response:
{
    "strengths": ["strength1", "strength2", ...],
    "concerns": ["concern1", "concern2", ...],
    "sentiment": "positive|neutral|negative|mixed",
    "key_themes": ["theme1", "theme2", ...],
    "fit_score": <1-10>,
    "summary": "Brief 2-3 sentence summary"
}'''
    }
    
    return jsonify(prompts)

@app.route('/api/quality/<candidate_id>')
def analyze_quality(candidate_id):
    """Analyze the quality of LLM processing for a candidate"""
    stages = viewer.get_candidate_stages(candidate_id)
    
    quality_metrics = {
        'candidate_id': candidate_id,
        'data_completeness': {},
        'enhanced_analysis_quality': {},
        'issues': []
    }
    
    # Check data completeness
    merged = stages['merged']
    quality_metrics['data_completeness'] = {
        'has_basic_info': bool(merged.get('name') and merged.get('email')),
        'has_professional_info': bool(merged.get('title') or merged.get('company')),
        'has_comments': bool(merged.get('comments')),
        'comment_count': len(merged.get('comments', [])),
        'has_resume': bool(merged.get('resume_files')),
        'resume_count': len(merged.get('resume_files', []))
    }
    
    # Check LLM analysis quality
    if stages['processed'] and stages['processed'].get('enhanced_analysis'):
        analysis = stages['processed']['enhanced_analysis']['analysis']
        
        # Check for expected fields
        expected_fields = [
            'career_trajectory', 'leadership_scope', 'company_pedigree',
            'technical_skills', 'soft_skills', 'cultural_signals'
        ]
        
        fields_present = sum(1 for field in expected_fields if field in analysis)
        
        quality_metrics['enhanced_analysis_quality'] = {
            'completeness': f"{fields_present}/{len(expected_fields)}",
            'has_error': 'error' in analysis,
            'career_analyzed': 'career_trajectory' in analysis,
            'skills_extracted': len(analysis.get('technical_skills', [])) > 0,
            'leadership_analyzed': 'leadership_scope' in analysis,
            'cultural_signals_found': len(analysis.get('cultural_signals', [])) > 0
        }
        
        # Identify issues
        if 'error' in analysis:
            quality_metrics['issues'].append(f"LLM processing error: {analysis['error']}")
        if fields_present < len(expected_fields):
            quality_metrics['issues'].append(f"Incomplete analysis: only {fields_present}/{len(expected_fields)} fields")
        if not analysis.get('technical_skills'):
            quality_metrics['issues'].append("No technical skills extracted")
    else:
        quality_metrics['enhanced_analysis_quality'] = {
            'status': 'Not processed',
            'completeness': '0/6'
        }
        quality_metrics['issues'].append("Candidate not processed by LLM")
    
    # Calculate overall quality score
    score = 0
    if quality_metrics['data_completeness']['has_basic_info']:
        score += 20
    if quality_metrics['data_completeness']['has_professional_info']:
        score += 20
    if quality_metrics['data_completeness']['has_comments']:
        score += 20
    if quality_metrics['data_completeness']['has_resume']:
        score += 20
    if stages['processed'] and not stages['processed'].get('enhanced_analysis', {}).get('error'):
        score += 20
    
    quality_metrics['overall_score'] = score
    
    return jsonify(quality_metrics)

@app.route('/api/refresh', methods=['POST'])
def refresh_data():
    """Refresh the candidate data from NAS database"""
    try:
        # Reload all data from NAS
        viewer.load_all_data()
        
        # Get updated statistics
        stats = viewer.get_statistics()
        
        return jsonify({
            'status': 'success',
            'message': 'Data refreshed successfully',
            'stats': stats,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error refreshing data: {str(e)}',
            'timestamp': datetime.now().isoformat()
        }), 500

if __name__ == '__main__':
    # Create templates directory
    templates_dir = Path(__file__).parent / 'templates'
    templates_dir.mkdir(exist_ok=True)
    
    # Create basic HTML template
    index_html = templates_dir / 'index.html'
    if not index_html.exists():
        with open(index_html, 'w') as f:
            f.write('''<!DOCTYPE html>
<html>
<head>
    <title>Headhunter Candidate Viewer</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .stats { background: #f0f0f0; padding: 20px; border-radius: 5px; }
        .stat-item { margin: 10px 0; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background: #f2f2f2; }
        .stage { margin: 20px 0; padding: 15px; border: 1px solid #ddd; }
        .json-view { background: #f5f5f5; padding: 10px; border-radius: 3px; white-space: pre-wrap; }
        button { padding: 10px 20px; margin: 5px; cursor: pointer; }
        .prompt { background: #e8f4f8; padding: 15px; margin: 10px 0; border-left: 4px solid #0084ff; }
    </style>
</head>
<body>
    <h1>Headhunter Candidate Data Viewer</h1>
    
    <div class="stats">
        <h2>Data Statistics</h2>
        <div class="stat-item">Total Raw Candidates: {{ stats.total_raw }}</div>
        <div class="stat-item">Total Merged: {{ stats.total_merged }}</div>
        <div class="stat-item">Total Processed: {{ stats.total_processed }}</div>
        <div class="stat-item">With Comments: {{ stats.with_comments }}</div>
        <div class="stat-item">With Resumes: {{ stats.with_resumes }}</div>
        <div class="stat-item">With Enhanced Analysis: {{ stats.with_enhanced_analysis }}</div>
        <div class="stat-item">Processing Errors: {{ stats.processing_errors }}</div>
    </div>
    
    <div style="margin-top: 30px;">
        <h2>Navigation</h2>
        <button onclick="refreshData()">🔄 Refresh Data</button>
        <button onclick="loadCandidates('raw')">View Raw Data</button>
        <button onclick="loadCandidates('merged')">View Merged Data</button>
        <button onclick="loadCandidates('processed')">View Processed Data</button>
        <button onclick="viewPrompts()">View LLM Prompts</button>
    </div>
    
    <div id="content" style="margin-top: 30px;"></div>
    
    <script>
        function refreshData() {
            fetch('/api/refresh', { method: 'POST' })
                .then(r => r.json())
                .then(data => {
                    if (data.status === 'success') {
                        alert('Data refreshed successfully! Enhanced analysis count: ' + data.stats.with_enhanced_analysis);
                        location.reload(); // Reload the page to show updated stats
                    } else {
                        alert('Error refreshing data: ' + data.message);
                    }
                })
                .catch(e => alert('Error: ' + e.message));
        }
        
        function loadCandidates(stage) {
            fetch(`/api/candidates?stage=${stage}`)
                .then(r => r.json())
                .then(data => {
                    let html = `<h3>${stage.charAt(0).toUpperCase() + stage.slice(1)} Candidates (${data.total})</h3>`;
                    html += '<table><tr><th>ID</th><th>Name</th><th>Title</th><th>Company</th><th>Actions</th></tr>';
                    data.candidates.forEach(c => {
                        html += `<tr>
                            <td>${c.id}</td>
                            <td>${c.name}</td>
                            <td>${c.title || '-'}</td>
                            <td>${c.company || '-'}</td>
                            <td>
                                <button onclick="viewCandidate('${c.id}')">View</button>
                                <button onclick="analyzeQuality('${c.id}')">Quality</button>
                            </td>
                        </tr>`;
                    });
                    html += '</table>';
                    document.getElementById('content').innerHTML = html;
                });
        }
        
        function viewCandidate(id) {
            fetch(`/api/candidate/${id}`)
                .then(r => r.json())
                .then(data => {
                    let html = `<h3>Candidate: ${id}</h3>`;
                    
                    // Summary
                    if (data.summary && Object.keys(data.summary).length > 0) {
                        html += '<div class="stage"><h4>Summary</h4>';
                        html += '<div class="json-view">' + JSON.stringify(data.summary, null, 2) + '</div></div>';
                    }
                    
                    // Stage 1: Raw
                    html += '<div class="stage"><h4>Stage 1: Raw Data</h4>';
                    html += '<div class="json-view">' + JSON.stringify(data.stages.raw, null, 2) + '</div></div>';
                    
                    // Stage 2: Merged
                    html += '<div class="stage"><h4>Stage 2: Merged Data</h4>';
                    html += '<div class="json-view">' + JSON.stringify(data.stages.merged, null, 2) + '</div></div>';
                    
                    // Stage 3: Processed
                    if (data.stages.processed && data.stages.processed.enhanced_analysis) {
                        html += '<div class="stage"><h4>Stage 3: Enhanced Analysis</h4>';
                        html += '<div class="json-view">' + JSON.stringify(data.stages.processed.enhanced_analysis.analysis, null, 2) + '</div></div>';
                    }
                    
                    document.getElementById('content').innerHTML = html;
                });
        }
        
        function analyzeQuality(id) {
            fetch(`/api/quality/${id}`)
                .then(r => r.json())
                .then(data => {
                    let html = `<h3>Quality Analysis: ${id}</h3>`;
                    html += `<div class="stage">
                        <h4>Overall Score: ${data.overall_score}/100</h4>
                        <h5>Data Completeness:</h5>
                        <div class="json-view">${JSON.stringify(data.data_completeness, null, 2)}</div>
                        <h5>Enhanced Analysis Quality:</h5>
                        <div class="json-view">${JSON.stringify(data.enhanced_analysis_quality, null, 2)}</div>
                        <h5>Issues:</h5>
                        <ul>${data.issues.map(i => '<li>' + i + '</li>').join('')}</ul>
                    </div>`;
                    document.getElementById('content').innerHTML = html;
                });
        }
        
        function viewPrompts() {
            fetch('/api/prompts')
                .then(r => r.json())
                .then(data => {
                    let html = '<h3>LLM Prompts</h3>';
                    for (let [key, prompt] of Object.entries(data)) {
                        html += `<div class="prompt">
                            <h4>${key.replace(/_/g, ' ').toUpperCase()}</h4>
                            <pre>${prompt}</pre>
                        </div>`;
                    }
                    document.getElementById('content').innerHTML = html;
                });
        }
        
        // Load merged candidates by default
        loadCandidates('merged');
    </script>
</body>
</html>''')
    
    print("=" * 80)
    print("CANDIDATE DATA VIEWER")
    print("=" * 80)
    print(f"Statistics: {viewer.get_statistics()}")
    print("\nStarting Flask server...")
    print("Access the viewer at: http://localhost:5555")
    print("=" * 80)
    
    app.run(host='0.0.0.0', debug=True, port=5555)
