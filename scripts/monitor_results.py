#!/usr/bin/env python3
"""
Results Monitor - Real-time monitoring and output viewing for Cloud enrichment
"""

import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime
from google.cloud import firestore
import subprocess
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.json import JSON
from rich.live import Live
from rich.layout import Layout
import argparse

console = Console()

def setup_gcp():
    """Initialize GCP clients"""
    try:
        os.environ['GOOGLE_CLOUD_PROJECT'] = 'headhunter-ai-0088'
        firestore_client = firestore.Client()
        return firestore_client
    except Exception as e:
        console.print(f"❌ GCP setup failed: {e}", style="red")
        return None

def get_enriched_profiles(firestore_client, limit=50):
    """Get enriched profiles from Firestore"""
    try:
        docs = firestore_client.collection('enriched_profiles').limit(limit).get()
        profiles = []
        for doc in docs:
            data = doc.to_dict()
            profiles.append({
                'id': doc.id,
                'name': data.get('name', 'Unknown'),
                'enrichment_version': data.get('enrichment', {}).get('enrichment_version', 'unknown'),
                'timestamp': data.get('enrichment', {}).get('enrichment_timestamp', ''),
                'ai_summary_length': len(data.get('enrichment', {}).get('ai_summary', '')),
                'has_career_analysis': 'career_analysis' in data.get('enrichment', {}),
                'has_strategic_fit': 'strategic_fit' in data.get('enrichment', {}),
                'alignment_score': data.get('enrichment', {}).get('strategic_fit', {}).get('role_alignment_score', 0),
                'data': data
            })
        return profiles
    except Exception as e:
        console.print(f"❌ Error fetching profiles: {e}", style="red")
        return []

def get_embeddings(firestore_client, limit=20):
    """Get vector embeddings from Firestore"""
    try:
        docs = firestore_client.collection('candidate_embeddings').limit(limit).get()
        embeddings = []
        for doc in docs:
            data = doc.to_dict()
            embeddings.append({
                'candidate_id': data.get('candidate_id'),
                'embedding_size': len(data.get('embedding_vector', [])),
                'metadata': data.get('metadata', {}),
                'updated_at': data.get('metadata', {}).get('updated_at', ''),
            })
        return embeddings
    except Exception as e:
        console.print(f"❌ Error fetching embeddings: {e}", style="red")
        return []

def display_profile_details(profile):
    """Display detailed profile information"""
    console.clear()
    
    # Header
    console.print(f"\n🔍 CANDIDATE PROFILE DETAILS", style="bold blue")
    console.print("=" * 60)
    
    # Basic Info
    info_table = Table(title="Basic Information")
    info_table.add_column("Field", style="cyan", no_wrap=True)
    info_table.add_column("Value", style="white")
    
    info_table.add_row("Candidate ID", profile['id'])
    info_table.add_row("Name", profile['name'])
    info_table.add_row("Enrichment Version", profile['enrichment_version'])
    info_table.add_row("Processing Time", profile['timestamp'])
    info_table.add_row("AI Summary Length", f"{profile['ai_summary_length']} characters")
    info_table.add_row("Alignment Score", f"{profile['alignment_score']}/100")
    
    console.print(info_table)
    console.print()
    
    # AI Summary
    if profile['data'].get('enrichment', {}).get('ai_summary'):
        ai_summary = profile['data']['enrichment']['ai_summary']
        console.print(Panel(ai_summary, title="🤖 AI Summary", border_style="green"))
        console.print()
    
    # Career Analysis
    if profile['has_career_analysis']:
        career = profile['data']['enrichment']['career_analysis']
        career_table = Table(title="📊 Career Analysis")
        career_table.add_column("Aspect", style="yellow", no_wrap=True)
        career_table.add_column("Analysis", style="white")
        
        for key, value in career.items():
            if isinstance(value, str):
                career_table.add_row(key.replace('_', ' ').title(), value[:100] + "..." if len(value) > 100 else value)
        
        console.print(career_table)
        console.print()
    
    # Strategic Fit
    if profile['has_strategic_fit']:
        strategic = profile['data']['enrichment']['strategic_fit']
        
        console.print(f"🎯 Strategic Fit Score: {strategic.get('role_alignment_score', 0)}/100", style="bold")
        
        if strategic.get('cultural_match_indicators'):
            console.print("Cultural Match Indicators:", style="cyan")
            for indicator in strategic['cultural_match_indicators'][:5]:
                console.print(f"  • {indicator}")
        
        if strategic.get('development_recommendations'):
            console.print("\\nDevelopment Recommendations:", style="cyan")
            for rec in strategic['development_recommendations'][:3]:
                console.print(f"  • {rec}")
        console.print()
    
    console.print("Press any key to continue...", style="dim")
    input()

