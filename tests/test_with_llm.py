#!/usr/bin/env python3
"""
Test script for LLM integration and fuzzy matching
Run this after setting up your GOOGLE_API_KEY
"""

import os
import sys
import pytest
sys.path.append('.')

from scripts.agent_graph import run_agent_on_message
from scripts.gemini_client import init_gemini, GeminiConfig
import logging

# Set up logging to see detailed output
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s-%(name)s-%(levelname)s-%(message)s'
)

def test_fuzzy_matching_without_llm():
    """Test cases that should work with fuzzy matching (without LLM)"""
    print("🔍 Testing Fuzzy Matching Scenarios")
    print("=" * 50)

    # Test cases that should trigger fuzzy detection
    test_cases = [
        "discount",  # Short message, might need fuzzy
        "What's up", # Out of scope, should be classified properly
        "hello marques",  # Partial name match
        "hi mkbhd",  # Partial name match
    ]

    for message in test_cases:
        print(f"\n📝 Testing: '{message}'")
        try:
            result = run_agent_on_message(message)
            reply = result.get('reply', 'No reply')
            creator = result['database_row'].get('identified_creator', 'None')

            print(f"   🤖 Reply: {reply}")
            print(f"   👤 Creator: {creator}")
            print(f"   📄 Status: {result['database_row'].get('conversation_status', 'N/A')}")

        except Exception as e:
            print(f"   ❌ Error: {e}")

@pytest.mark.optional
def test_with_llm_api():
    """Test a specific message with LLM fallback"""
    message = "I need a discount code"
    print(f"\n🧠 Testing LLM Fallback: '{message}'")
    print("=" * 50)

    # Check if API key is available
    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key:
        pytest.skip("GOOGLE_API_KEY not set; skipping live LLM test")

    # Initialize Gemini client
    try:
        config = GeminiConfig(
            api_key=api_key,
            max_attempts=2,
            total_budget_ms=8000,
            per_attempt_timeout_ms=4000,
            model_version="gemini-2.5-flash-lite"
        )
        init_gemini(config)
        print("✅ Gemini client initialized successfully")

        # Test the message
        result = run_agent_on_message(message)
        reply = result.get('reply', 'No reply')
        creator = result['database_row'].get('identified_creator', 'None')

        print(f"   🤖 Reply: {reply}")
        print(f"   👤 Creator: {creator}")
        print(f"   📊 Method: {result['database_row'].get('detection_method', 'N/A')}")

    except Exception as e:
        print(f"   ❌ LLM Test Failed: {e}")

def main():
    print("🧪 AI Discount Agent LLM Integration Test")
    print("=" * 60)
    print("This script tests your Gemini API key integration")

    # First test fuzzy matching (doesn't require API key)
    test_fuzzy_matching_without_llm()

    # Then test LLM integration
    test_with_llm_api("I need a discount code")

    # Suggest manual testing
    print("\n📖 Manual Testing Instructions:")
    print("=" * 50)
    print("1. Activate virtual environment:")
    print("   source .venv/bin/activate")
    print("")
    print("2. Test specific messages:")
    print("   python3 -c \"from scripts.agent_graph import run_agent_on_message; print(run_agent_on_message('mkbhd discount for me'))\"")
    print("")
    print("3. Run full demo:")
    print("   ./demo.sh")
    print("")
    print("4. Start API server:")
    print("   ./run.sh")
    print("   # Then test endpoints:")
    print("   curl -X POST localhost:8000/simulate -d '{\"message\":\"mkbhd sent me\"}'")
    print("")
    print("5. Run tests:")
    print("   ./test.sh")

if __name__ == "__main__":
    main()
