#!/usr/bin/env python3
"""
Monitor Progress - Real-time monitoring of continuous processing
"""

import json
import time
from pathlib import Path
from datetime import datetime
import sys

def monitor():
    """Monitor continuous processing progress"""
    progress_file = Path("continuous_progress.json")
    metrics_file = Path("continuous_metrics.json")
    enhanced_dir = Path("/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project/enhanced_analysis")
    
    print("📊 CONTINUOUS PROCESSING MONITOR")
    print("=" * 60)
    print("Press Ctrl+C to exit monitoring")
    print()
    
    last_update = None
    
    while True:
        try:
            # Count actual files
            files_count = len(list(enhanced_dir.glob("*.json")))
            
            # Load progress
            if progress_file.exists():
                with open(progress_file, 'r') as f:
                    progress = json.load(f)
                
                # Clear screen (optional - comment out if you prefer scrolling)
                # print("\033[H\033[J", end="")
                
                print(f"\n{'='*60}")
                print(f"📊 PROGRESS UPDATE - {datetime.now().strftime('%I:%M:%S %p')}")
                print(f"{'='*60}")
                
                print(f"\n📈 PROCESSING STATUS:")
                print(f"  Last Index: {progress.get('last_index', 0):,} / 29,138")
                print(f"  Batch Number: {progress.get('batch_number', 0)}")
                print(f"  Completion: {100 * progress.get('last_index', 0) / 29138:.1f}%")
                print(f"  Files Created: {files_count:,}")
                
                print(f"\n📊 SESSION STATISTICS:")
                print(f"  Total Processed: {progress.get('total_processed', 0):,}")
                print(f"  Total Failed: {progress.get('total_failed', 0)}")
                print(f"  Success Rate: {100 * progress.get('total_processed', 0) / max(progress.get('total_processed', 0) + progress.get('total_failed', 0), 1):.1f}%")
                print(f"  Session Duration: {progress.get('session_duration', 'N/A')}")
                
                # Load metrics if available
                if metrics_file.exists():
                    with open(metrics_file, 'r') as f:
                        metrics = json.load(f)
                    
                    if 'overall' in metrics:
                        overall = metrics['overall']
                        print(f"\n⚡ PERFORMANCE METRICS:")
                        print(f"  Total Batches: {overall.get('total_batches', 0)}")
                        print(f"  Avg Rate: {overall.get('avg_rate_per_minute', 0):.2f} candidates/minute")
                        print(f"  Total Time: {overall.get('total_time_seconds', 0)/60:.1f} minutes")
                        
                        # Estimate remaining time
                        remaining = 29138 - progress.get('last_index', 0)
                        if overall.get('avg_rate_per_minute', 0) > 0:
                            eta_hours = remaining / (overall.get('avg_rate_per_minute', 0) * 60)
                            print(f"  Est. Time Remaining: {eta_hours:.1f} hours")
                            
                            # Calculate completion time
                            if eta_hours < 24:
                                print(f"  Est. Completion: Today at {(datetime.now().timestamp() + eta_hours*3600)}")
                            else:
                                days = int(eta_hours / 24)
                                hours = eta_hours % 24
                                print(f"  Est. Completion: {days} days, {hours:.1f} hours")
                    
                    # Show recent batches
                    if 'batches' in metrics and metrics['batches']:
                        recent = metrics['batches'][-3:]
                        print(f"\n📋 RECENT BATCHES:")
                        for batch in recent:
                            print(f"  Batch {batch['batch_number']}: {batch['rate_per_minute']:.1f}/min ({batch['processing_time']/60:.1f} min)")
                
                print(f"\n⏰ Last Updated: {progress.get('timestamp', 'N/A')}")
                
                # Check if still running
                import subprocess
                result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
                if 'continuous_quality_processor' in result.stdout:
                    print(f"✅ Processor Status: RUNNING")
                else:
                    print(f"⚠️ Processor Status: STOPPED")
                    print(f"   Run: cd scripts && python3 continuous_quality_processor.py")
            
            else:
                print("⚠️ No progress file found yet...")
            
            # Wait before next update
            time.sleep(30)  # Update every 30 seconds
            
        except KeyboardInterrupt:
            print("\n\n👋 Monitoring stopped")
            sys.exit(0)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    monitor()