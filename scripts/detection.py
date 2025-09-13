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
    "good evening", "thank you", "thanks", "bye", "goodbye",
    "how's it going", "sup", "yo", "hey", "greetings"
}

# Creator tokens for pre-gate filtering
CREATOR_TOKENS = {
    "casey", "casey_neistat", "neistat", "mkbhd", "marques", "brownlee",
    "lily", "lily_singh", "singh", "lilysuperwoman", "peter", "mckinnon",
    "petermckinnon24", "mckinnon24"
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

        # Pre-gate 1: Check for explicit out-of-scope keywords
        out_of_scope_count = sum(1 for kw in OUT_OF_SCOPE_KEYWORDS
                                if kw.lower() in text_lower)
        # If multiple out-of-scope keywords and no discount keywords, reject
        discount_kw_count = sum(1 for kw in DISCOUNT_KEYWORDS
                               if kw in text_lower)
        if out_of_scope_count >= 1 and discount_kw_count == 0:
            logger.info(f"Out-of-scope detected: '{text}' contains greeting but no discount keywords")
            return False

        # Pre-gate 2: If contains discount keywords or creator tokens, accept
        for keyword in DISCOUNT_KEYWORDS:
            if keyword in text_lower:
                return True

        for token in CREATOR_TOKENS:
            if token in text_lower:
                return True

        # Conservative default: mark out-of-scope for unknown messages
        logger.info(f"Unknown intent: '{text}' - defaulting to out-of-scope")
        return False

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

        # Pre-gate: Only consider fuzzy if message contains creator-relevant tokens
        text_lower = text.lower()
        has_creator_token = any(token in text_lower for token in CREATOR_TOKENS)
        if not has_creator_token:
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
            similarity = fuzz.partial_ratio(text_lower, alias)
            normalized_confidence = similarity / 100.0  # Convert to 0-1 scale
            if normalized_confidence > best_score:
                best_score = normalized_confidence
                best_match = alias
                best_creator = alias_to_creators[alias]

        # Apply thresholds (already normalized)
        fuzzy_accept_threshold = self.thresholds['fuzzy_accept']  # 0.8
        # Add margin check - best should be significantly better than second best

        if best_creator:
            logger.info(f"Fuzzy match: '{text}' -> {best_creator} "
                       f"(confidence: {best_score:.3f})")
        else:
            logger.info(f"No fuzzy match for: '{text}'")
            return None

        # Check threshold with margin requirement
        if best_score >= fuzzy_accept_threshold:
            logger.info(f"Fuzzy match accepted: '{text}' ~ '{best_match}' "
                       f"-> {best_creator} (confidence: {best_score:.3f})")
            return best_creator, best_score, DetectionMethod.FUZZY
        else:
            logger.info(f"Fuzzy match rejected: '{text}' has low confidence ({best_score:.3f})")
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
