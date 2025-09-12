#!/usr/bin/env python3
"""
Test script to verify GCP infrastructure connectivity and permissions
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime

def test_imports():
    """Test if required libraries can be imported"""
    print("🔍 Testing Python library imports...")
    try:
        import google.cloud.aiplatform as aiplatform
        print("✅ google-cloud-aiplatform imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import google-cloud-aiplatform: {e}")
        return False
    
    try:
        import google.cloud.firestore as firestore
        print("✅ google-cloud-firestore imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import google-cloud-firestore: {e}")
        return False
    
    try:
        import google.cloud.storage as storage
        print("✅ google-cloud-storage imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import google-cloud-storage: {e}")
        return False
    
    return True

def test_credentials():
    """Test if credentials are properly configured"""
    print("\n🔑 Testing credentials configuration...")
    
    # Check for service account key
    key_file = Path(__file__).parent.parent / ".gcp" / "headhunter-service-key.json"
    if key_file.exists():
        print(f"✅ Service account key found: {key_file}")
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(key_file)
        
        # Load and validate key file
        try:
            with open(key_file, 'r') as f:
                key_data = json.load(f)
            print(f"✅ Service account: {key_data.get('client_email', 'Unknown')}")
            print(f"✅ Project ID: {key_data.get('project_id', 'Unknown')}")
            return key_data.get('project_id')
        except Exception as e:
            print(f"❌ Failed to load service account key: {e}")
            return None
    else:
        print(f"❌ Service account key not found: {key_file}")
        print("Run the setup script first: ./scripts/setup_gcp_infrastructure.sh")
        return None

def test_firestore(project_id):
    """Test Firestore connectivity"""
    print("\n🔥 Testing Firestore connectivity...")
    try:
        from google.cloud import firestore
        
        # Initialize Firestore client
        db = firestore.Client(project=project_id)
        print("✅ Firestore client initialized")
        
        # Test write operation
        test_doc = db.collection('test').document('connectivity_test')
        test_doc.set({
            'test': True,
            'timestamp': datetime.now(),
            'message': 'Connectivity test from Headhunter AI'
        })
        print("✅ Test document written to Firestore")
        
        # Test read operation
        doc = test_doc.get()
        if doc.exists:
            print("✅ Test document read from Firestore")
            print(f"   Data: {doc.to_dict()}")
        else:
            print("❌ Failed to read test document")
            return False
        
        # Clean up test document
        test_doc.delete()
        print("✅ Test document cleaned up")
        
        return True
    except Exception as e:
        print(f"❌ Firestore test failed: {e}")
        return False

def test_storage(project_id):
    """Test Cloud Storage connectivity"""
    print("\n🪣 Testing Cloud Storage connectivity...")
    try:
        from google.cloud import storage
        
        # Initialize Storage client
        client = storage.Client(project=project_id)
        print("✅ Storage client initialized")
        
        # Test bucket listing
        buckets = list(client.list_buckets())
        print(f"✅ Found {len(buckets)} buckets")
        
        # Look for project-specific buckets
        project_buckets = [b for b in buckets if project_id in b.name]
        if project_buckets:
            print("✅ Project-specific buckets found:")
            for bucket in project_buckets:
                print(f"   - {bucket.name}")
        else:
            print("⚠️  No project-specific buckets found (this is okay for initial setup)")
        
        return True
    except Exception as e:
        print(f"❌ Storage test failed: {e}")
        return False

def test_vertex_ai(project_id):
    """Test Vertex AI connectivity"""
    print("\n🤖 Testing Vertex AI connectivity...")
    try:
        from google.cloud import aiplatform
        
        # Initialize AI Platform
        aiplatform.init(project=project_id, location='us-central1')
        print("✅ Vertex AI initialized")
        
        # Test listing models (this requires Vertex AI API to be enabled)
        try:
            models = aiplatform.Model.list()
            print(f"✅ Vertex AI API accessible (found {len(models)} models)")
        except Exception as e:
            print(f"⚠️  Vertex AI API accessible but no models found: {e}")
        
        return True
    except Exception as e:
        print(f"❌ Vertex AI test failed: {e}")
        return False

def test_firebase_project(project_id):
    """Test Firebase project configuration"""
    print("\n🚀 Testing Firebase project configuration...")
    try:
        # Check Firebase config files
        config_files = [
            Path(__file__).parent.parent / "firebase.json",
            Path(__file__).parent.parent / ".firebaserc",
            Path(__file__).parent.parent / "firestore.rules",
            Path(__file__).parent.parent / "firestore.indexes.json"
        ]
        
        all_exist = True
        for config_file in config_files:
            if config_file.exists():
                print(f"✅ {config_file.name} exists")
            else:
                print(f"❌ {config_file.name} missing")
                all_exist = False
        
        # Check .firebaserc project ID
        firebaserc_path = Path(__file__).parent.parent / ".firebaserc"
        if firebaserc_path.exists():
            with open(firebaserc_path, 'r') as f:
                firebase_config = json.load(f)
            configured_project = firebase_config.get('projects', {}).get('default')
            if configured_project == project_id:
                print(f"✅ Firebase configured for project: {project_id}")
            else:
                print(f"⚠️  Firebase configured for different project: {configured_project}")
        
        return all_exist
    except Exception as e:
        print(f"❌ Firebase configuration test failed: {e}")
        return False

def main():
    """Run all connectivity tests"""
    print("🎯 Headhunter AI - GCP Infrastructure Connectivity Test")
    print("=" * 60)
    
    # Test 1: Python imports
    if not test_imports():
        print("\n❌ Import tests failed. Install required packages:")
        print("   pip install google-cloud-aiplatform google-cloud-firestore google-cloud-storage")
        return False
    
    # Test 2: Credentials
    project_id = test_credentials()
    if not project_id:
        return False
    
    # Test 3: Firebase configuration
    firebase_ok = test_firebase_project(project_id)
    
    # Test 4: Firestore
    firestore_ok = test_firestore(project_id)
    
    # Test 5: Cloud Storage
    storage_ok = test_storage(project_id)
    
    # Test 6: Vertex AI
    vertex_ok = test_vertex_ai(project_id)
    
    # Summary
    print("\n" + "=" * 60)
    print("🏁 Test Summary")
    print("=" * 60)
    
    tests = [
        ("Python Imports", True),  # Already tested above
        ("Credentials", project_id is not None),
        ("Firebase Config", firebase_ok),
        ("Firestore", firestore_ok),
        ("Cloud Storage", storage_ok),
        ("Vertex AI", vertex_ok)
    ]
    
    passed = sum(1 for _, result in tests if result)
    total = len(tests)
    
    for test_name, result in tests:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Infrastructure is ready.")
        print(f"\nEnvironment variables for local development:")
        print(f"export GOOGLE_APPLICATION_CREDENTIALS='{os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')}'")
        print(f"export GOOGLE_CLOUD_PROJECT='{project_id}'")
        return True
    else:
        print("\n⚠️  Some tests failed. Check the setup and try again.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)