#!/bin/bash
# FULLY AUTOMATED ZERO-SETUP STARTUP SCRIPT
# AI Video Editor Bot - Production Readiness Edition

echo "🎬 Starting AI Video Editor System Bootstrapper..."

# 1. Ensure core directories exist
mkdir -p logs uploads tmp

# 2. Check and install Python dependencies (with retry)
echo "🐍 Verifying Python environment..."
if [ -f "requirements.txt" ]; then
    success=false
    for i in {1..2}; do
        if pip install -r requirements.txt --quiet; then
            echo "✅ Python dependencies verified."
            success=true
            break
        else
            echo "⚠️ Dependency install failed, retrying ($i/2)..."
            sleep 2
        fi
    done
    if [ "$success" = false ]; then
        echo "❌ Critical failure installing dependencies."
    fi
fi

# 3. Set PYTHONPATH to root for internal imports
export PYTHONPATH=.

# 4. Execute the Unified Startup Manager
python3 start_system.py
