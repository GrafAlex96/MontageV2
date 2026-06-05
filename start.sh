#!/bin/bash

echo "🚀 Starting AI Video Editor Bot (Unified Startup)..."

# Ensure .env exists
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        echo "📝 Creating .env from .env.example..."
        cp .env.example .env
        echo "⚠️ Please update .env with your real BOT_TOKEN if you haven't already."
    else
        echo "❌ .env.example not found! Cannot create .env."
        exit 1
    fi
fi

export PYTHONPATH=.

# 1. Start Redis if not running
if ! redis-cli ping &> /dev/null; then
    echo "📦 Starting Redis server..."
    redis-server --daemonize yes
    sleep 2
    if ! redis-cli ping &> /dev/null; then
        echo "❌ Failed to start Redis!"
        exit 1
    fi
fi
echo "✅ Redis is running."

# 2. Run Health Checks
echo "🔍 Running system health checks..."
python3 app/services/health_check.py
if [ $? -ne 0 ]; then
    echo "❌ Health checks failed. Aborting startup."
    exit 1
fi

# 3. Initialize DB if not exists
if [ ! -f video_editor.db ]; then
    echo "📦 Initializing database..."
    python3 scripts/init_db.py
fi

# 4. Start Background Worker
echo "⚙️ Starting background worker..."
PYTHONPATH=. rq worker video_processing > worker.log 2>&1 &
echo $! > worker.pid

# 5. Start Bot & API
echo "🤖 Starting Bot and API..."
# We run this in the foreground to keep the container/codespace alive
python3 app/main.py
