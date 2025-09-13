#!/usr/bin/env bash
set -e

echo "AI Discount Agent Setup"
echo "======================"

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv .venv

# Activate virtual environment
echo "Activating virtual environment..."
source .venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
python3 -m pip install --upgrade pip

# Install dependencies
echo "Installing dependencies..."
python3 -m pip install --upgrade pip
pip3 install -r requirements.txt || python3 -m pip install -r requirements.txt

echo "Setup complete!"
echo ""
echo "Next steps:"
echo "1. Optional: Set your GOOGLE_API_KEY for LLM fallback"
echo "   export GOOGLE_API_KEY=your_key_here"
echo "2. Run the demo: ./demo.sh"
echo "3. Start the server: ./run.sh"
echo ""
echo "Note: Database setup is not required - the demo uses in-memory storage."
