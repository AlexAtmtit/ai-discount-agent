# System Architecture Patterns - AI Discount Agent

## Core Architecture Pattern: LangGraph State Machine

### Pattern Overview
The system uses **LangGraph** as the primary orchestration framework, implementing a finite state machine that coordinates processing through distinct, testable nodes.

**Benefits:**
- **Explicit State Management**: Every processing step is visible and auditable
- **Error Isolation**: Node failures are contained and recoverable
- **Testability**: Each node can be unit tested independently
- **Scalability**: Easy to parallelize or distribute processing stages

```python
# Core Pattern Implementation
workflow.add_node("normalize", normalize_node)
workflow.add_node("detect_intent", intent_node)
workflow.add_node("detect_creator", creator_node)
workflow.add_edge("normalize", "detect_intent")
```

## Pattern 1: Rule-First AI Processing

### Implementation Strategy
**Rule-Based First, AI Second:**
1. Exact text matching against known creator aliases
2. Fuzzy string matching with confidence thresholds
3. Bounded LLM fallback only for ambiguous cases

```python
def detect_creator(self, message: str) -> Optional[Tuple[str, DetectionMethod]]:
    # Step 1: Exact match (fastest, most reliable)
    result = self.exact_match(message)
    if result:
        return result

    # Step 2: Fuzzy match (configurable, deterministic)
    fuzzy_result = self.fuzzy_match(message)
    if fuzzy_result:
        return fuzzy_result

    # Step 3: LLM fallback (expensive, bounded)
    return self.llm_fallback(message)
```

**Rationale:**
- **Cost Efficiency**: Rules << Fuzzy << LLM
- **Reliability**: Deterministic rules preferred over statistical methods
- **Debuggability**: Rule matches are explainable, LLM calls are black boxes

## Pattern 2: Bounded LLM Execution

### Resource Control Pattern
**LLM Guardrails:**
- Maximum 2 attempts per message
- 1-second total execution budget
- 400ms timeout per attempt
- Exponential backoff between retries

```python
@dataclass
class GeminiConfig:
    max_attempts: int = 2
    total_budget_ms: int = 1000
    per_attempt_timeout_ms: int = 400
```

**Failure Modes:**
- **Timeout**: <400ms per attempt → Fall back to user clarification
- **Budget Exceeded**: >1000ms total → Fall back to user clarification
- **API Errors**: Network/Rate limit issues → Retry with backoff
- **Parse Errors**: Invalid LLM response → Fall back to user clarification

## Pattern 3: Intent Classification

### Dual-Classification Strategy
**Message Intent Analysis:**
```python
def is_in_scope(self, text: str) -> bool:
    # Include: Contains discount keywords OR creator names OR aliases
    return (has_discount_keywords(text) or
           contains_creator_name(text) or
           contains_alias(text))
```

**Creator Context Detection:**
```python
def detect_creator(self, text: str) -> str:
    # Extract which specific creator is being referenced
    return match_creator_or_alias(text)
```

**Separation of Concerns:**
- Intent classification: "Is this about a discount?"
- Creator detection: "Which creator specifically?"

## Pattern 4: Business Rule Enforcement

### Code Issuance Guardrails
**Idempotency Pattern:**
```python
def can_issue_code(self, platform: str, user_id: str) -> bool:
    """One code per user per campaign per platform"""
    # Check existing interactions for this user/platform
    # Return False if code already issued
    return len(previous_codes) == 0
```

**Anti-Fraud Measures:**
- Platform isolation: Instagram codes ≠ TikTok codes
- User identification: Platform-specific user IDs
- Rate limiting: Ready for integration
- Audit trail: Complete interaction logging

## Pattern 5: Enrichment Engine

### Simulated CRM Integration
**Deterministic Enrichment:**
```python
def enrich_creator(self, creator: str) -> EnrichmentData:
    """Hash-based pseudo-random enrichment for demo purposes"""
    follower_hash = hash(creator) % 900000
    follower_count = 10000 + follower_hash

    is_influencer = (follower_count > 50000 or
                    hash(creator) % 10 > 7)

    return EnrichmentData(
        follower_count=follower_count,
        is_potential_influencer=is_influencer
    )
```

**Production Extension:**
- Real CRM API integration
- Social media follower count lookups
- Engagement rate calculations
- Influencer tier classification

## Pattern 6: Configuration-Driven Behavior

### Externalized Configuration
**YAML-Based Configuration:**
```yaml
creators:
  mkbhd:
    code: MARQUES20
    aliases: [marques, brownlee, mkbhd]

thresholds:
  fuzzy_accept: 0.8
  fuzzy_reject: 0.6

flags:
  enable_llm_fallback: true
  enable_fuzzy_matching: true
```

**Hot-Reload Capability:**
```python
@app.post("/admin/reload")
async def reload_config():
    """Runtime configuration updates without restart"""
    global agent
    agent = AIDiscountAgent(CMAPPAIGN_CONFIG, TEMPLATES_CONFIG)
```

## Pattern 7: Memory-Based Storage Adapter

### Storage Abstraction Pattern
**Unified Storage Interface:**
```python
class MemoryStore:
    """Same interface as SQL-based storage"""

    def store_interaction(self, row: InteractionRow):
        self.interactions.append(row)

    def can_issue_code(self, platform: str, user_id: str) -> bool:
        # Business logic independent of storage backend
        return self._check_eligibility(platform, user_id)
```

**Production Ready:**
- Easy swap to SQLAlchemy + PostgreSQL
- Interface remains unchanged
- Business logic stays the same

## Anti-Patterns Avoided

### ❌ Avoided Patterns

1. **Direct LLM-first processing**: Too expensive, too slow, less reliable
2. **Custom ML models**: Overkill for pattern-matching problem
3. **Global state coupling**: Storage and business logic mixed
4. **Infinite retries**: Resource exhaustion risk
5. **Hard-coded configuration**: Makes changes require deployments

### ✅ Best Practices

- **Graceful degradation**: System works with LLM disabled
- **Defensive programming**: Extensive input validation
- **Logging everywhere**: Complete audit trail for debugging
- **Type safety**: Full Pydantic validation
- **Environment isolation**: Configuration external to code

## Performance Characteristics

### Throughput Expectations
- **Text processing**: <10ms per message
- **Creator detection (exact)**: <1ms
- **Fuzzy matching**: 5-20ms
- **LLM fallback**: 200-800ms (with caching: <10ms)
- **Total response time**: 1-1000ms depending on fallback needed

### Scalability Design
- **Stateless processing**: Individual messages independent
- **Horizontal scaling**: Containers can run N copies
- **Async processing**: Ready for concurrent request handling
- **Memory bounds**: O(1) memory usage per request
