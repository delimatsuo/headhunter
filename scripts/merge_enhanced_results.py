#!/usr/bin/env python3
"""
Merge Enhanced Analysis Results into Main NAS Database
Takes processed results from enhanced_analysis files and merges them into the main database
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

class EnhancedResultsMerger:
    def __init__(self):
        self.nas_file = "/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project/comprehensive_merged_candidates.json"
        self.enhanced_dir = Path("/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project/enhanced_analysis")
        self.local_enhanced_dir = Path("enhanced_analysis")
        
    def load_nas_data(self):
        """Load the main NAS database"""
        print(f"📂 Loading NAS database: {self.nas_file}")
        with open(self.nas_file, 'r') as f:
            return json.load(f)
    
    def save_nas_data(self, data):
        """Save updated data back to NAS with backup"""
        backup_file = self.nas_file.replace('.json', f'_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
        print(f"💾 Creating backup: {backup_file}")
        with open(backup_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"💾 Updating NAS database...")
        with open(self.nas_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def find_enhanced_files(self):
        """Find all enhanced analysis files"""
        files = []
        
        # Check NAS enhanced_analysis directory
        if self.enhanced_dir.exists():
            for file in self.enhanced_dir.glob("*enhanced*.json"):
                files.append(file)
        
        # Check local enhanced_analysis directory
        if self.local_enhanced_dir.exists():
            for file in self.local_enhanced_dir.glob("*enhanced*.json"):
                files.append(file)
        
        # Check for timestamped files
        for pattern in ["enhanced_analysis_*.json", "*_enhanced.json"]:
            for dir_path in [self.enhanced_dir.parent, Path(".")]:
                if dir_path.exists():
                    for file in dir_path.glob(pattern):
                        files.append(file)
        
        return files
    
    def load_enhanced_file(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Load enhanced analysis from a file"""
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ Error loading {file_path}: {e}")
            return None
    
    def extract_enhancements(self, enhanced_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Extract enhancements keyed by candidate ID"""
        enhancements = {}
        
        # Handle different file formats
        if isinstance(enhanced_data, list):
            # List of enhanced analyses
            for item in enhanced_data:
                if isinstance(item, dict):
                    candidate_id = item.get('candidate_id') or item.get('id')
                    if candidate_id:
                        analysis = item.get('enhanced_analysis', item.get('analysis'))
                        if analysis:
                            enhancements[str(candidate_id)] = {
                                'analysis': analysis,
                                'processing_timestamp': item.get('timestamp', datetime.now().isoformat())
                            }
        
        elif isinstance(enhanced_data, dict):
            # Single enhanced analysis or dict of analyses
            if 'candidate_id' in enhanced_data:
                # Single candidate
                candidate_id = enhanced_data['candidate_id']
                analysis = enhanced_data.get('enhanced_analysis', enhanced_data.get('analysis'))
                if analysis:
                    enhancements[str(candidate_id)] = {
                        'analysis': analysis,
                        'processing_timestamp': enhanced_data.get('timestamp', datetime.now().isoformat())
                    }
            else:
                # Dict keyed by candidate ID
                for candidate_id, data in enhanced_data.items():
                    if isinstance(data, dict) and ('analysis' in data or 'enhanced_analysis' in data):
                        analysis = data.get('enhanced_analysis', data.get('analysis'))
                        if analysis:
                            enhancements[str(candidate_id)] = {
                                'analysis': analysis,
                                'processing_timestamp': data.get('timestamp', datetime.now().isoformat())
                            }
        
        return enhancements
    
    def merge_results(self):
        """Merge all enhanced results into main database"""
        print("🔄 Enhanced Results Merger")
        print("=" * 60)
        
        # Load main database
        candidates = self.load_nas_data()
        total_candidates = len(candidates)
        
        # Count existing enhanced analyses
        existing_count = sum(1 for c in candidates if c.get('enhanced_analysis'))
        print(f"📊 Total candidates: {total_candidates}")
        print(f"📊 Existing enhanced analyses: {existing_count}")
        
        # Find all enhanced files
        enhanced_files = self.find_enhanced_files()
        print(f"📂 Found {len(enhanced_files)} enhanced analysis files")
        
        if not enhanced_files:
            print("⚠️ No enhanced analysis files found!")
            return
        
        # Collect all enhancements
        all_enhancements = {}
        
        for file_path in enhanced_files:
            print(f"  📄 Processing: {file_path}")
            enhanced_data = self.load_enhanced_file(file_path)
            if enhanced_data:
                enhancements = self.extract_enhancements(enhanced_data)
                print(f"     ✓ Found {len(enhancements)} enhancements")
                all_enhancements.update(enhancements)
        
        print(f"\n📊 Total unique enhancements to merge: {len(all_enhancements)}")
        
        if not all_enhancements:
            print("⚠️ No valid enhancements found in files!")
            return
        
        # Merge enhancements into main database
        merged_count = 0
        updated_count = 0
        
        for i, candidate in enumerate(candidates):
            candidate_id = str(candidate.get('id', ''))
            if candidate_id in all_enhancements:
                enhancement = all_enhancements[candidate_id]
                
                if candidate.get('enhanced_analysis'):
                    # Update existing
                    candidates[i]['enhanced_analysis'] = enhancement
                    updated_count += 1
                    print(f"  🔄 Updated: {candidate_id} - {candidate.get('name', 'Unknown')}")
                else:
                    # Add new
                    candidates[i]['enhanced_analysis'] = enhancement
                    merged_count += 1
                    print(f"  ✅ Added: {candidate_id} - {candidate.get('name', 'Unknown')}")
        
        # Save updated database
        if merged_count > 0 or updated_count > 0:
            self.save_nas_data(candidates)
            
            final_count = sum(1 for c in candidates if c.get('enhanced_analysis'))
            print(f"\n✅ Merge complete!")
            print(f"📈 New enhancements added: {merged_count}")
            print(f"🔄 Existing enhancements updated: {updated_count}")
            print(f"📊 Total enhanced candidates: {final_count} (was {existing_count})")
            print(f"💾 NAS database updated!")
        else:
            print("\n⚠️ No changes made to database")

def main():
    merger = EnhancedResultsMerger()
    merger.merge_results()

if __name__ == "__main__":
    main()