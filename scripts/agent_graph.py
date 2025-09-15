"""LangGraph agent pipeline for AI Discount Agent

This module implements the AI agent's decision flow using LangGraph.
The agent processes messages through a series of nodes: intent detection,
creator identification, enrichment, and final decision making.
"""

import logging
import yaml
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from uuid import uuid4
from typing import List

from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableLambda

from scripts.models import (
    IncomingMessage,
    AgentDecision,
    InteractionRow,
    DetectionMethod,
    ConversationStatus
)
from scripts.detection import CreatorMatcher, normalize_text
from scripts.gemini_client import get_gemini_client, LLMResult

# Configure logging
logger = logging.getLogger(__name__)


# Simplified approach: Use regular dict type for LangGraph state
# This avoids complex initialization issues with the AgentState class
AgentState = Dict[str, Any]


class AIDiscountAgent:
    """LangGraph-based AI agent for discount code distribution"""

    def __init__(self, campaign_config_path: str, templates_path: str):
        """Initialize the agent with configuration

        Args:
            campaign_config_path: Path to YAML campaign config
            templates_path: Path to YAML templates config
        """
        with open(campaign_config_path, 'r') as f:
            self.campaign_config = yaml.safe_load(f)

        with open(templates_path, 'r') as f:
            self.templates = yaml.safe_load(f)['replies']

        self.matcher = CreatorMatcher(self.campaign_config)

        # Build the LangGraph (sync and async variants)
        self.graph = self._build_graph(async_mode=False)
        self.graph_async = self._build_graph(async_mode=True)

    def _build_graph(self, async_mode: bool = False) -> StateGraph:
        """Build and compile the LangGraph

        Returns:
            Compiled StateGraph ready for execution
        """
        # Define the graph structure
        workflow = StateGraph(AgentState)

        # Add nodes (functions that process the state)
        workflow.add_node("normalize", RunnableLambda(self._normalize_node))
        workflow.add_node("detect_intent", RunnableLambda(self._detect_intent_node))
        # Use async detect_creator when in async mode
        if async_mode:
            workflow.add_node("detect_creator", RunnableLambda(self._detect_creator_node_async))
        else:
            workflow.add_node("detect_creator", RunnableLambda(self._detect_creator_node))
        workflow.add_node("enrich_lead", RunnableLambda(self._enrich_lead_node))
        workflow.add_node("decide_response", RunnableLambda(self._decide_response_node))

        # Define flow
        workflow.set_entry_point("normalize")
        workflow.add_edge("normalize", "detect_intent")

        # Add conditional edges
        workflow.add_conditional_edges(
            "detect_intent",
            lambda state: state["is_in_scope"],
            {
                True: "detect_creator",
                False: "decide_response"
            }
        )

        # Creator detection always goes to enrichment (or skip if no creator)
        workflow.add_edge("detect_creator", "enrich_lead")
        workflow.add_edge("enrich_lead", "decide_response")

        # End at decision
        workflow.add_edge("decide_response", END)

        # Compile the graph
        return workflow.compile()

    def _normalize_node(self, state: AgentState) -> AgentState:
        """Normalize the incoming message

        Args:
            state: Current agent state

        Returns:
            Updated state with normalized message
        """
        raw_message = state["raw_message"]
        normalized = normalize_text(raw_message)

        logger.info(f"Normalized message: '{raw_message}' -> '{normalized}'")

        state["normalized_message"] = normalized
        # Trace
        state.setdefault("trace", []).append(f"normalize: '{raw_message}' -> '{normalized}'")
        return state

    def _detect_intent_node(self, state: AgentState) -> AgentState:
        """Detect if message is related to discount requests

        Args:
            state: Current agent state

        Returns:
            Updated state with intent classification
        """
        message = state["normalized_message"]
        is_in_scope = self.matcher.is_in_scope(message)

        logger.info(f"Intent detection: '{message}' -> in_scope={is_in_scope}")
        logger.info(f"Graph flow: normalized message processed, deciding next step")

        state["is_in_scope"] = is_in_scope
        # Trace
        state.setdefault("trace", []).append(f"intent: {'in_scope' if is_in_scope else 'out_of_scope'}")
        return state

    def _detect_creator_node(self, state: AgentState) -> AgentState:
        """Detect which creator sent the discount code

        Args:
            state: Current agent state

        Returns:
            Updated state with creator detection results
        """
        message = state["normalized_message"]

        # Step 1: Exact match
        result = self.matcher.exact_match(message)
        if result:
            creator, detection_method = result
            logger.info(f"Exact match success: {creator}")
            state["creator"] = creator
            state["detection_method"] = detection_method
            state["detection_confidence"] = 1.0  # Exact match = 100% confidence
            state.setdefault("trace", []).append(f"exact: {creator}")
            return state

        # Step 2: Fuzzy match
        fuzzy_result = self.matcher.fuzzy_match(message)
        if fuzzy_result:
            creator, confidence, detection_method = fuzzy_result
            # Clamp confidence to 0-1 range to prevent Pydantic validation errors
            clamped_confidence = max(0.0, min(1.0, confidence))
            logger.info(f"Fuzzy match success: {creator} (confidence: {clamped_confidence:.3f})")
            state["creator"] = creator
            state["detection_method"] = detection_method
            state["detection_confidence"] = clamped_confidence
            state.setdefault("trace", []).append(f"fuzzy: {creator} ({clamped_confidence:.2f})")
            return state
        else:
            state.setdefault("trace", []).append("fuzzy: none")

        # Step 3: LLM fallback
        if self.campaign_config['flags'].get('enable_llm_fallback', True):
            gemini_client = get_gemini_client()
            if gemini_client:
                logger.info("Attempting LLM fallback for creator detection")

                # Note: This is a simplified version - in production this would be async
                # For the demo, we'll simulate synchronous call
                import asyncio

                async def async_llm_call():
                    llm_result = await gemini_client.detect_creator(message)
                    return llm_result

                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        logger.warning("LLM fallback skipped: event loop already running")
                    else:
                        llm_result = loop.run_until_complete(async_llm_call())

                        if llm_result.creator:
                            # Clamp LLM confidence to prevent validation errors
                            clamped_llm_confidence = max(0.0, min(1.0, llm_result.detection_confidence))
                            logger.info(f"✅ LLM SUCCESS: {llm_result.creator} "
                                       f"(method=llm, attempts={llm_result.attempts}, "
                                       f"latency={llm_result.total_latency_ms}ms, "
                                       f"model={llm_result.model_version}, "
                                       f"confidence={clamped_llm_confidence:.3f})")
                            state["creator"] = llm_result.creator
                            state["detection_method"] = llm_result.detection_method
                            state["detection_confidence"] = clamped_llm_confidence
                            state.setdefault("trace", []).append(
                                f"llm: {llm_result.creator} ({clamped_llm_confidence:.2f}), attempts={llm_result.attempts}"
                            )
                            return state
                        else:
                            logger.info(f"LLM FAILURE: No creator detected after "
                                       f"{llm_result.attempts} attempts "
                                       f"({llm_result.total_latency_ms}ms, "
                                       f"model={llm_result.model_version}) "
                                       f"Reason: {llm_result.error_reason}")
                            state.setdefault("trace", []).append(
                                f"llm: none (reason={llm_result.error_reason})"
                            )
                except Exception as e:
                    logger.warning(f"LLM fallback failed: {e}")
                    state.setdefault("trace", []).append(f"llm: error ({e})")
            else:
                state.setdefault("trace", []).append("llm: disabled/no_key")

        logger.info("No creator detected, will ask user")
        return state

    async def _detect_creator_node_async(self, state: AgentState) -> AgentState:
        """Async version to support LLM fallback in async contexts"""
        message = state["normalized_message"]

        # Step 1: Exact match
        result = self.matcher.exact_match(message)
        if result:
            creator, detection_method = result
            state["creator"] = creator
            state["detection_method"] = detection_method
            state["detection_confidence"] = 1.0
            state.setdefault("trace", []).append(f"exact: {creator}")
            return state

        # Step 2: Fuzzy match
        fuzzy_result = self.matcher.fuzzy_match(message)
        if fuzzy_result:
            creator, confidence, detection_method = fuzzy_result
            clamped_confidence = max(0.0, min(1.0, confidence))
            state["creator"] = creator
            state["detection_method"] = detection_method
            state["detection_confidence"] = clamped_confidence
            state.setdefault("trace", []).append(f"fuzzy: {creator} ({clamped_confidence:.2f})")
            return state
        else:
            state.setdefault("trace", []).append("fuzzy: none")

        # Step 3: LLM fallback
        if self.campaign_config['flags'].get('enable_llm_fallback', True):
            gemini_client = get_gemini_client()
            if gemini_client:
                try:
                    llm_result = await gemini_client.detect_creator(message)
                    if llm_result.creator:
                        clamped_llm_confidence = max(0.0, min(1.0, llm_result.detection_confidence))
                        state["creator"] = llm_result.creator
                        state["detection_method"] = llm_result.detection_method
                        state["detection_confidence"] = clamped_llm_confidence
                        state.setdefault("trace", []).append(
                            f"llm: {llm_result.creator} ({clamped_llm_confidence:.2f}), attempts={llm_result.attempts}"
                        )
                        return state
                    else:
                        state.setdefault("trace", []).append(
                            f"llm: none (reason={llm_result.error_reason})"
                        )
                except Exception as e:
                    state.setdefault("trace", []).append(f"llm: error ({e})")
            else:
                state.setdefault("trace", []).append("llm: disabled/no_key")

        return state

    def _enrich_lead_node(self, state: AgentState) -> AgentState:
        """Generate enrichment data for the lead/user (Bonus B)

        Args:
            state: Current agent state

        Returns:
            Updated state with enrichment data
        """
        creator = state["creator"]
        if not creator:
            return state

        # Generate deterministic enrichment based on user_id (lead enrichment)
        user_id = state.get("user_id") or "unknown_user"
        uid_hash = hash(user_id) % 100000

        follower_count = 10000 + (uid_hash % 900000)  # 10k to 910k followers
        is_potential_influencer = follower_count > 50000 or (uid_hash % 10) > 7

        logger.info(
            f"Enrichment for user_id={user_id}: {follower_count} followers, "
            f"potential_influencer={is_potential_influencer}"
        )

        state["follower_count"] = follower_count
        state["is_potential_influencer"] = is_potential_influencer
        state.setdefault("trace", []).append(
            f"enrich: user_id={user_id} followers={follower_count} potential={is_potential_influencer}"
        )

        return state

    def _decide_response_node(self, state: AgentState) -> AgentState:
        """Make final decision about response and conversation status

        Args:
            state: Current agent state

        Returns:
            Updated state with final decision
        """
        is_in_scope = state["is_in_scope"]
        creator = state["creator"]
        detection_method = state["detection_method"]

        if not is_in_scope:
            # Out of scope message
            reply = self.templates["out_of_scope"]
            template_key = "out_of_scope"
            status = ConversationStatus.OUT_OF_SCOPE
            discount_code = None
            should_send_reply = True
            state.setdefault("trace", []).append("decide: out_of_scope")

        elif not creator:
            # In scope but no creator identified
            reply = self.templates["ask_creator"]
            template_key = "ask_creator"
            status = ConversationStatus.PENDING_CREATOR_INFO
            discount_code = None
            should_send_reply = True
            state.setdefault("trace", []).append("decide: ask_creator")

        else:
            # Creator detected - check if we can issue code
            platform = state["platform"]
            user_id = state["user_id"]

            # Import here to avoid circular imports
            from scripts.store import get_store

            store = get_store()
            can_issue = store.can_issue_code(platform, user_id)

            if can_issue:
                # Issue the discount code
                code = self.campaign_config['creators'][creator]['code']
                reply = self.templates["issue_code"].format(
                    creator_handle=creator,
                    discount_code=code
                )
                template_key = "issue_code"
                status = ConversationStatus.COMPLETED
                discount_code = code
                should_send_reply = True

                logger.info(f"Issuing code {code} for creator {creator}")
                state.setdefault("trace", []).append(f"decide: issue_code {code} for {creator}")

            else:
                # Already issued code before - can't issue again
                code = self.campaign_config['creators'][creator]['code']
                reply = self.templates["already_sent_no_resend"]
                template_key = "already_sent_no_resend"
                status = ConversationStatus.PENDING_CREATOR_INFO
                discount_code = None
                should_send_reply = True

                logger.info(f"Code already issued for {creator}, denying reissuance")
                state.setdefault("trace", []).append("decide: already_sent_no_resend")

        # Store enrichment data for Bonus B
        state["follower_count"] = state.get("follower_count")
        state["is_potential_influencer"] = state.get("is_potential_influencer")

        # Update state with final decisions
        state["reply"] = reply
        state["template_key"] = template_key
        state["conversation_status"] = status
        state["discount_code"] = discount_code
        state["should_send_reply"] = should_send_reply

        return state

    def process_message(self, incoming: IncomingMessage) -> AgentDecision:
        """Process an incoming message through the agent pipeline

        Args:
            incoming: Incoming message to process

        Returns:
            Agent decision with reply and interaction data
        """
        logger.info(f"Processing message from {incoming.user_id} on {incoming.platform.value}: {incoming.text}")

        # Initialize state with ALL required keys to prevent KeyError
        initial_state = {
            # Core message data
            "platform": incoming.platform.value,
            "user_id": incoming.user_id,
            "raw_message": incoming.text,
            "message_id": incoming.message_id,

            # Processing state - initialize all to prevent KeyError
            "normalized_message": "",
            "is_in_scope": None,
            "creator": None,
            "detection_method": None,
            "detection_confidence": 0.0,
            "discount_code": None,
            "can_issue_code": False,

            # Output state
            "reply": "",
            "template_key": "",
            "conversation_status": ConversationStatus.PENDING_CREATOR_INFO,
            "should_send_reply": True,

            # Bonus B enrichment
            "follower_count": None,
            "is_potential_influencer": None
        }
        initial_state["trace"] = []

        # Execute the graph
        final_state = self.graph.invoke(initial_state)

        # Extract results
        creator = final_state["creator"]
        detection_method = final_state["detection_method"]
        confidence = final_state["detection_confidence"]
        reply = final_state["reply"]
        template_key = final_state["template_key"]
        status = final_state["conversation_status"]
        discount_code = final_state["discount_code"]
        is_potential = final_state.get("is_potential_influencer", None)
        follower_count = final_state.get("follower_count", None)

        # Create AgentDecision
        decision = AgentDecision(
            reply_text=reply,
            template_key=template_key,
            identified_creator=creator,
            detection_method=detection_method,
            detection_confidence=confidence,
            discount_code_sent=discount_code,
            conversation_status=status,
            is_potential_influencer=is_potential,
            follower_count=follower_count,
            trace=final_state.get("trace", [])
        )

        logger.info(f"Agent decision: creator={creator}, status={status.value}, "
                   f"code={discount_code}, method={detection_method}")

        return decision

    async def process_message_async(self, incoming: IncomingMessage) -> AgentDecision:
        """Async processing to support LLM fallback within FastAPI event loop"""
        logger.info(f"Processing message (async) from {incoming.user_id} on {incoming.platform.value}: {incoming.text}")

        initial_state = {
            "platform": incoming.platform.value,
            "user_id": incoming.user_id,
            "raw_message": incoming.text,
            "message_id": incoming.message_id,

            "normalized_message": "",
            "is_in_scope": None,
            "creator": None,
            "detection_method": None,
            "detection_confidence": 0.0,
            "discount_code": None,
            "can_issue_code": False,

            "reply": "",
            "template_key": "",
            "conversation_status": ConversationStatus.PENDING_CREATOR_INFO,
            "should_send_reply": True,

            "follower_count": None,
            "is_potential_influencer": None,
            "trace": []
        }

        final_state = await self.graph_async.ainvoke(initial_state)

        creator = final_state["creator"]
        detection_method = final_state["detection_method"]
        confidence = final_state["detection_confidence"]
        reply = final_state["reply"]
        template_key = final_state["template_key"]
        status = final_state["conversation_status"]
        discount_code = final_state["discount_code"]
        is_potential = final_state.get("is_potential_influencer", None)
        follower_count = final_state.get("follower_count", None)

        decision = AgentDecision(
            reply_text=reply,
            template_key=template_key,
            identified_creator=creator,
            detection_method=detection_method,
            detection_confidence=confidence,
            discount_code_sent=discount_code,
            conversation_status=status,
            is_potential_influencer=is_potential,
            follower_count=follower_count,
            trace=final_state.get("trace", [])
        )

        logger.info(f"Agent decision (async): creator={creator}, status={status.value}, "
                    f"code={discount_code}, method={detection_method}")

        return decision

    def create_interaction_row(self, incoming: IncomingMessage, decision: AgentDecision) -> InteractionRow:
        """Create database interaction row from message and decision

        Args:
            incoming: Original incoming message
            decision: Agent decision result

        Returns:
            InteractionRow for database storage
        """
        # Use the model's validator to format the timestamp correctly
        now_utc = datetime.now(timezone.utc)

        # Bonus B: reuse enrichment from decision if provided
        follower_count: Optional[int] = decision.follower_count
        is_potential: Optional[bool] = decision.is_potential_influencer

        return InteractionRow(
            user_id=incoming.user_id,
            platform=incoming.platform.value,
            timestamp=now_utc,
            raw_incoming_message=incoming.text,
            identified_creator=decision.identified_creator,
            discount_code_sent=decision.discount_code_sent,
            conversation_status=decision.conversation_status.value,
            follower_count=follower_count,
            is_potential_influencer=is_potential
        )


