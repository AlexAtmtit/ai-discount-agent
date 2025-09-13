"""Gemini client for AI Discount Agent

This module provides a bounded LLM client for creator detection fallback.
It implements strict JSON parsing, retry logic with timeouts, and bounded execution.
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

import google.generativeai as genai
from google.generativeai import types as genai_types

from scripts.models import DetectionMethod

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class GeminiConfig:
    """Configuration for Gemini API calls"""
    api_key: Optional[str]
    max_attempts: int = 2
    total_budget_ms: int = 2000  # Increased budget
    per_attempt_timeout_ms: int = 900  # Increased timeout
    model_version: str = "gemini-2.5-flash-lite"


@dataclass
class LLMResult:
    """Result of LLM processing"""
    creator: Optional[str]
    detection_method: DetectionMethod
    detection_confidence: float
    model_version: str
    attempts: int
    total_latency_ms: int
    error_reason: Optional[str]


class GeminiClient:
    """Bounded Gemini client for creator detection"""

    def __init__(self, config: GeminiConfig, campaign_config: Dict[str, Any]):
        """Initialize Gemini client with configuration

        Args:
            config: Gemini configuration parameters
            campaign_config: Campaign configuration with creators and aliases
        """
        self.config = config
        self.campaign_config = campaign_config
        self.allowed_creators = {
            "casey_neistat", "mkbhd", "lily_singh", "peter_mckinnon"
        }

        # Build alias hints from campaign config
        self.alias_hints = self._build_alias_hints()

        if config.api_key:
            genai.configure(api_key=config.api_key)

    def _build_alias_hints(self) -> Dict[str, List[str]]:
        """Build alias hints from campaign configuration

        Returns:
            Dictionary mapping creator handles to lists of alias hints
        """
        hints = {}
        if 'creators' in self.campaign_config:
            for creator, data in self.campaign_config['creators'].items():
                aliases = []
                # Add the main creator name
                aliases.append(creator)
                # Add aliases from config
                if 'aliases' in data:
                    aliases.extend(data['aliases'])
                # Add common variations based on patterns
                if creator == 'mkbhd':
                    aliases.extend(['marques', 'brownlee', 'mkbhd', 'marqes', 'mr brownlee'])
                elif creator == 'casey_neistat':
                    aliases.extend(['casey', 'caseyy', 'mr neistat'])
                elif creator == 'lily_singh':
                    aliases.extend(['lily', 'superwoman', 'lili', 'lilly'])
                elif creator == 'peter_mckinnon':
                    aliases.extend(['peter', 'pete', 'mckinonn'])

                hints[creator] = list(set(aliases))  # Remove duplicates

        return hints

    def _validate_creator_response(self, response_text: str) -> Optional[str]:
        """Validate LLM response against allow-list

        Args:
            response_text: Raw JSON response from LLM

        Returns:
            Creator handle if valid, None otherwise
        """
        try:
            # Parse JSON response
            response = json.loads(response_text)

            # Check strict structure
            if not isinstance(response, dict) or "creator" not in response:
                logger.warning(f"Invalid response structure: {response}")
                return None

            creator = response["creator"]

            if creator == "none":
                # Explicit "none" is valid - TERMINAL response (non-retryable)
                logger.info("✅ LLM TERMINAL: 'none' - no creator detected (non-retryable)")
                return None

            # Validate against allow-list
            if isinstance(creator, str) and creator in self.allowed_creators:
                logger.info(f"✅ LLM SUCCESS: validated {creator}")
                return creator

            logger.warning(f"Unallowed creator in response: {creator}")
            return None

        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON in LLM response: {e}")
            return None

    async def _single_attempt(self, message: str, timeout_ms: int) -> Optional[str]:
        """Make a single LLM call with timeout

        Args:
            message: User message to classify
            timeout_ms: Timeout for this attempt in ms

        Returns:
            Creator handle if detected, None otherwise
        """
        try:
            if not self.config.api_key:
                logger.warning("No API key provided for Gemini")
                return None

            # Configure model
            model = genai.GenerativeModel(
                model_name=self.config.model_version,
                generation_config=genai_types.GenerationConfig(
                    temperature=0.0,  # Deterministic responses
                    candidate_count=1,
                    response_mime_type="application/json",
                    response_schema={
                        "type": "object",
                        "properties": {
                            "creator": {
                                "type": "string",
                                "enum": ["none", "casey_neistat", "mkbhd", "lily_singh", "peter_mckinnon"]
                            }
                        },
                        "required": ["creator"]
                    }
                )
            )

            # Craft detailed prompt with system context and examples
            alias_section = ""
            for creator, aliases in self.alias_hints.items():
                if creator in self.allowed_creators:
                    alias_str = ', '.join([f'"{alias}"' for alias in aliases])
                    alias_section += f"- {creator}: {alias_str}\n"

            prompt = f"""
# System Instructions
You are a short-text classifier. Map a user message to ONE creator handle from an allowed list, or "none" if it clearly does not refer to any of them.

You MUST consider misspellings, nicknames, real names, and common variations. Pick the closest matching creator when there is a clear referent; otherwise return "none".

# Allowed Output Schema
{{"creator":"casey_neistat|mkbhd|lily_singh|peter_mckinnon|none"}}

# Creator Alias Hints
{alias_section.strip()}

# Rules
- If the message clearly refers to a creator via a misspelling or nickname, choose that creator.
- If uncertain or unrelated, choose "none".
- Output only JSON as: {{"creator":"<one|none>"}}

# Examples
Q: "promo from marqes brwnli pls"
A: {{"creator":"mkbhd"}}

Q: "techbuddy sent me a code"
A: {{"creator":"none"}}

Q: "caseyy discount?"
A: {{"creator":"casey_neistat"}}

