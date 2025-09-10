import pytest
import tempfile
import os
import json
from datetime import datetime
from scripts.quarantine_system import QuarantineSystem


def test_quarantine_stores_failed_responses():
    """Test that failed responses are stored in quarantine"""
    with tempfile.TemporaryDirectory() as temp_dir:
        quarantine = QuarantineSystem(quarantine_dir=temp_dir)
        
        failed_response = "This is completely broken JSON {{{ [[["
        error_info = {
            "error_type": "JSONDecodeError",
            "error_message": "Invalid JSON syntax",
            "candidate_id": "test_123",
            "processor": "intelligent_skill_processor"
        }
        
        quarantine_id = quarantine.store(failed_response, error_info)
        
        assert quarantine_id is not None
        assert len(quarantine_id) > 0
        
        # Check file was created
        quarantine_files = os.listdir(temp_dir)
        assert len(quarantine_files) == 1
        assert quarantine_files[0].startswith('quarantine_')


def test_quarantine_retrieval():
    """Test that quarantined items can be retrieved"""
    with tempfile.TemporaryDirectory() as temp_dir:
        quarantine = QuarantineSystem(quarantine_dir=temp_dir)
        
        failed_response = "broken json"
        error_info = {"error": "test"}
        
        quarantine_id = quarantine.store(failed_response, error_info)
        retrieved = quarantine.retrieve(quarantine_id)
        
        assert retrieved is not None
        assert retrieved['original_response'] == failed_response
        assert retrieved['error_info'] == error_info
        assert 'timestamp' in retrieved
        assert 'quarantine_id' in retrieved


def test_quarantine_statistics():
    """Test quarantine statistics tracking"""
    with tempfile.TemporaryDirectory() as temp_dir:
        quarantine = QuarantineSystem(quarantine_dir=temp_dir)
        
        # Add some quarantined items
        quarantine.store("broken1", {"error": "syntax"})
        quarantine.store("broken2", {"error": "encoding"})
        quarantine.store("broken3", {"error": "syntax"})
        
        stats = quarantine.get_statistics()
        
        assert stats['total_quarantined'] == 3
        assert stats['error_patterns']['syntax'] == 2
        assert stats['error_patterns']['encoding'] == 1
        assert 'oldest_entry' in stats
        assert 'newest_entry' in stats


def test_quarantine_cleanup():
    """Test quarantine cleanup functionality"""
    with tempfile.TemporaryDirectory() as temp_dir:
        quarantine = QuarantineSystem(quarantine_dir=temp_dir)
        
        # Store some items
        id1 = quarantine.store("test1", {"error": "test"})
        id2 = quarantine.store("test2", {"error": "test"})
        
        # Should have 2 files
        assert len(os.listdir(temp_dir)) == 2
        
        # Clean up one specific item
        quarantine.cleanup(quarantine_id=id1)
        
        # Should have 1 file left
        assert len(os.listdir(temp_dir)) == 1
        
        # Should not be able to retrieve cleaned up item
        assert quarantine.retrieve(id1) is None
        assert quarantine.retrieve(id2) is not None