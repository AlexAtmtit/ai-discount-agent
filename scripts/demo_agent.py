"""Real AI Discount Agent Demo

This script demonstrates the complete AI agent's functionality by running it on
real processing logic from scripts/agent_graph.py, making actual LLM calls when needed.

Features:
- Real AIDiscountAgent processing (not simulation)
- Actual LLM API calls with graceful fallback
- Production-grade AI agent demonstration
- Comprehensive test coverage (15+ scenarios)

Usage: python scripts/demo_agent.py [--explain] [--reset] [--mock-llm {success,none}]
"""

import logging
import sys
import os
import argparse

# Add the project root directory to Python path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import REAL AI agent and models (not simulation)
from scripts.agent_graph import AIDiscountAgent
from scripts.models import IncomingMessage, DetectionMethod, ConversationStatus
from scripts.store import get_store
from scripts.gemini_client import LLMResult
from datetime import datetime, timezone
import yaml
import asyncio

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Comprehensive test suite demonstrating system capabilities
# Each item: (message, description, opts)
TEST_CASES = [
    # Exact Match Cases
    ("mkbhd sent me", "Exact match - mkbhd", {}),
    ("Hi, Casey sent me", "Exact match - casey alias", {}),
    ("mkbhd discount code please", "Exact match - mkbhd with context", {}),
    ("lily_singh sent me here", "Exact match - lily_singh", {}),
    ("peter_mckinnon discount", "Exact match - peter_mckinnon", {}),

    # Fuzzy true positives (no alias tokens)
    ("marqes brwnli promo", "Fuzzy match - mkbhd typos", {}),
    ("casey nistt discount", "Fuzzy match - casey_neistat misspelling", {}),

    # From-mention fuzzy-aware intent
    ("from @mkbd", "From-mention (typo) - mkbhd", {}),
    ("from lilly_sing", "From-mention (typo) - lily_singh", {}),

    # LLM fallback (terminal none)
    ("promo code", "LLM terminal - missing creator", {}),
    ("unknown creator here", "LLM terminal - completely unknown", {}),

    # LLM fallback (success demo) - disable fuzzy for this case if API key is set
    ("marq brnli sent me a coupon", "LLM success demo (rules disabled)", {"llm_success": True}),

    # Normalization showcase (noise tolerance)
    ("mkbhd!!!", "Normalization - trailing punctuation", {}),
    ("   MkBhD    SeNt   Me   ", "Normalization - whitespace/case", {}),
    ("casey-neistat discount", "Normalization - hyphenation", {}),
    ("Lily’s video discount", "Normalization - unicode apostrophe", {}),
    ("I came from @mkbhd, need code", "Normalization - mention with punctuation", {}),
    ("mkbhd 😃🔥 sent me", "Normalization - emoji noise", {}),

    # Out-of-scope Detection Cases
    ("what's up", "Intent filter - greeting", {}),
    ("hello", "Intent filter - pure greeting", {}),
    ("nice video", "Intent filter - no discount mention", {}),
]

