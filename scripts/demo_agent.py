"""Standalone demo agent for assignment Step 2

This script demonstrates the AI agent's functionality by running it on
sample messages and printing the results as required by the assignment.

Usage: python scripts/demo_agent.py
"""

import logging
import sys
import os

# Add the project root directory to Python path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.agent_graph import run_agent_on_message

# Configure logging to show info level
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Suppress httpx and google.generativeai logs for cleaner output
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('google').setLevel(logging.WARNING)

# Sample messages to test the agent
TEST_MESSAGES = [
    "I saw this on mkbhd's story, I need the discount",
    "Hi, Casey sent me",
    "discount",
    "What's up",
    "mkbhd discount code please",
    "lily_singh sent me here",
    "Marques Bronlee discount",  # Forces LLM fallback demo
    "error_test",  # Forces error handling demo
    "SteveCreator sent me here for discount",  # Forces LLM fallback for unknown creator
    "hey, promo from marqes brwnli pls"  # Should trigger exact LLM success for mkbhd
]


def main():
    """Main function to run the demo"""
    print("AI Discount Agent Demo")
    print("=" * 50)
    print("This demonstrates the agent processing messages from Step 2 of the assignment.")
    print("Each message is processed and returns a reply + database row JSON.\n")

    for i, test_msg in enumerate(TEST_MESSAGES, 1):
        print(f"Test Message {i}:")
        print(f"'{test_msg}'")
        print("-" * 30)

        try:
            # Process the message
            result = run_agent_on_message(test_msg)

            # Assert row shape (prevents regression of truncated output)
            row = result['database_row']
            required_fields = ['user_id', 'platform', 'timestamp', 'raw_incoming_message', 'identified_creator', 'discount_code_sent', 'conversation_status']
            assert all(field in row for field in required_fields), f"Missing fields in row: {set(required_fields) - set(row.keys())}"
            assert isinstance(row, dict), "Row must be dict"
            assert len(row) == len(required_fields), f"Expected {len(required_fields)} fields, got {len(row)}"

            # Print results
            print("Reply:")
            print(f"  {result['reply']}")
            print("\nDatabase Row (JSON):")
            # Ensure all expected fields are present
            row = result['database_row']
            fields_to_show = [
                'user_id', 'platform', 'timestamp', 'raw_incoming_message',
                'identified_creator', 'discount_code_sent', 'conversation_status'
            ]
            for field in fields_to_show:
                value = row.get(field, None)
                if value is None:
                    value = "None"
                print(f"  {field}: {value}")

        except Exception as e:
            print(f"Error processing message: {e}")

        print("\n" + "=" * 50 + "\n")

    print("Demo complete!")
    print("Note: This demo runs rules-only unless GOOGLE_API_KEY is set for LLM fallback.")
    print("(No real database needed - uses in-memory storage)")


if __name__ == "__main__":
    main()
