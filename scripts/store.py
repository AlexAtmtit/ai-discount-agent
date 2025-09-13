"""In-memory storage implementation for AI Discount Agent

This module provides an in-memory storage layer that implements the same interface
as a production SQL database. It stores interaction rows in memory for demo/testing
purposes and is interchangeable with SQL-based storage.
"""

import asyncio
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone

from scripts.models import InteractionRow, AnalyticsSummary, CreatorStats


class MemoryStore:
    """In-memory storage for interaction data

    This class provides the same interface as SQL-based storage but uses
    a Python list to store data in memory. Data persists only during runtime
    and resets on restart - perfect for demos and testing.
    """

    def __init__(self):
        """Initialize empty storage"""
        self.interactions: List[InteractionRow] = []

    def store_interaction(self, row: InteractionRow) -> None:
        """Store a new interaction row

        Args:
            row: The interaction data to store
        """
        self.interactions.append(row)

    def get_all_interactions(self) -> List[InteractionRow]:
        """Retrieve all stored interactions

        Returns:
            List of all interaction rows
        """
        return self.interactions.copy()  # Return copy to prevent external mutations

    def get_analytics(self) -> AnalyticsSummary:
        """Generate analytics summary from stored data

        Returns:
            AnalyticsSummary with creator and platform breakdowns
        """
        # Initialize counters
        total_requests = len(self.interactions)
        total_completed = sum(1 for row in self.interactions
                            if row.conversation_status == "completed")
        creator_stats: Dict[str, CreatorStats] = {}

        # Process each interaction
        for row in self.interactions:
            creator = row.identified_creator or "unknown"

            if creator not in creator_stats:
                creator_stats[creator] = CreatorStats(
                    creator_handle=creator,
                    total_requests=0,
                    total_completed=0,
                    platform_breakdown={}
                )

            creator_stats[creator].total_requests += 1
            if row.conversation_status == "completed":
                creator_stats[creator].total_completed += 1

            # Platform breakdown
            platform = row.platform
            if platform not in creator_stats[creator].platform_breakdown:
                creator_stats[creator].platform_breakdown[platform] = {
                    "requests": 0,
                    "completed": 0
                }

            platform_stats = creator_stats[creator].platform_breakdown[platform]
            platform_stats["requests"] += 1
            if row.conversation_status == "completed":
                platform_stats["completed"] += 1

        return AnalyticsSummary(
            total_creators=len(creator_stats),
            total_requests=total_requests,
            total_completed=total_completed,
            creators=creator_stats
        )

    def can_issue_code(self, platform: str, user_id: str) -> bool:
        """Check if user can receive a new discount code

        This implements the business rule: one code per user per campaign per platform

        Args:
            platform: Social media platform
            user_id: User's platform ID

        Returns:
            True if user can receive a code, False if they've already received one
        """
        completed_interactions = [
            row for row in self.interactions
            if (row.platform == platform and
                row.user_id == user_id and
                row.conversation_status == "completed" and
                row.discount_code_sent is not None)
        ]
        return len(completed_interactions) == 0

    def clear_data(self) -> None:
        """Clear all stored data (useful for testing)"""
        self.interactions.clear()

    async def astore_interaction(self, row: InteractionRow) -> None:
        """Async version of store_interaction

        Args:
            row: The interaction data to store
        """
        # Simulate some async operation for production realism
        await asyncio.sleep(0.01)
        self.store_interaction(row)

    async def aget_analytics(self) -> AnalyticsSummary:
        """Async version of get_analytics

        Returns:
            AnalyticsSummary with creator and platform breakdowns
        """
        # Simulate some async operation
        await asyncio.sleep(0.01)
        return self.get_analytics()


# Global instance for the demo
store = MemoryStore()


def get_store() -> MemoryStore:
    """Factory function to get the storage instance

    Returns:
        The configured storage instance
    """
    return store
