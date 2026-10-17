#!/bin/bash
set -e
echo "Running NaSCon '26 Sports Platform Tests..."
cd "$(dirname "$0")/backend"
pip install -q -r requirements.txt
pip install -q pytest pytest-asyncio httpx anyio
python -m pytest tests/ -v --tb=short 2>&1
echo "Tests complete."
