"""Detection and normalization logic for AI Discount Agent

This module handles text normalization, creator detection using exact/fuzzy matching,
intent classification, and business rules for discount code issuance.
"""

import re
import logging
from typing import Optional, Dict, List, Tuple, Any
from rapidfuzz import fuzz
import yaml

from scripts.models import Platform, IncomingMessage, DetectionMethod, Intent

# Configure logging
logger = logging.getLogger(__name__)

# Keywords indicating discount-related intent
DISCOUNT_KEYWORDS = {
    "discount", "code", "coupon", "promo", "creator", "sent me",
    "story", "mkbhd", "casey", "lily", "peter", "from @"
}

OUT_OF_SCOPE_KEYWORDS = {
    "hello", "hi", "how are you", "what's up", "good morning",
    "good evening", "thank you", "thanks", "bye", "goodbye"
}


class CreatorMatcher:
    """Handles creator detection with exact and fuzzy matching"""

    def __init__(self, campaign_config: Dict[str, Any]):
        """Initialize matcher with campaign configuration

        Args:
            campaign_config: Dictionary with creators data from YAML
        """
        self.creators = campaign_config['creators']
        self.thresholds = campaign_config['thresholds']
        self.flags = campaign_config['flags']

        # Create reverse alias lookup for exact matching
        self.alias_to_creator: Dict[str, str] = {}
        for creator, data in self.creators.items():
            for alias in data['aliases']:
                self.alias_to_creator[alias.lower()] = creator

    def is_in_scope(self, text: str) -> bool:
        """Check if message is related to discount requests

        Args:
            text: Normalized message text

        Returns:
            True if message appears to be about discounts
        """
        text_lower = text.lower()

        # Rule-based keywords check
        for keyword in DISCOUNT_KEYWORDS:
            if keyword in text_lower:
                return True

        # Check if contains any creator name
        creator_names = [name.lower() for name in self.creators.keys()]
        for creator in creator_names:
            if creator in text_lower:
                return True

        # Check if contains any known alias
        all_aliases = [alias.lower() for data in self.creators.values()
                      for alias in data['aliases']]

        for alias in all_aliases:
            alias_lower = alias.lower()
            if alias_lower in text_lower and len(alias_lower) > 2:
                return True

        # Out of scope if common greetings without discount keywords
        greeting_count = sum(1 for kw in OUT_OF_SCOPE_KEYWORDS
                           if kw.lower() in text_lower)
        if greeting_count >= 2 and not any(kw in text_lower for kw in DISCOUNT_KEYWORDS):
            return False

        # Default to in-scope for unknown messages to not miss potential requests
        return True

    def exact_match(self, text: str) -> Optional[Tuple[str, DetectionMethod]]:
        """Attempt exact alias matching

        Args:
            text: Normalized message text

        Returns:
            Tuple of (creator_handle, detection_method) or None
        """
        text_lower = text.lower()
        logger.info(f"Creator detection: checking '{text}' against {list(self.creators.keys())}")

        # Direct creator name match
        for creator in self.creators:
            if creator.lower() in text_lower:
                logger.info(f"Direct creator match: {creator}")
                return creator, DetectionMethod.EXACT

        # Alias match
        for alias, creator in self.alias_to_creator.items():
            if alias in text_lower:
                logger.info(f"Exact alias match: '{alias}' -> {creator}")
                return creator, DetectionMethod.EXACT

        return None

    def fuzzy_match(self, text: str) -> Optional[Tuple[str, float, DetectionMethod]]:
        """Attempt fuzzy matching against known aliases

        Args:
            text: Normalized message text

        Returns:
            Tuple of (creator_handle, confidence, detection_method) or None
        """
        if not self.flags.get('enable_fuzzy_matching', True):
            return None

        best_match = None
        best_score = 0.0
        best_creator = None

        # Fuzzy match against all known aliases
        all_aliases = []
        alias_to_creators = {}

        for creator, data in self.creators.items():
            for alias in data['aliases']:
                alias_lower = alias.lower()
                all_aliases.append(alias_lower)
                if alias_lower not in alias_to_creators:
                    alias_to_creators[alias_lower] = creator

        # Perform fuzzy matching
        for alias in all_aliases:
            similarity = fuzz.partial_ratio(text.lower(), alias)
            if similarity > best_score:
                best_score = similarity
                best_match = alias
                best_creator = alias_to_creators[alias]

        # Apply thresholds
        fuzzy_accept_threshold = self.thresholds['fuzzy_accept']
        fuzzy_reject_threshold = self.thresholds['fuzzy_reject']

        if best_score >= fuzzy_accept_threshold:
            logger.info(f"Fuzzy match accepted: '{text}' ~ '{best_match}' "
                       f"-> {best_creator} (confidence: {best_score:.2f})")
            return best_creator, best_score, DetectionMethod.FUZZY
        elif best_score >= fuzzy_reject_threshold:
            logger.info(f"Fuzzy match rejected: '{text}' ~ '{best_match}' "
                       f"(confidence: {best_score:.2f}) - below acceptance threshold")
            return None
        else:
            # Very low confidence, no match
            return None


def normalize_text(text: str) -> str:
    """Normalize text for consistent processing

    Args:
        text: Raw text from user

    Returns:
        Normalized text (lowercase, stripped, extra spaces removed)
    """
    if not text:
        return ""

    # Convert to lowercase and strip whitespace
    normalized = text.lower().strip()

    # Remove extra whitespace
    normalized = re.sub(r'\s+', ' ', normalized)

    # Remove common punctuation that might interfere with matching
    normalized = re.sub(r'[!?.,;:]+$', '', normalized)  # Trailing punctuation

    return normalized


def extract_creator_context(text: str) -> str:
    """Extract context around potential creator mentions

    Args:
        text: Normalized message text

    Returns:
        Text with potential creator context emphasis
    """
    # Simple heuristic: take text around creator keywords
    words = text.split()
    creator_keywords = ["creator", "sent me", "from", "@"]

    for keyword in creator_keywords:
        if keyword in text:
            # Extract words around the keyword
            kw_index = words.index(keyword) if keyword in words else -1
            if kw_index >= 0:
                start = max(0, kw_index - 2)
                end = min(len(words), kw_index + 3)
                return ' '.join(words[start:end])

    return text
