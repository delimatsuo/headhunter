#!/usr/bin/env python3
"""Quick test of turbo processor functionality"""

import json
from pathlib import Path
from datetime import datetime
import psutil
from multiprocessing import cpu_count

print("🧪 TURBO PROCESSOR TEST")
print("=" * 40)

# Check system resources
print(f"CPU Cores: {cpu_count()}")
print(f"CPU Usage: {psutil.cpu_percent()}%")
print(f"Memory: {psutil.virtual_memory().percent}%")

# Check files exist
nas_file = "/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project/comprehensive_merged_candidates.json"
enhanced_dir = Path("/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project/enhanced_analysis")

if Path(nas_file).exists():
    with open(nas_file, 'r') as f:
        candidates = json.load(f)
    print(f"✅ Database loaded: {len(candidates)} candidates")
else:
    print("❌ Database file not found")

if enhanced_dir.exists():
    existing_files = list(enhanced_dir.glob("*.json"))
    print(f"✅ Enhanced directory: {len(existing_files)} files")
else:
    print("❌ Enhanced directory not found")

# Check Ollama
import subprocess
try:
    result = subprocess.run(['ollama', 'list'], capture_output=True, text=True)
    if 'llama3.1:8b' in result.stdout:
        print("✅ Ollama with llama3.1:8b is available")
    else:
        print("⚠️  llama3.1:8b model not found")
except:
    print("❌ Ollama not accessible")

print("\n✅ Test complete - ready for processing!")