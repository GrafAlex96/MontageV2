#!/bin/bash

echo "🚀 Starting AI Video Editor Bot..."

# Ensure .env exists
if [ ! -f .env ]; then
    echo "⚠️ .env file not found! Please create it from .env.example"
    exit 1
fi

export PYTHONPATH=.

# Initialize DB if not exists
if [ ! -f video_editor.db ]; then
    echo "📦 Initializing database..."
    python3 scripts/init_db.py
fi

python3 -m app.main
