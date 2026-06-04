#!/bin/bash

echo "🚀 Starting AI Video Editor Bot..."

# Ensure .env exists
if [ ! -f .env ]; then
    echo "⚠️ .env file not found! Please create it from .env.example"
    exit 1
fi

export PYTHONPATH=.

# Validate Dependencies
echo "🔍 Validating system dependencies..."
if ! command -v ffmpeg &> /dev/null; then
    echo "❌ FFmpeg not found! Please install it."
    exit 1
fi

if ! command -v redis-server &> /dev/null; then
    echo "❌ Redis server not found! Please install it."
    exit 1
fi

# Initialize DB if not exists
if [ ! -f video_editor.db ]; then
    echo "📦 Initializing database..."
    python3 scripts/init_db.py
fi

echo "✅ System health check passed."
python3 -m app.main
