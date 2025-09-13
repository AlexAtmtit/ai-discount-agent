#!/usr/bin/env bash
set -e

echo "AI Discount Agent Demo"
echo "======================"

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Virtual environment not found. Running setup..."
    ./setup.sh
fi

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate

# Run the demo agent
echo "Running agent demo..."
python3 scripts/demo_agent.py
