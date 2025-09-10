import os
import json
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
from collections import defaultdict


class QuarantineSystem:
    """System for storing and managing failed JSON responses"""
    
    def __init__(self, quarantine_dir: str = ".quarantine"):
        self.quarantine_dir = quarantine_dir
        self._ensure_quarantine_dir()
    
    def _ensure_quarantine_dir(self):
        """Ensure quarantine directory exists"""
        if not os.path.exists(self.quarantine_dir):
            os.makedirs(self.quarantine_dir, exist_ok=True)
    
    def store(self, failed_response: str, error_info: Dict[str, Any]) -> str:
        """Store a failed response in quarantine"""
        quarantine_id = f"quarantine_{uuid.uuid4().hex[:8]}"
        timestamp = datetime.now().isoformat()
        
        quarantine_data = {
            "quarantine_id": quarantine_id,
            "timestamp": timestamp,
            "original_response": failed_response,
            "error_info": error_info
        }
        
        filepath = os.path.join(self.quarantine_dir, f"{quarantine_id}.json")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(quarantine_data, f, indent=2, ensure_ascii=False)
        
        return quarantine_id
    
    def retrieve(self, quarantine_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a quarantined item by ID"""
        filepath = os.path.join(self.quarantine_dir, f"{quarantine_id}.json")
        
        if not os.path.exists(filepath):
            return None
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None
    
    def list_quarantined(self) -> List[str]:
        """List all quarantined item IDs"""
        if not os.path.exists(self.quarantine_dir):
            return []
        
        ids = []
        for filename in os.listdir(self.quarantine_dir):
            if filename.startswith('quarantine_') and filename.endswith('.json'):
                quarantine_id = filename[:-5]  # Remove .json extension
                ids.append(quarantine_id)
        
        return sorted(ids)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get quarantine statistics"""
        quarantined_ids = self.list_quarantined()
        
        if not quarantined_ids:
            return {
                'total_quarantined': 0,
                'error_patterns': {},
                'oldest_entry': None,
                'newest_entry': None
            }
        
        error_patterns = defaultdict(int)
        timestamps = []
        
        for qid in quarantined_ids:
            data = self.retrieve(qid)
            if data:
                timestamps.append(data['timestamp'])
                # Handle both direct error key and nested error_info structure
                error_info = data.get('error_info', {})
                if isinstance(error_info, dict):
                    error_type = error_info.get('error_type') or error_info.get('error', 'unknown')
                else:
                    error_type = str(error_info)
                error_patterns[error_type] += 1
        
        timestamps.sort()
        
        return {
            'total_quarantined': len(quarantined_ids),
            'error_patterns': dict(error_patterns),
            'oldest_entry': timestamps[0] if timestamps else None,
            'newest_entry': timestamps[-1] if timestamps else None
        }
    
    def cleanup(self, quarantine_id: Optional[str] = None, older_than_days: Optional[int] = None):
        """Clean up quarantine entries"""
        if quarantine_id:
            # Clean up specific item
            filepath = os.path.join(self.quarantine_dir, f"{quarantine_id}.json")
            if os.path.exists(filepath):
                os.remove(filepath)
        
        if older_than_days is not None:
            # Clean up old entries
            cutoff_time = datetime.now().timestamp() - (older_than_days * 24 * 60 * 60)
            
            for qid in self.list_quarantined():
                data = self.retrieve(qid)
                if data:
                    entry_time = datetime.fromisoformat(data['timestamp']).timestamp()
                    if entry_time < cutoff_time:
                        self.cleanup(quarantine_id=qid)
    
    def export_for_review(self, output_file: str):
        """Export all quarantined items for manual review"""
        quarantined_ids = self.list_quarantined()
        
        export_data = {
            'export_timestamp': datetime.now().isoformat(),
            'total_items': len(quarantined_ids),
            'items': []
        }
        
        for qid in quarantined_ids:
            data = self.retrieve(qid)
            if data:
                export_data['items'].append(data)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)