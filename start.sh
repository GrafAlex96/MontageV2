#!/bin/bash
# FULLY AUTOMATED ONE-COMMAND STARTUP SCRIPT
# AI Video Editor Bot - Production Readiness Edition

echo "🎬 Starting AI Video Editor System..."

# 1. Ensure logs directory exists for startup logging
mkdir -p logs

# 2. Basic dependency check
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found!"
    exit 1
fi

# 3. Ensure we have the latest core dependencies for process management
pip install pydantic-settings python-json-logger rq --quiet

# 4. Run the Unified Startup Manager
# This script handles System Deps, Redis, .env, DB, Worker, and Bot
PYTHONPATH=. python3 start_system.py
