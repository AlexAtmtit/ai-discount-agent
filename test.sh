#!/usr/bin/env bash
set -e

echo "AI Discount Agent Test Suite"
echo "============================"

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Virtual environment not found. Running setup..."
    ./setup.sh
fi

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate

# Run tests
echo "Running tests..."
if [ -d "tests" ] && ls tests/*.py >/dev/null 2>&1; then
    python3 -m pytest -v tests/
    echo ""
    echo "Run coverage: python3 -m pytest --cov=scripts --cov-report=html tests/"
else
    echo "No test files found in tests/ directory."
    echo "Create test files following the plan:"
    echo "- tests/test_agent_core.py      (detection + responses)"
    echo "- tests/test_idempotency.py     (no duplicate codes)"
    echo "- tests/test_integration.py     (/simulate end-to-end)"
fi
