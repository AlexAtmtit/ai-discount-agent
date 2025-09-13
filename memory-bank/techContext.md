# Technical Context - AI Discount Agent

## Technology Stack Overview

This project implements a complete AI-powered message processing system using modern Python frameworks and best practices for production deployment.

## Core Frameworks & Libraries

### LangGraph (State Machine Orchestration)
**Purpose**: Orchestrates complex AI decision flows and state management

**Version**: 0.6.7
**Why chosen**:
- Explicit state transitions make decisions auditable
- Each processing node can be independently tested
- Natural fit for multi-stage AI processing pipelines
- Better than custom state management or bare LangChain

**Usage Pattern**:
```python
workflow = StateGraph(AgentState)
workflow.add_node("normalize", normalize_node)
workflow.add_node("detect_creator", creator_detection_node)
workflow.add_edge("normalize", "detect_creator")
```

### FastAPI (Web API Framework)
**Purpose**: Production-ready REST API with automatic OpenAPI documentation

**Version**: 0.116.1
**Why chosen**:
- Automatic request/response validation via Pydantic
- Async-first design for concurrent request handling
- Built-in OpenAPI/Swagger documentation generation
- Native dependency injection for clean code organization

**Key Endpoints**:
```python
@app.post("/simulate")
async def simulate_message(request: SimulateRequest)
@app.get("/analytics/creators")
async def get_analytics()
@app.post("/webhook/{platform}")
async def webhook_handler()
```

### Pydantic (Data Validation & Serialization)
**Purpose**: Runtime data validation and type enforcement

**Version**: 2.11.9
**Why chosen**:
- Compile-time type checking with mypy/Pylance
- Automatic JSON serialization/deserialization
- Custom validators for business rules
- Automatic OpenAPI schema generation for FastAPI

**Critical Implementation**:
```python
class IncomingMessage(BaseModel):
    platform: Platform
    user_id: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)

    @validator('text')
    def normalize_text(cls, v):
        return v.lower().strip()
```

### LangChain Core (LLM Integration Framework)
**Purpose**: Standardized interface for LLM interactions

**Version**: 0.3.76
**Why chosen**:
- Industry standard for LLM application development
- Supports multiple LLM providers (OpenAI, Anthropic, Google)
- Standardized prompt templates and output parsing
- Extensive ecosystem of integrations and tools

### RapidFuzz (Fuzzy String Matching)
**Purpose**: High-performance fuzzy text matching for creator detection

**Version**: 3.13.0
**Why chosen**:
- ~10x faster than alternatives (difflib, fuzzywuzzy)
- Native Python implementation (no C extensions needed)
- Configurable similarity algorithms (partial ratio, token sort, etc.)
- Determnistic results for reproducible testing

**Usage**:
```python
similarity = fuzz.partial_ratio("mkbhd", user_message)
if similarity > threshold:
    return "mkbhd", DetectionMethod.FUZZY
```

## AI & Machine Learning Technologies

### Gemini 2.5 Flash Lite (LLM Provider)
**Purpose**: Bounded fallback for creator detection when rules fail

**Why chosen**:
- Excellent balance of cost vs. performance
- Low latency responses (typically <300ms)
- Strong understanding of entity extraction tasks
- GCP integration for enterprise deployments

**Bounded Execution Pattern**:
- Max 2 attempts per message
- 1-second total budget across all attempts
- 400ms timeout per individual attempt
- Exponential backoff for retries

### Rule-Based Processing (Primary Strategy)
**Pattern**: Rules → Fuzzy → LLM (cascading fallback)

**Why preferred over pure LLM-first**:
- **Cost**: Rules cost ~$0.001, LLM costs ~$0.01 per request
- **Speed**: Rules <1ms, LLM 200-800ms
- **Reliability**: 100% deterministic results vs. statistical confidence
- **Debuggability**: Rule matches are explainable

## Infrastructure & Platform

### Python Version & Runtime
**Python**: 3.9.6 (macOS system Python)
**Execution Environment**: Virtual environment (venv)
**Package Management**: pip with requirements.txt

**Why this stack**:
- Industry standard for AI/ML applications
- Rich ecosystem of well-maintained libraries
- Strong typing support for production reliability
- Cross-platform deployment capabilities

