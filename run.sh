#!/usr/bin/env bash
set -e

echo "Starting AI Discount Agent Server"
echo "================================"

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Virtual environment not found. Running setup..."
    ./setup.sh
fi

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate
export PYTHONPATH=.

# Set environment variables (optional)
export CAMPAIGN_CONFIG_PATH=./config/campaign.yaml
export TEMPLATES_PATH=./config/templates.yaml

# Optional: Set API key if provided
if [ -n "$GOOGLE_API_KEY" ]; then
    echo "Gemini API key detected - LLM fallback enabled"
else
    echo "No GOOGLE_API_KEY set - LLM fallback disabled"
fi

# Start server (module mode so imports resolve)
echo "Starting FastAPI server..."
echo "API will be available at:"
echo "  http://localhost:8000"
echo "  http://localhost:8000/docs (interactive docs)"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

python3 -m uvicorn api.app:app --reload
