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
    total_budget_ms: int = 1000
    per_attempt_timeout_ms: int = 400
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

    def __init__(self, config: GeminiConfig):
        """Initialize Gemini client with configuration

        Args:
            config: Gemini configuration parameters
        """
        self.config = config
        self.allowed_creators = {
            "casey_neistat", "mkbhd", "lily_singh", "peter_mckinnon"
        }

        if config.api_key:
            genai.configure(api_key=config.api_key)

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
                # Explicit "none" is valid
                logger.info("LLM explicitly returned 'none' (no creator detected)")
                return None

            # Validate against allow-list
            if isinstance(creator, str) and creator in self.allowed_creators:
                logger.info(f"LLM validated creator: {creator}")
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

            # Craft prompt
            prompt = f"""
Analyze this user message to identify which creator sent them a discount code.

Message: "{message}"

Respond with JSON in this exact format:
{{
  "creator": "casey_neistat|mkbhd|lily_singh|peter_mckinnon|none"
}}

Rules:
- Only respond with the name of a known creator OR "none"
- If no creator is mentioned, use "none"
- Match the exact creator name from the list
- Do not make up responses outside the allowed values
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
                    return LLMResult(
                        creator=creator,
                        detection_method=DetectionMethod.LLM,
                        detection_confidence=0.8 if creator else 0.0,  # Conservative confidence
                        model_version=self.config.model_version,
                        attempts=attempts,
                        total_latency_ms=int(total_time),
                        error_reason=None
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


def init_gemini(config: GeminiConfig) -> None:
    """Initialize global Gemini client

    Args:
        config: Gemini configuration
    """
    global _gemini_client
    _gemini_client = GeminiClient(config)
    logger.info("Gemini client initialized")


def get_gemini_client() -> Optional[GeminiClient]:
    """Get the configured Gemini client

    Returns:
        Configured GeminiClient or None if not initialized
    """
    return _gemini_client
