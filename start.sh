#!/bin/bash
# FULLY AUTOMATED ZERO-SETUP STARTUP SCRIPT
# AI Video Editor Bot - Production Readiness Edition

echo "🎬 Starting AI Video Editor System Bootstrapper..."

# 1. Ensure core directories exist
mkdir -p logs uploads tmp

# 2. Check and install Python dependencies
echo "🐍 Verifying Python environment..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt --quiet
    echo "✅ Python dependencies verified."
fi

# 3. Set PYTHONPATH to root for internal imports
export PYTHONPATH=.

# 4. Execute the Unified Startup Manager
# This script handles System Deps (apt), Redis, .env, DB, Worker, and Bot
python3 start_system.py
