#!/bin/bash
# FULLY AUTOMATED ONE-COMMAND STARTUP SCRIPT
# AI Video Editor Bot - v3.4.3 STABLE

echo "🎬 Starting AI Video Editor System..."

# 1. Ensure logs directory exists
mkdir -p logs

# 2. Run the Unified Startup Manager
# This script handles System Deps, Redis, .env, DB, Worker, and Bot
PYTHONPATH=. python3 start_system.py
