# AI Discount Agent

A production-minded backend system that automates discount code distribution in DMs across Instagram, TikTok, and WhatsApp.

## Architecture Overview

### System Diagram
```mermaid
sequenceDiagram
  participant User
  participant Webhook
  participant Agent
  participant Platform
  participant DB

  User->>Webhook: DM text
  Webhook->>Agent: normalized message
  Agent->>Agent: detect creator or ask
  Agent->>Platform: reply text
  Platform-->>User: message delivered
  Agent->>DB: write interaction row
```

```mermaid
sequenceDiagram
  participant User
  participant Webhook
  participant Agent
  participant Platform
  participant DB

  User->>Webhook: DM text
  Webhook->>Agent: normalized message
  Agent->>Agent: detect creator or ask
  Agent->>Platform: reply text
  Platform-->>User: message delivered
  Agent->>DB: write interaction row
```

flowchart TD
  P[DM from IG or TT or WA]
  W[Webhook receive]
  N[Normalize message]
A[Agent - LangGraph
 detect creator
 or ask for creator]
  R[Send reply via platform API]
  D[Log interaction in DB]
  X[Analytics read DB]

  P --> W --> N --> A --> R --> D --> X

## Quick Demo (2 minutes)

```bash
git clone <your-repo-url>
cd ai-discount-agent
./setup.sh              # Setup virtual environment and dependencies
./demo.sh               # Run the standalone agent demo
```

### Sample Output
```
Input: I saw this on mkbhd's story, I need the discount
Reply: Here's your discount code from mkbhd: MARQUES20 🎉

Input: mkbhd discount code please
Reply: Here's your discount code from mkbhd: MARQUES20 🎉

Input: discount
Reply: Thanks for your message! Which creator sent you? I have codes forCasey Neistat, Marques Brownlee, Lily Singh, or Peter McKinnon. 😊
```

## Approach Overview

We prioritize a hybrid detection strategy: exact alias matching first, then fuzzy matching, finally bounded LLM fallback. The system avoids guessing to prevent incorrect code distribution.

**Key decisions:**
- **In-memory storage for demo** (files are for documentation)
- **Bounded LLM** (2 attempts, 1s budget, only allow-listed responses)
- **Intent detection** prevents spam/abuse by asking out irrelevant messages
- **One code per user per platform** prevents fraud

First, we address state and idempotency. Each platform is treated separately. The unit of truth is "campaign + platform + user," and each message has a unique message ID for unique identification. This approach maintains simplicity and security by ensuring that each user has their own unique code for each campaign on each platform.

We use a hybrid processing model with a fast webhook acknowledgment. A worker does most of the work, and we can reply inline if a message contains a clear exact alias and the user hasn't received a code yet. Otherwise, we queue and reply from the worker to avoid timeouts and maintain speed.

Creator detection is rule-first. First, we normalize the text, then we check for exact aliases and use a tight fuzzy match. If the rules cannot decide, we call Gemini 2.5 Flash Lite once within a strict budget with allow-listed JSON. If it times out or appears incorrect, we do not make an educated guess. We ask the user to name the creator.

The code policy is straightforward. Each user is limited to one code per campaign per platform. The first confident match gets attribution. Resending returns the same code without creating a new issuance.

We use LangGraph to express the decision flow. The graph is a single pass: normalize → exact → fuzzy → Gemini → decide. The worker calls the graph and receives a user reply and a row for logging.

Configuration lives outside of the code. Creators, codes, aliases, thresholds, and templates are in YAML. We can hot-reload them. Secrets come from environment variables.

Persistence follows the assignment of one simple table. We store the platform, user, timestamp, raw text, identified creator (if applicable), discount code (if applicable), and conversation status. In production, we would add unique constraints for webhook deduplication and issuance guards. We include these as commented "notes" in the schema file.

This design is scalable. If the number of creators grows to the hundreds or thousands, we can swap the matcher under the same interface (Aho–Corasick + n-gram retrieval). The agent, worker, and API would remain the same.



## Agent Function (Step 2)

The core requirement is met through `run_agent_on_message()`:

