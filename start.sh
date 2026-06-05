#!/bin/bash
# FULLY AUTOMATED ONE-COMMAND STARTUP SCRIPT
# AI Video Editor Bot - Production Readiness Edition

echo "🎬 Starting AI Video Editor System..."

# 1. Ensure Python dependencies are met
echo "🐍 Verifying Python dependencies..."
pip install -r requirements.txt --quiet

# 2. Run the Unified Startup Manager
# This script handles System Deps, Redis, .env, DB, Worker, and Bot
PYTHONPATH=. python3 start_system.py