def main():
    parser = argparse.ArgumentParser(description="AI Discount Agent Demo")
    parser.add_argument("--explain", action="store_true", help="Print agent trace (explain mode)")
    parser.add_argument("--reset", action="store_true", help="Reset in-memory store before running")
    parser.add_argument("--mock-llm", choices=["success", "none"], help="Mock LLM fallback outcome (no real API calls)")
    args = parser.parse_args()

    print("AI DISCOUNT AGENT - ASSIGNMENT DEMONSTRATION")
    print("=" * 70)
    print("Using: AIDiscountAgent (Real Processing Pipeline)")
    print("Features: Actual LLM calls + Production-grade AI")
    print("run_agent_on_message(message: str) → {reply:, database_row:}")
    print("=" * 70)
    print()

    # Reset store if requested
    if args.reset:
        get_store().clear_data()
        print("💾 Store reset: cleared previous interactions.\n")

    # Mock LLM if requested and clearly label it
    mock_llm_note = None
    if args.mock_llm:
        import scripts.gemini_client as gc

        class FakeGeminiClient:
            async def detect_creator(self, message: str) -> LLMResult:
                if args.mock_llm == "success":
                    return LLMResult(
                        creator="mkbhd",
                        detection_method=DetectionMethod.LLM,
                        detection_confidence=0.8,
                        model_version="mock-llm",
                        attempts=1,
                        total_latency_ms=10,
                        error_reason=None,
                    )
                else:
                    return LLMResult(
                        creator=None,
                        detection_method=DetectionMethod.LLM,
                        detection_confidence=0.0,
                        model_version="mock-llm",
                        attempts=1,
                        total_latency_ms=10,
                        error_reason="mock_none",
                    )

        gc.get_gemini_client = lambda: FakeGeminiClient()
        mock_llm_note = f"MOCK LLM ACTIVE: outcome={args.mock_llm}"

    # Set explain mode flag for downstream printing
    if args.explain:
        os.environ["DEMO_EXPLAIN"] = "1"

    # Initialize success counter
    success_count = 0
    total_tests = len(TEST_CASES)

    # Initialize REAL AI agent (not simulation)
    print("🚀 Initializing AI Discount Agent...")
    agent = AIDiscountAgent("config/campaign.yaml", "config/templates.yaml")
    print("✅ Agent initialized successfully!\n")
    # Print active config thresholds/flags
    with open("config/campaign.yaml", "r") as f:
        cfg = yaml.safe_load(f)
    thresholds = cfg.get("thresholds", {})
    flags = cfg.get("flags", {})
    print("CONFIG:")
    print(f"  fuzzy_accept: {thresholds.get('fuzzy_accept')}")
    print(f"  enable_llm_fallback: {flags.get('enable_llm_fallback')}")
    if mock_llm_note:
        print(f"  {mock_llm_note}")
    print()

    for i, (message, description, opts) in enumerate(TEST_CASES, 1):
        print(f"🎯 TEST CASE {i}: {description}")
        print("INPUT:")
        print(f"  {message}")
        print("-" * 40)

        # Process message using REAL AI AGENT (not simulation)
        try:
            # Determine if this case should force LLM path (disable fuzzy) — only if API key present
            force_llm = bool(opts.get("llm_success")) and bool(os.getenv("GOOGLE_API_KEY"))

            # Choose agent: base agent, or a temporary with fuzzy disabled
            active_agent = agent
            if force_llm:
                active_agent = AIDiscountAgent("config/campaign.yaml", "config/templates.yaml")
                active_agent.matcher.flags["enable_fuzzy_matching"] = False

            incoming = IncomingMessage(platform="instagram", user_id=f"demo_user_{i}", text=message)

            print("🚀 Processing with AI Agent...")

            # Use REAL agent processing and build row from pipeline
            decision = active_agent.process_message(incoming)
            row_model = active_agent.create_interaction_row(incoming, decision)
            get_store().store_interaction(row_model)

            # Convert decision to result format
            result = {
                "reply": decision.reply_text,
                "creator": decision.identified_creator,
                "method": decision.detection_method.value.lower() if decision.detection_method else "unknown",
                "status": decision.conversation_status.value,
                "code": decision.discount_code_sent,
                "trace": decision.trace or [],
                "row": row_model.model_dump(),
            }

            print("✅ Processing completed!")
            success_count += 1

        except Exception as e:
            print(f"❌ ERROR: {e}")
            print("   ⇧ Zig This test failed, but continuing with next...")
            result = {
                "reply": "Processing error occurred",
                "creator": None,
                "method": "error",
                "status": "error",
                "code": None
            }

        print()  # Add spacing

        # Show METHOD DETECTION DETAILS
        print("METHOD:")
        method = result.get('method', 'unknown')
        status = result.get('status')

        if method == 'exact':
            print("   📏 EXACT MATCH: Creator found directly in rules database")
        elif method == 'fuzzy':
            print("   🌀 FUZZY MATCH: Creator found via similarity algorithm")
        elif method == 'llm':
            print("   🤖 LLM PROCESSING: Creator found via Gemini AI analysis")
        elif status == 'pending_creator_info':
            print("   🤖 LLM/Rules ASK: No confident creator, asking user for clarification")
        elif status == 'out_of_scope':
            print("   🚫 INTENT FILTER: Message identified as non-discount related")
            print("     • Detection: No discount/creator signal")
        else:
            print("   ❓ METHOD UNAVAILABLE: Creator detection method not specified")
        print()

        print("REPLY:")
        print(f"  {result['reply']}")
        print()

        print("ROW:")
        row = result["row"]
        for key in [
            'user_id', 'platform', 'timestamp', 'raw_incoming_message',
            'identified_creator', 'discount_code_sent', 'conversation_status',
            'follower_count', 'is_potential_influencer'
        ]:
            print(f"  {key}: {row.get(key)}")

        # Trace in explain mode
        if 'trace' in result and result['trace']:
            from argparse import Namespace
            # Only print if --explain is enabled
            # We can't access args here directly, so detect via env toggle
            if os.environ.get("DEMO_EXPLAIN", "0") == "1":
                print()
                print("TRACE:")
                for step in result['trace']:
                    print(f"  - {step}")

        # Notes for mock LLM
        if os.environ.get("DEMO_EXPLAIN", "0") == "1" and mock_llm_note:
            print()
            print("NOTES:")
            print(f"  {mock_llm_note}")

        print("\n" + "=" * 60 + "\n")

    # Print analytics summary at end
    summary = get_store().get_analytics()
    print("ANALYTICS SUMMARY:")
    print(f"  total_creators: {summary.total_creators}")
    print(f"  total_requests: {summary.total_requests}")
    print(f"  total_completed: {summary.total_completed}")
    if summary.creators:
        print("  by creator:")
        for creator, stats in summary.creators.items():
            print(f"   - {creator}: requests={stats.total_requests}, completed={stats.total_completed}")
    # Enrichment printed from row above; no static demo mapping

if __name__ == "__main__":
    main()