# User Message
Message: "{message}"
"""

            # Make call with timeout
            response = await asyncio.wait_for(
                model.generate_content_async(prompt),
                timeout=timeout_ms / 1000.0
            )

            if response.text:
                return self._validate_creator_response(response.text.strip())

            logger.warning("Empty response from Gemini")
            return None

        except asyncio.TimeoutError:
            logger.warning(f"Gemini timeout after {timeout_ms}ms")
            return None
        except Exception as e:
            logger.warning(f"Gemini API error: {e}")
            return None

    async def detect_creator(self, message: str) -> LLMResult:
        """Run bounded LLM detection with retries

        Args:
            message: User message to classify

        Returns:
            LLMResult with detection outcome
        """
        start_time = time.time()
        attempts = 0
        last_error = None

        logger.info(f"Starting LLM detection for message: {message}")

        while attempts < self.config.max_attempts:
            attempts += 1
            elapsed_ms = (time.time() - start_time) * 1000

            # Check if we're over budget
            if elapsed_ms > self.config.total_budget_ms:
                logger.warning(f"Exhausted total budget ({self.config.total_budget_ms}ms) "
                             f"after {attempts} attempts")
                break

            # Calculate remaining budget and timeout
            remaining_budget = int(self.config.total_budget_ms - elapsed_ms)
            attempt_timeout = min(self.config.per_attempt_timeout_ms, remaining_budget)

            logger.info(f"Attempt {attempts}/{self.config.max_attempts}, "
                       f"budget left: {remaining_budget:.0f}ms")

            try:
                creator = await self._single_attempt(message, attempt_timeout)

                if creator is not None:
                    # Successful detection
                    total_time = (time.time() - start_time) * 1000
                    logger.info(f"🎯 LLM SUCCESS! method=llm, "
                               f"llm_attempt={attempts}, "
                               f"llm_latency_ms={int(total_time)}, "
                               f"model_version={self.config.model_version}, "
                               f"creator={creator}")
                    return LLMResult(
                        creator=creator,
                        detection_method=DetectionMethod.LLM,
                        detection_confidence=0.8,  # Valid creator confidence
                        model_version=self.config.model_version,
                        attempts=attempts,
                        total_latency_ms=int(total_time),
                        error_reason=None
                    )

                elif creator is None and attempts == 1:
                    # LLM returned "none" on first attempt - TERMINAL (don't retry)
                    terminal_latency = int((time.time() - start_time) * 1000)
                    logger.info(f"🚫 LLM TERMINAL: attempt={attempts}, "
                               f"llm_attempt_timeout_ms={self.config.per_attempt_timeout_ms}, "
                               f"llm_latency_ms={terminal_latency}, "
                               f"model_version={self.config.model_version} - "
                               "'none' response is non-retryable")
                    return LLMResult(
                        creator=None,
                        detection_method=DetectionMethod.LLM,
                        detection_confidence=0.0,
                        model_version=self.config.model_version,
                        attempts=attempts,
                        total_latency_ms=terminal_latency,
                        error_reason="LLM returned 'none' (terminal)"
                    )

            except Exception as e:
                last_error = str(e)
                logger.warning(f"Attempt {attempts} failed: {e}")

            # Add small jitter/backoff between attempts
            if attempts < self.config.max_attempts:
                backoff_ms = 10 + (attempts * 5)  # Progressive backoff
                await asyncio.sleep(backoff_ms / 1000.0)

        # All attempts exhausted or budget exceeded
        total_time = (time.time() - start_time) * 1000

        if not self.config.api_key:
            last_error = "No API key configured"

        return LLMResult(
            creator=None,
            detection_method=DetectionMethod.LLM,
            detection_confidence=0.0,
            model_version=self.config.model_version,
            attempts=attempts,
            total_latency_ms=int(total_time),
            error_reason=last_error or "Retry limit exceeded"
        )


# Global client instance (will be configured on startup)
_gemini_client: Optional[GeminiClient] = None


def init_gemini(config: GeminiConfig, campaign_config: Dict[str, Any]) -> None:
    """Initialize global Gemini client

    Args:
        config: Gemini configuration
        campaign_config: Campaign configuration with creators and aliases
    """
    global _gemini_client
    _gemini_client = GeminiClient(config, campaign_config)
    logger.info("Gemini client initialized")


def get_gemini_client() -> Optional[GeminiClient]:
    """Get the configured Gemini client

    Returns:
        Configured GeminiClient or None if not initialized
    """
    global _gemini_client

    # If already initialized, return it
    if _gemini_client is not None:
        return _gemini_client

    # Try to initialize new client
    import os
    api_key = os.getenv("GOOGLE_API_KEY")

    if not api_key:
        logger.warning("No GOOGLE_API_KEY environment variable found")
        return None

    # Load configurable LLM settings from environment
    max_attempts = int(os.getenv("LLM_MAX_ATTEMPTS", "2"))
    total_budget_ms = int(os.getenv("LLM_TOTAL_BUDGET_MS", "2000"))
    per_attempt_timeout_ms = int(os.getenv("LLM_PER_ATTEMPT_TIMEOUT_MS", "900"))

    # Load campaign configuration
    import yaml
    campaign_config_path = os.getenv("CAMPAIGN_CONFIG_PATH", "config/campaign.yaml")
    try:
        with open(campaign_config_path, 'r') as f:
            campaign_config = yaml.safe_load(f)
    except Exception as e:
        logger.warning(f"Failed to load campaign config: {e}")
        campaign_config = {}

    config = GeminiConfig(
        api_key=api_key,
        max_attempts=max_attempts,
        total_budget_ms=total_budget_ms,
        per_attempt_timeout_ms=per_attempt_timeout_ms
    )
    init_gemini(config, campaign_config)
    return _gemini_client
