import pytest

from scripts.agent_graph import AIDiscountAgent
from scripts.models import IncomingMessage, DetectionMethod
from scripts.store import get_store


@pytest.fixture(autouse=True)
def clear_store():
    get_store().clear_data()


def test_fuzzy_acceptance():
    agent = AIDiscountAgent("config/campaign.yaml", "config/templates.yaml")
    incoming = IncomingMessage(platform="instagram", user_id="u1", text="Marqes Brwnlee discount")
    decision = agent.process_message(incoming)
    assert decision.identified_creator == "mkbhd"
    assert decision.detection_method == DetectionMethod.FUZZY
    assert decision.discount_code_sent == "MARQUES20"


@pytest.mark.asyncio
async def test_llm_success_on_second_attempt(monkeypatch):
    # Mock LLM to return a success with attempts=2
    from scripts import agent_graph as ag

    class FakeLLM:
        async def detect_creator(self, message: str):
            from scripts.gemini_client import LLMResult
            return LLMResult(
                creator="mkbhd",
                detection_method=DetectionMethod.LLM,
                detection_confidence=0.8,
                model_version="mock-llm",
                attempts=2,
                total_latency_ms=300,
                error_reason=None,
            )

    monkeypatch.setattr(ag, "get_gemini_client", lambda: FakeLLM())

    agent = AIDiscountAgent("config/campaign.yaml", "config/templates.yaml")
    incoming = IncomingMessage(platform="instagram", user_id="u2", text="I need a discount")
    decision = await agent.process_message_async(incoming)
    assert decision.identified_creator == "mkbhd"
    assert decision.detection_method == DetectionMethod.LLM
    assert decision.discount_code_sent == "MARQUES20"


@pytest.mark.asyncio
async def test_llm_terminal_none(monkeypatch):
    from scripts import agent_graph as ag

    class FakeLLM:
        async def detect_creator(self, message: str):
            from scripts.gemini_client import LLMResult
            return LLMResult(
                creator=None,
                detection_method=DetectionMethod.LLM,
                detection_confidence=0.0,
                model_version="mock-llm",
                attempts=1,
                total_latency_ms=120,
                error_reason="LLM returned 'none' (terminal)",
            )

    monkeypatch.setattr(ag, "get_gemini_client", lambda: FakeLLM())

    agent = AIDiscountAgent("config/campaign.yaml", "config/templates.yaml")
    incoming = IncomingMessage(platform="instagram", user_id="u3", text="discount please")
    decision = await agent.process_message_async(incoming)
    assert decision.identified_creator is None
    assert decision.discount_code_sent is None
    assert decision.template_key == "ask_creator"


@pytest.mark.asyncio
async def test_llm_budget_exhausted(monkeypatch):
    from scripts import agent_graph as ag

    class FakeLLM:
        async def detect_creator(self, message: str):
            from scripts.gemini_client import LLMResult
            return LLMResult(
                creator=None,
                detection_method=DetectionMethod.LLM,
                detection_confidence=0.0,
                model_version="mock-llm",
                attempts=2,
                total_latency_ms=2000,
                error_reason="Retry limit exceeded",
            )

    monkeypatch.setattr(ag, "get_gemini_client", lambda: FakeLLM())

    agent = AIDiscountAgent("config/campaign.yaml", "config/templates.yaml")
    incoming = IncomingMessage(platform="instagram", user_id="u4", text="promo")
    decision = await agent.process_message_async(incoming)
    assert decision.identified_creator is None
    assert decision.discount_code_sent is None
    assert decision.template_key == "ask_creator"
