"""Data models for AI Discount Agent

This module defines Pydantic models that represent the core data structures
used throughout the system. All models include validation and type hints
for production reliability.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, validator


class Platform(Enum):
    """Supported social media platforms"""
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"
    WHATSAPP = "whatsapp"


class ConversationStatus(Enum):
    """Possible states of a conversation"""
    PENDING_CREATOR_INFO = "pending_creator_info"
    COMPLETED = "completed"
    ERROR = "error"
    OUT_OF_SCOPE = "out_of_scope"


class DetectionMethod(Enum):
    """Methods used to identify creator"""
    EXACT = "exact"
    FUZZY = "fuzzy"
    LLM = "llm"


class Intent(Enum):
    """Classification of user intent"""
    DISCOUNT_REQUEST = "discount_request"
    CREATOR_PROVIDE = "creator_provide"
    OUT_OF_SCOPE = "out_of_scope"


class IncomingMessage(BaseModel):
    """Represents an incoming message from a platform"""
    platform: Platform
    user_id: str = Field(..., min_length=1, description="Platform-specific user identifier")
    text: str = Field(..., min_length=1, description="Normalized message text")
    thread_id: Optional[str] = Field(None, description="Platform-specific conversation thread ID")
    message_id: Optional[str] = Field(None, description="Platform-specific message ID")

    @validator('text')
    def normalize_text(cls, v):
        """Normalize text to lowercase for consistent processing"""
        return v.lower().strip()


class AgentDecision(BaseModel):
    """Result of agent processing, determines next action"""
    reply_text: str = Field(..., description="Text to send back to user")
    template_key: str = Field(..., description="Template used for reply")
    identified_creator: Optional[str] = Field(None, description="Creator handle if detected")
    detection_method: Optional[DetectionMethod] = Field(None, description="How creator was identified")
    detection_confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Detection confidence")
    discount_code_sent: Optional[str] = Field(None, description="Code issued to user")
    conversation_status: ConversationStatus = Field(..., description="Final status of interaction")
    is_potential_influencer: Optional[bool] = Field(None, description="Engagement heuristic")


class InteractionRow(BaseModel):
    """Represents a database row for logging interactions"""
    user_id: str
    platform: str = Field(..., pattern='^(instagram|tiktok|whatsapp)$')
    ts: str = Field(..., pattern=r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$')
    raw_incoming_message: str
    identified_creator: Optional[str] = None
    discount_code_sent: Optional[str] = None
    conversation_status: str = Field(..., pattern='^(pending_creator_info|completed|error|out_of_scope)$')

    @validator('ts', pre=True)
    def ensure_utc_iso_format(cls, v):
        """Ensure timestamp is in ISO8601 UTC format"""
        if isinstance(v, datetime):
            # Convert to UTC and format as ISO8601 with 'Z' suffix
            utc_timestamp = v.astimezone(timezone.utc)
            return utc_timestamp.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
        return v


class EnrichmentData(BaseModel):
    """Simulated CRM enrichment data (Bonus B)"""
    follower_count: int = Field(..., ge=0, description="Simulated follower count")
    is_potential_influencer: bool = Field(..., description="Heuristic for potential influence")


class CreatorStats(BaseModel):
    """Statistics for a single creator"""
    creator_handle: str
    total_requests: int = Field(..., ge=0)
    total_completed: int = Field(..., ge=0)
    platform_breakdown: Dict[str, Dict[str, int]] = Field(
        default_factory=dict,
        description="Per-platform stats: {platform: {requests: int, completed: int}}"
    )


class AnalyticsSummary(BaseModel):
    """Summary analytics for /analytics/creators endpoint"""
    total_creators: int = Field(..., ge=0)
    total_requests: int = Field(..., ge=0)
    total_completed: int = Field(..., ge=0)
    creators: Dict[str, CreatorStats] = Field(
        default_factory=dict,
        description="Per-creator statistics"
    )


class Settings(BaseModel):
    """Application settings loaded from environment"""
    google_api_key: Optional[str] = Field(None, description="Gemini API key")
    db_url: str = Field(default="sqlite:///ai_discount_agent.db", description="Database connection URL")
    campaign_config_path: str = Field(default="./config/campaign.yaml", description="Path to campaign config")
    templates_path: str = Field(default="./config/templates.yaml", description="Path to reply templates")
    fastpath_enabled: bool = Field(default=True, description="Enable fast-path processing")
    log_level: str = Field(default="INFO", description="Logging level")
