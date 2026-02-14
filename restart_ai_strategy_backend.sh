#!/usr/bin/env bash
set -e

cd "$(dirname "$0")/applications/ai_strategy_agent/backend"

echo "🛑 Stopping any process on port 8000..."
if lsof -ti tcp:8000 >/dev/null 2>&1; then
  lsof -ti tcp:8000 | xargs kill -9
  echo "✅ Stopped process on port 8000"
else
  echo "No process on port 8000"
fi

if [ -f .venv/bin/activate ]; then
  source .venv/bin/activate
fi

uvicorn app.main:app --reload
