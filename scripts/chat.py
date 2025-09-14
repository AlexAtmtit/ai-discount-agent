"""
Interactive CLI chat client for the AI Discount Agent server.

Usage:
  # Start the API server in another terminal
  ./run.sh

  # Start chat (defaults to instagram + user 'cli_user')
  python3 scripts/chat.py --server http://localhost:8000 --user cli_user --platform instagram --explain

Commands:
  /quit or /exit   - leave chat
  /help            - show help
  /reset           - POST /admin/reset (clears in-memory store)
  /reload          - POST /admin/reload (reloads YAML configs)
  /health          - GET /health (service status)
  /analytics       - GET /analytics/creators (summary)

Notes:
  - If GOOGLE_API_KEY is set, ambiguous messages may use LLM fallback.
  - The server responds with detection_method and detection_confidence.
  - Use --explain to print the agent trace if provided by the server.
"""

import argparse
import sys
import httpx
import yaml
import os


def print_help():
    print("Commands:")
    print("  /quit or /exit   - leave chat")
    print("  /help            - show this help")
    print("  /reset           - clear in-memory store on server")
    print("  /reload          - reload YAML configs on server")
    print("  /health          - show service health")
    print("  /analytics       - show creator analytics summary")


def main():
    parser = argparse.ArgumentParser(description="AI Discount Agent - CLI Chat")
    parser.add_argument("--server", default="http://localhost:8000", help="Server base URL")
    parser.add_argument("--user", default="cli_user", help="User id to use for this session")
    parser.add_argument("--platform", default="instagram", help="Platform: instagram|tiktok|whatsapp")
    parser.add_argument("--explain", action="store_true", help="Print agent trace if available")
    args = parser.parse_args()

    base = args.server.rstrip("/")

    print("AI DISCOUNT AGENT - CLI CHAT")
    print("Connected to:", base)
    print(f"Session: platform={args.platform}, user_id={args.user}")
    print("Type '/help' for commands. Press Ctrl+C or type '/quit' to exit.\n")

    with httpx.Client(timeout=10) as client:
        # Show health and config at start
        try:
            h = client.get(f"{base}/health").json()
            gemini = h.get("components", {}).get("gemini")
            print(f"HEALTH: gemini={gemini}")
        except Exception:
            print("HEALTH: (unavailable)")

        try:
            cfg_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "campaign.yaml")
            with open(cfg_path, "r") as f:
                cfg = yaml.safe_load(f)
            thresholds = cfg.get("thresholds", {})
            flags = cfg.get("flags", {})
            print("CONFIG:")
            print(f"  fuzzy_accept: {thresholds.get('fuzzy_accept')}")
            print(f"  enable_llm_fallback: {flags.get('enable_llm_fallback')}")
        except Exception:
            pass
        print()

        while True:
            try:
                text = input("> ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nBye!")
                return

            if not text:
                continue

            if text in ("/quit", "/exit"):
                print("Bye!")
                return
            if text == "/help":
                print_help()
                continue
            if text == "/reset":
                r = client.post(f"{base}/admin/reset")
                print(r.json())
                continue
            if text == "/reload":
                r = client.post(f"{base}/admin/reload")
                print(r.json())
                continue
            if text == "/health":
                r = client.get(f"{base}/health")
                print(r.json())
                continue
            if text == "/analytics":
                r = client.get(f"{base}/analytics/creators")
                print(r.json())
                continue

            # Send to /simulate
            payload = {
                "platform": args.platform,
                "user_id": args.user,
                "message": text,
            }
            try:
                resp = client.post(f"{base}/simulate", json=payload)
            except httpx.RequestError as e:
                print(f"Connection error: {e}")
                print("Is the server running? Try ./run.sh")
                continue

            if resp.status_code != 200:
                print(f"Error {resp.status_code}: {resp.text}")
                continue

            data = resp.json()
            print("INPUT:")
            print("  ", text)
            reply = data.get("reply", "")
            method = data.get("detection_method")
            conf = data.get("detection_confidence")
            row = data.get("database_row", {})
            trace = data.get("trace", [])

            print("REPLY:")
            print("  ", reply)
            if method:
                if conf is not None:
                    print(f"METHOD: {method} (confidence={conf:.2f})")
                else:
                    print(f"METHOD: {method}")

            creator = row.get("identified_creator")
            code = row.get("discount_code_sent")
            status = row.get("conversation_status")
            print("ROW:")
            for key in [
                "user_id",
                "platform",
                "timestamp",
                "raw_incoming_message",
                "identified_creator",
                "discount_code_sent",
                "conversation_status",
                "follower_count",
                "is_potential_influencer",
            ]:
                if key in row and row.get(key) is not None:
                    print(f"  {key}: {row.get(key)}")

            if args.explain and trace:
                print("TRACE:")
                for step in trace:
                    print("  -", step)


if __name__ == "__main__":
    main()