```python
from scripts.agent_graph import run_agent_on_message

result = run_agent_on_message("mkbhd sent me")
# Returns: {"reply": str, "database_row": dict}
```

## Tooling Justification

**LangGraph + LangChain**: Explicit state machines for reliable AI workflows
**Pydantic**: Type safety and validation throughout the system
**FastAPI**: Production-ready web framework for high-throughput APIs
**RapidFuzz**: Efficient fuzzy string matching
**Gemini 2.5 Flash Lite**: Cost-effective LLM with bounded execution

Each tool is chosen for its production maturity and operational reliability.

## Database Schema

The provided `design/schema.sql` meets the assignment requirements:

```sql
CREATE TABLE interactions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id TEXT NOT NULL,
  platform TEXT NOT NULL,
  ts TEXT NOT NULL,
  raw_incoming_message TEXT NOT NULL,
  identified_creator TEXT NULL,
  discount_code_sent TEXT NULL,
  conversation_status TEXT NOT NULL
);
```

Production notes include unique constraints for webhook dedupe and issuance guards.

## LLM Provider Configuration

**Model**: Gemini 2.5 Flash Lite via google-generativeai
**Execution**: Bounded with 2 attempts, 1s total budget, 400ms per attempt
**Validation**: Strict JSON mode with {"creator":"<allow-listed|none>"} response
**Fallback**: If LLM fails after retries, system asks for creator clarification

Set your key:
```bash
export GOOGLE_API_KEY=your_google_api_key_here
```

## Bonus Features

### A) Multi-Platform Considerations
See `design/multi-platform.md` for webhook signature validation, reply windows (24h), and platform-specific restrictions (e.g., WhatsApp templates). The normalizer handles all platforms uniformly.

### B) Enrichment & Lead Scoring
Agent enrichment generates deterministic follower counts and potential influencer flags when creator is identified:
```json
{
  "follower_count": 15000000,
  "is_potential_influencer": true
}
```

### C) Analytics Endpoint
```
GET /analytics/creators
```
Returns aggregated summary of codes distributed by creator and platform.

## API Endpoints

### `/simulate` (POST)
End-to-end message processing for testing:
```json
{
  "platform": "instagram",
  "user_id": "user123",
  "message": "discount from mkbhd"
}
```
Response:
```json
{
  "reply": "Here's your discount code from mkbhd: MARQUES20 🎉",
  "database_row": { ... }
}
```

### `/webhook/{platform}` (POST)
Production webhook endpoint with fast-path optimization.

### `/analytics/creators` (GET)
Summary statistics for campaign effectiveness.

## Testing

Run the test suite:
```bash
./test.sh
```

The suite covers:
- **Detection logic**: exact/alias, fuzzy, intent classification
- **Integration tests**: end-to-end /simulate flow
- **Idempotency**: one-code-per-user guarantee
- **Error handling**: LLM timeout/retry, malformed inputs
- **Bonus features**: enrichment data, analytics aggregation

## Campaign Configuration

Creator codes and aliases in `config/campaign.yaml`:

```yaml
creators:
  casey_neistat:
    code: CASEY15OFF
    aliases:
      - casey
      - neistat
      - @casey
  mkbhd:
    code: MARQUES20
    aliases:
      - marques
      - mkbhd
      - @mkbhd
    threshold: 0.8  # Fuzzy match threshold
```

Reply templates in `config/templates.yaml`:

```yaml
replies:
  issue_code: "Here's your discount code from {creator_handle}: {discount_code} 🎉"
  ask_creator: "Which creator sent you? I have codes from Casey Neistat, Marques Brownlee, Lily Singh, Peter McKinnon."
  ambiguous: "Could you clarify which creator sent you? {creator_handle} or {other_creator}?"
```

## Setup Instructions

1. **Clone and install**:
   ```bash
   git clone <your-repo-url>
   cd ai-discount-agent
   ./setup.sh
   ```

2. **Optional LLM setup**:
   ```bash
   export GOOGLE_API_KEY=your_api_key
   ```

3. **Run demo**:
   ```bash
   ./demo.sh
   ```

4. **Start server**:
   ```bash
   ./run.sh  # FastAPI server on localhost:8000
   ```


