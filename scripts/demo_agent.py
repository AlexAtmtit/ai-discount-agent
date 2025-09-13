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
    "lily_singh sent me here"
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

            # Print results
            print("Reply:")
            print(f"  {result['reply']}")
            print("\nDatabase Row (JSON):")
            for key, value in result['database_row'].items():
                print(f"  {key}: {value}")

        except Exception as e:
            print(f"Error processing message: {e}")

        print("\n" + "=" * 50 + "\n")

    print("Demo complete!")
    print("Note: This demo uses mocked detection and does not require a real database.")
    print("For LLM fallback, set GOOGLE_API_KEY environment variable.")


if __name__ == "__main__":
    main()