def create_summary_report(profiles, embeddings):
    """Create and save summary report"""
    now = datetime.now()
    
    # Count enrichment versions
    version_counts = {}
    for profile in profiles:
        version = profile['enrichment_version']
        version_counts[version] = version_counts.get(version, 0) + 1
    
    # Calculate quality metrics
    total_profiles = len(profiles)
    gemini_count = version_counts.get('1.0-gemini', 0)
    fallback_count = version_counts.get('1.0-fallback', 0)
    
    avg_summary_length = sum(p['ai_summary_length'] for p in profiles) / total_profiles if total_profiles > 0 else 0
    avg_alignment_score = sum(p['alignment_score'] for p in profiles) / total_profiles if total_profiles > 0 else 0
    
    report = {
        "report_timestamp": now.isoformat(),
        "summary": {
            "total_enriched_profiles": total_profiles,
            "total_embeddings": len(embeddings),
            "gemini_enrichments": gemini_count,
            "fallback_enrichments": fallback_count,
            "success_rate": (gemini_count / total_profiles * 100) if total_profiles > 0 else 0,
            "avg_ai_summary_length": round(avg_summary_length),
            "avg_alignment_score": round(avg_alignment_score, 1)
        },
        "enrichment_versions": version_counts,
        "quality_metrics": {
            "profiles_with_career_analysis": len([p for p in profiles if p['has_career_analysis']]),
            "profiles_with_strategic_fit": len([p for p in profiles if p['has_strategic_fit']]),
            "alignment_score_distribution": {
                "excellent (90-100)": len([p for p in profiles if p['alignment_score'] >= 90]),
                "good (80-89)": len([p for p in profiles if 80 <= p['alignment_score'] < 90]),
                "fair (70-79)": len([p for p in profiles if 70 <= p['alignment_score'] < 80]),
                "needs_improvement (<70)": len([p for p in profiles if p['alignment_score'] < 70])
            }
        },
        "sample_profiles": [
            {
                "candidate_id": p['id'],
                "name": p['name'],
                "enrichment_version": p['enrichment_version'],
                "alignment_score": p['alignment_score'],
                "ai_summary_preview": (p['data'].get('enrichment', {}).get('ai_summary', ''))[:200] + "..."
            } for p in profiles[:5]
        ]
    }
    
    # Save report
    report_path = Path(__file__).parent / f"enrichment_results_{now.strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    return report, report_path

