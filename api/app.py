"""FastAPI application for AI Discount Agent

Production-ready web API with endpoints for simulation, webhooks, and analytics.
Implements async processing and proper error handling.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import logging
import os
import yaml
from typing import Optional, Dict, Any

from scripts.agent_graph import AIDiscountAgent
from scripts.models import Platform
from scripts.store import get_store
from scripts.gemini_client import init_gemini, GeminiConfig

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="AI Discount Agent",
    version="1.0.0",
    description="Automated discount code distribution via DMs"
)

# Load configuration
CAMPAIGN_CONFIG = "config/campaign.yaml"
TEMPLATES_CONFIG = "config/templates.yaml"

# Initialize components
agent = AIDiscountAgent(CAMPAIGN_CONFIG, TEMPLATES_CONFIG)

# Optional Gemini initialization
api_key = os.getenv("GOOGLE_API_KEY")
if api_key:
    gemini_config = GeminiConfig(
        api_key=api_key,
        max_attempts=2,
        total_budget_ms=1000,
        per_attempt_timeout_ms=400,
        model_version="gemini-2.5-flash-lite"
    )
    init_gemini(gemini_config)
    logger.info("Gemini client initialized with API key")

# Request/Response models
class SimulateRequest(BaseModel):
    """Request for /simulate endpoint"""
    platform: str = "instagram"
    user_id: str = "demo_user"
    message: str
    message_id: Optional[str] = None
    thread_id: Optional[str] = None

class SimulateResponse(BaseModel):
    """Response for /simulate endpoint"""
    reply: str
    database_row: Dict[str, Any]

class WebhookRequest(BaseModel):
    """Webhook request from platform"""
    # Platform-specific webhook payload structure
    # Simplified for demo - in production would handle actual webhook signatures
    user_id: str
    message: str
    message_id: Optional[str] = None
    thread_id: Optional[str] = None

class AnalyticsResponse(BaseModel):
    """Response for /analytics/creators endpoint"""
    total_creators: int
    total_requests: int
    total_completed: int
    creators: Dict[str, Dict[str, Any]]


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "AI Discount Agent API",
        "version": "1.0.0",
        "endpoints": {
            "simulate": "/simulate (POST) - test message processing",
            "analytics": "/analytics/creators (GET) - campaign analytics",
            "health": "/health (GET) - service health check"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "ai-discount-agent",
        "components": {
            "agent": "loaded",
            "store": "in_memory",
            "gemini": "ready" if api_key else "no_key"
        }
    }


@app.post("/simulate", response_model=SimulateResponse)
async def simulate_message(request: SimulateRequest):
    """Process a message through the agent pipeline (for testing)

    This endpoint demonstrates end-to-end message processing without
    external platform integration.
    """
    try:
        logger.info(f"Simulating message processing: {request.message} from {request.user_id}")

        # Create incoming message object
        incoming = {
            "platform": request.platform if isinstance(request.platform, str) else request.platform,
            "user_id": request.user_id,
            "text": request.message,
            "message_id": request.message_id,
            "thread_id": request.thread_id
        }

        # Note: For simplicity, we're using the demo function directly
        # In production, this would use the full agent pipeline
        from scripts.agent_graph import run_agent_on_message

        # Map to expected format
        result = run_agent_on_message(
            request.message,
            platform=request.platform,
            user_id=request.user_id
        )

        return SimulateResponse(
            reply=result["reply"],
            database_row=result["database_row"]
        )

    except Exception as e:
        logger.error(f"Simulation error: {e}")
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


@app.get("/analytics/creators", response_model=AnalyticsResponse)
async def get_analytics():
    """Get analytics summary by creator

    Returns aggregated statistics for campaign performance tracking.
    """
    try:
        store = get_store()
        summary = store.get_analytics()

        return AnalyticsResponse(
            total_creators=summary.total_creators,
            total_requests=summary.total_requests,
            total_completed=summary.total_completed,
            creators={
                k: v.dict() for k, v in summary.creators.items()
            }
        )

    except Exception as e:
        logger.error(f"Analytics error: {e}")
        raise HTTPException(status_code=500, detail=f"Analytics failed: {str(e)}")


@app.post("/webhook/{platform}")
async def webhook_handler(platform: str, request: WebhookRequest):
    """Handle webhook messages from platforms (placeholder)

    In production, this would:
    - Verify webhook signatures
    - Fast-path processing
    - Queue for background processing
    - Store interaction data

    For demo, returns immediate acknowledgment.
    """
    try:
        logger.info(f"Webhook received from {platform}: {request.message}")

        # In production: validate signature, normalize payload, check fast-path conditions
        # For demo: just acknowledge

        return {
            "status": "received",
            "ack_id": f"ack_{request.message_id or 'demo'}",
            "note": "Full webhook processing would be implemented in production"
        }

    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise HTTPException(status_code=500, detail=f"Webhook failed: {str(e)}")


@app.post("/admin/reload")
async def reload_config():
    """Reload configuration from YAML files

    Allows hot-reloading of campaign and template configurations
    without restarting the service.
    """
    try:
        global agent

        # Reload configurations
        agent = AIDiscountAgent(CAMPAIGN_CONFIG, TEMPLATES_CONFIG)

        logger.info("Configuration reloaded successfully")
        return {"status": "reloaded", "message": "Configuration updated"}

    except Exception as e:
        logger.error(f"Config reload error: {e}")
        raise HTTPException(status_code=500, detail=f"Reload failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")

    logger.info(f"Starting server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)
