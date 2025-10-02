#!/bin/bash


SCRIPT_DIR=${SCRIPT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
# Guard against running from deprecated repository clones.
REPO_ROOT=${REPO_ROOT:-$(cd "${SCRIPT_DIR}/.." && pwd)}
# shellcheck source=./utils/repo_guard.sh
source "${SCRIPT_DIR}/utils/repo_guard.sh"

# Overnight Processing Launcher
# Runs from 6:50 PM to 7:00 AM with maximum performance

echo "🚀 OVERNIGHT TURBO PROCESSOR LAUNCHER"
echo "======================================"
echo "Schedule: 6:50 PM tonight - 7:00 AM tomorrow"
echo "Current time: $(date '+%I:%M %p')"
echo ""

# Kill any existing processors
echo "🔄 Stopping any existing processors..."
pkill -f "chunked_processor.py" 2>/dev/null
pkill -f "turbo_parallel_processor.py" 2>/dev/null
sleep 2

# Ensure Ollama is running
echo "✅ Checking Ollama status..."
if ! ollama list > /dev/null 2>&1; then
    echo "⚠️  Starting Ollama service..."
    ollama serve &
    sleep 5
fi

# Show current progress
echo ""
echo "📊 Current Status:"
ENHANCED_COUNT=$(ls -1 "/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project/enhanced_analysis"/*.json 2>/dev/null | wc -l | tr -d ' ')
echo "  Enhanced files: $ENHANCED_COUNT"

if [ -f "turbo_progress.json" ]; then
    echo "  Last turbo progress:"
    cat turbo_progress.json | python3 -m json.tool | head -10
fi

# Launch the turbo processor
echo ""
echo "🚀 Launching Turbo Parallel Processor..."
echo "  - Using all CPU cores for maximum speed"
echo "  - Will automatically start at 6:50 PM"
echo "  - Will automatically stop at 7:00 AM"
echo ""

# Run with nohup to survive terminal closure
nohup python3 turbo_parallel_processor.py > turbo_overnight.log 2>&1 &
PROCESSOR_PID=$!

echo "✅ Processor launched with PID: $PROCESSOR_PID"
echo "📝 Log file: turbo_overnight.log"
echo ""
echo "Monitor with:"
echo "  tail -f turbo_overnight.log"
echo ""
echo "Check progress with:"
echo "  cat turbo_progress.json | python3 -m json.tool"
echo ""
echo "Stop manually with:"
echo "  kill $PROCESSOR_PID"
echo ""
echo "🎯 Processing will begin at 6:50 PM and run overnight!"