def monitor_live():
    """Live monitoring dashboard"""
    firestore_client = setup_gcp()
    if not firestore_client:
        return
    
    console.print("🔄 Starting live monitoring...", style="blue")
    console.print("Press Ctrl+C to stop\\n")
    
    try:
        while True:
            # Get latest data
            profiles = get_enriched_profiles(firestore_client, 20)
            embeddings = get_embeddings(firestore_client, 20)
            
            # Create dashboard
            console.clear()
            console.print("📊 LIVE ENRICHMENT MONITORING DASHBOARD", style="bold blue")
            console.print(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            console.print("=" * 80)
            
            # Summary stats
            stats_table = Table(title="📈 Current Statistics")
            stats_table.add_column("Metric", style="cyan")
            stats_table.add_column("Value", style="white")
            
            stats_table.add_row("Enriched Profiles", str(len(profiles)))
            stats_table.add_row("Vector Embeddings", str(len(embeddings)))
            
            if profiles:
                gemini_count = len([p for p in profiles if 'gemini' in p['enrichment_version']])
                stats_table.add_row("Gemini 2.5 Flash", str(gemini_count))
                stats_table.add_row("Success Rate", f"{gemini_count/len(profiles)*100:.1f}%")
                avg_score = sum(p['alignment_score'] for p in profiles) / len(profiles)
                stats_table.add_row("Avg Alignment Score", f"{avg_score:.1f}/100")
            
            console.print(stats_table)
            console.print()
            
            # Recent profiles
            if profiles:
                recent_table = Table(title="🆕 Recent Enrichments")
                recent_table.add_column("ID", style="yellow")
                recent_table.add_column("Name", style="white")
                recent_table.add_column("Version", style="green")
                recent_table.add_column("Score", style="cyan")
                recent_table.add_column("Summary Length", style="magenta")
                
                for profile in profiles[:10]:
                    recent_table.add_row(
                        profile['id'][:12] + "...",
                        profile['name'][:20],
                        profile['enrichment_version'],
                        f"{profile['alignment_score']}/100",
                        f"{profile['ai_summary_length']} chars"
                    )
                
                console.print(recent_table)
            
            time.sleep(10)
            
    except KeyboardInterrupt:
        console.print("\\n✋ Monitoring stopped by user")

def main():
    parser = argparse.ArgumentParser(description='Monitor Headhunter Cloud enrichment results')
    parser.add_argument('--live', action='store_true', help='Start live monitoring dashboard')
    parser.add_argument('--summary', action='store_true', help='Generate summary report')
    parser.add_argument('--details', type=str, help='Show detailed view of specific candidate ID')
    parser.add_argument('--export', action='store_true', help='Export all results to JSON file')
    
    args = parser.parse_args()
    
    if not any([args.live, args.summary, args.details, args.export]):
        # Default: show summary
        args.summary = True
    
    firestore_client = setup_gcp()
    if not firestore_client:
        return False
    
    if args.live:
        monitor_live()
        return True
    
    # Get data
    console.print("📡 Fetching enrichment results from Firestore...", style="blue")
    profiles = get_enriched_profiles(firestore_client, 100)
    embeddings = get_embeddings(firestore_client, 50)
    
    if not profiles:
        console.print("❌ No enriched profiles found in Firestore", style="red")
        console.print("   Make sure the Cloud Functions have processed some candidates")
        return False
    
    if args.details:
        # Show specific candidate details
        profile = next((p for p in profiles if args.details in p['id']), None)
        if profile:
            display_profile_details(profile)
        else:
            console.print(f"❌ Candidate {args.details} not found", style="red")
        return True
    
    if args.summary:
        # Generate and show summary
        report, report_path = create_summary_report(profiles, embeddings)
        
        console.print("\\n📊 ENRICHMENT RESULTS SUMMARY", style="bold green")
        console.print("=" * 50)
        
        summary = report['summary']
        console.print(f"Total Enriched Profiles: {summary['total_enriched_profiles']}")
        console.print(f"Gemini 2.5 Flash Enrichments: {summary['gemini_enrichments']}")
        console.print(f"Fallback Enrichments: {summary['fallback_enrichments']}")
        console.print(f"Success Rate: {summary['success_rate']:.1f}%")
        console.print(f"Average AI Summary Length: {summary['avg_ai_summary_length']} characters")
        console.print(f"Average Alignment Score: {summary['avg_alignment_score']}/100")
        console.print(f"Total Vector Embeddings: {summary['total_embeddings']}")
        
        console.print(f"\\n💾 Detailed report saved to: {report_path}", style="cyan")
        
        # Show sample profiles
        console.print("\\n🔍 Sample Enriched Profiles:", style="bold")
        for i, profile in enumerate(report['sample_profiles'], 1):
            console.print(f"\\n{i}. {profile['name']} ({profile['candidate_id']})")
            console.print(f"   Version: {profile['enrichment_version']} | Score: {profile['alignment_score']}/100")
            console.print(f"   Preview: {profile['ai_summary_preview']}")
    
    if args.export:
        # Export all data
        export_path = Path(__file__).parent / f"full_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        export_data = {
            'profiles': [p['data'] for p in profiles],
            'embeddings': embeddings,
            'export_timestamp': datetime.now().isoformat()
        }
        
        with open(export_path, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        console.print(f"\\n📦 Full data export saved to: {export_path}", style="green")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)