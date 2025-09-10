#!/bin/bash

# Adaptive Processing Launcher
# Automatically manages processing with day/night optimization

echo "🌙 ADAPTIVE PROCESSING SYSTEM"
echo "======================================"
echo "Night Mode (8 PM - 7 AM): 6 concurrent threads"
echo "Day Mode (7 AM - 8 PM): 2 background threads"
echo ""

# Stop any existing processors
echo "🔄 Stopping existing processors..."
pkill -f "continuous_quality_processor.py" 2>/dev/null
pkill -f "quality_batch_processor.py" 2>/dev/null
pkill -f "night_turbo_processor.py" 2>/dev/null
sleep 2

# Check current time and mode
HOUR=$(date +%H)
if [ $HOUR -ge 20 ] || [ $HOUR -lt 7 ]; then
    MODE="NIGHT"
    THREADS=6
else
    MODE="DAY"
    THREADS=2
fi

echo "⏰ Current time: $(date '+%I:%M %p')"
echo "📊 Active mode: $MODE"
echo "⚡ Thread count: $THREADS"
echo ""

# Show current progress
ENHANCED_COUNT=$(ls -1 "/Users/delimatsuo/Library/CloudStorage/SynologyDrive-NAS_Drive/NAS Files/Headhunter project/enhanced_analysis"/*.json 2>/dev/null | wc -l | tr -d ' ')
echo "📁 Current Status:"
echo "  Enhanced files: $ENHANCED_COUNT / 29,138"
echo "  Completion: $(echo "scale=1; $ENHANCED_COUNT * 100 / 29138" | bc)%"
echo ""

# Launch the night turbo processor
echo "🚀 Launching Adaptive Processor..."
echo "  - Automatically switches between day/night modes"
echo "  - Night: 6 threads for maximum throughput"
echo "  - Day: 2 threads for background processing"
echo ""

cd scripts 2>/dev/null || cd /Users/delimatsuo/Documents/Coding/headhunter/scripts

# Run with nohup
nohup python3 night_turbo_processor.py > night_turbo.log 2>&1 &
PROCESSOR_PID=$!

echo "✅ Processor launched with PID: $PROCESSOR_PID"
echo ""
echo "📝 Log files:"
echo "  tail -f night_turbo.log"
echo ""
echo "📊 Monitor progress:"
echo "  cat night_turbo_progress.json | python3 -m json.tool"
echo ""
echo "📈 View metrics:"
echo "  cat night_turbo_metrics.json | python3 -m json.tool"
echo ""
echo "🛑 Stop processing:"
echo "  kill $PROCESSOR_PID"
echo ""

# Show estimated completion
echo "⏱️ PERFORMANCE ESTIMATES:"
echo "  Night mode: ~6-8 candidates/minute (with 6 threads)"
echo "  Day mode: ~2-3 candidates/minute (with 2 threads)"
echo "  Full 29,138 database:"
echo "    If run nights only (11h/day): ~8-10 days"
echo "    If run 24/7 with adaptive: ~5-6 days"
echo ""
echo "🎯 The processor will automatically:"
echo "  1. Run at full speed from 8 PM to 7 AM"
echo "  2. Reduce to background mode during work hours"
echo "  3. Save progress continuously"
echo "  4. Resume from interruptions"