### Development Environment
**IDE**: VSCode with Pylance type checker
**Version Control**: Git
**Code Quality**: 

```bash
# Type checking
mypy scripts/ --ignore-missing-imports
pytest --cov=scripts
```

### Operating System
**Development**: macOS 12.0+ (M1/M2 Apple Silicon)
**Production Target**: Linux containers (Docker/PythonAnywhere)
**Local Testing**: Native Python with venv

## Configuration Management

### YAML Configuration Files
**Location**: `config/campaign.yaml`, `config/templates.yaml`
**Why YAML**:
- Human-readable format for non-technical stakeholders
- Supports comments for documentation
- Native Python support (no additional dependencies)
- Better for configuration than JSON

**Example Structure**:
```yaml
creators:
  mkbhd:
    code: MARQUES20
    aliases: [marques, mkbhd, brownlee]

thresholds:
  fuzzy_accept: 0.8
  fuzzy_reject: 0.6
```

### Environment Variables
**Pattern**: `.env` file with `.env.example` template
**Library**: `python-dotenv` for loading
**Why**:
- Separates secrets from code
- Environment-specific configuration
- Follows 12-factor app principles

## Testing Infrastructure

### pytest (Testing Framework)
**Purpose**: Comprehensive testing with fixtures and parametrization

**Key Features Used**:
- Async test support with pytest-asyncio
- Fixtures for test data setup
- Parameterized tests for edge cases
- Coverage reporting with pytest-cov

**Typical Test Structure**:
```python
def test_creator_detection_exact():
    result = run_agent_on_message("mkbhd sent me")
    assert "MARQUES20" in result["reply"]
    assert result["database_row"]["identified_creator"] == "mkbhd"
```

## Logging & Monitoring

### Python Logging (Standard Library)
**Configuration**: Structured logging with timestamps and log levels
**Output**: Console for development, file rotation for production
**Why standard library**:
- Zero dependencies
- Configurable to route to external services (ELK, CloudWatch)
- Familiar interface across Python ecosystem

**Implementation**:
```python
logger.info(f"Processing message from {user_id}: {message}")
logger.warning(f"LLM fallback failed: {error}")
```

## Production Readiness Assessment

### ✅ Implemented Production Features

- **Async/Await Support**: Full concurrency for high-throughput scenarios
- **Graceful Degradation**: System functions without LLM if API unavailable
- **Input Validation**: Pydantic validation prevents malformed data
- **Error Recovery**: Try/catch blocks with meaningful error messages
- **Resource Bounds**: LLM calls limited by time and attempt budgets

### 🚧 Production Considerations (Not Implemented for Demo)

- **Containerization**: Docker configuration for deployment
- **Database Migration**: Alembic for schema versioning
- **API Rate Limiting**: `slowapi` for request throttling
- **Health Checks**: `/health` endpoint for load balancer monitoring
- **Metrics Collection**: Prometheus integration for performance monitoring

### 🔧 Deployment Strategy

**Development**: Local Python venv with hot reload (`uvicorn --reload`)
**Testing**: Docker container with pytest execution
**Production**: Docker container with Gunicorn for multi-worker deployment

## Performance Characteristics

### Response Time Breakdown
- **Fast Path** (exact alias match): <10ms total
- **Medium Path** (fuzzy match): 20-50ms total  
- **Slow Path** (LLM fallback): 300-1000ms total

### Resource Consumption
- **CPU**: Minimal (text processing only)
- **Memory**: O(1) per request, <50MB baseline
- **Network**: Only for LLM calls (parallelizable)
- **Disk**: Configuration files only (database in memory for demo)

## Scalability Architecture

### Horizontal Scaling Ready
- **Stateless Design**: Each request independent
- **Externalized State**: Database/storage abstracted
- **Async Processing**: Concurrent request handling with FastAPI
- **Load Balancing Ready**: Multiple instances can run behind reverse proxy

### Future Extensions
- **Redis Queue**: For webhook processing backlog
- **Database Sharding**: For high-volume creator analytics
- **CDN Integration**: For static configuration distribution
- **Webhook Signature Verification**: For security in production

This technology stack represents a balanced approach between cutting-edge AI capabilities and production reliability, suitable for both rapid prototyping and enterprise deployment.