def run_agent_on_message(message: str, platform: str = "instagram", user_id: str = "demo_user") -> Dict[str, Any]:
    """Run the agent on a demo message

    This is the function required by Step 2 of the assignment.
    It takes a plain string message and returns reply + database row JSON.

    Args:
        message: Plain text message to process
        platform: Social media platform (default: instagram)
        user_id: User identifier (default: demo_user)

    Returns:
        Dictionary with reply text and database row as JSON
    """
    logger.info(f"Message received: normalized | user={user_id}, platform={platform}, raw=\"{message}\", norm=\"{message.lower().strip()}\"")

    # If using default demo user, generate a unique ID to avoid cross-test collisions
    if user_id == "demo_user":
        user_id = f"demo_user_{uuid4().hex[:8]}"

    # Load configurations
    agent = AIDiscountAgent("config/campaign.yaml", "config/templates.yaml")

    # Create incoming message
    incoming = IncomingMessage(
        platform=platform if isinstance(platform, str) else platform,
        user_id=user_id,
        text=message
    )

    # Process through agent
    decision = agent.process_message(incoming)

    # Create interaction row
    row = agent.create_interaction_row(incoming, decision)

    # Persist interaction for idempotency/analytics
    try:
        from scripts.store import get_store
        get_store().store_interaction(row)
    except Exception as e:
        logger.warning(f"Failed to persist interaction: {e}")

    # Return result as required by assignment
    return {
        "reply": decision.reply_text,
        "database_row": row.model_dump()
    }
