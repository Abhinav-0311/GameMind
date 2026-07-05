import pytest
from fastapi.testclient import TestClient
from main import app
from app.database import SessionLocal
from app.models.npc import NPCProfile
from app.models.session import Conversation, Message
from app.models.telemetry import LLMTelemetryLog
from app.models.memory import NPCMemory
from app.services.telemetry_service import TelemetryService
from app.services.memory_service import MemoryService
from unittest.mock import patch, MagicMock
import uuid
import json
import decimal

client = TestClient(app)

@pytest.fixture(scope="module")
def db():
    db_session = SessionLocal()
    try:
        # Clear existing logs to start fresh in telemetry tests
        db_session.query(LLMTelemetryLog).delete()
        db_session.commit()
        yield db_session
    finally:
        db_session.close()

@pytest.fixture(scope="module")
def setup_npc(db):
    npc_slug = f"telemetry_wizard_{uuid.uuid4().hex[:6]}"
    npc = NPCProfile(
        slug=npc_slug,
        name="Tele-wizard",
        personality_summary="A wizard of logs.",
        dialogue_style="Very systematic.",
        voice_profile="mono",
        faction_alignment="log_sect"
    )
    db.add(npc)
    db.commit()
    db.refresh(npc)
    return npc

def test_telemetry_recording_on_chat(db, setup_npc):
    # Create conversation
    conv_res = client.post("/api/v1/conversations", json={"npc_slug": setup_npc.slug})
    assert conv_res.status_code == 201
    conv_id = conv_res.json()["id"]

    # Mock provider response and telemetry
    mock_provider = MagicMock()
    async def mock_resp(*args, **kwargs):
        telemetry = {
            "latency_ms": 125,
            "input_tokens": 15,
            "output_tokens": 30,
            "estimated_cost_usd": 0.000185,
            "safety_blocked": False,
            "safety_ratings": [{"category": "HARM_CATEGORY_HARASSMENT", "probability": "NEGLIGIBLE"}],
            "error": None
        }
        return "Systematic response", telemetry
    mock_provider.generate_response.side_effect = mock_resp

    with patch("app.api.v1.dialogue.get_llm_provider", return_value=mock_provider):
        with patch.object(MemoryService, "retrieve_memories", return_value="No relevant memories."):
            chat_res = client.post("/api/v1/dialogue/chat", json={
                "npc_slug": setup_npc.slug,
                "player_message": "Hello analyzer.",
                "conversation_id": conv_id
            })
            assert chat_res.status_code == 200

    # Query telemetry logs for this conversation
    logs = db.query(LLMTelemetryLog).filter(LLMTelemetryLog.conversation_id == conv_id).all()
    assert len(logs) == 1
    log = logs[0]
    assert log.action_type == "dialogue"
    assert log.npc_slug == setup_npc.slug
    assert log.latency_ms == 125
    assert log.input_tokens == 15
    assert log.output_tokens == 30
    assert abs(log.estimated_cost_usd - decimal.Decimal("0.000185")) < decimal.Decimal("1e-9")
    assert log.safety_blocked is False
    assert log.error is None


def test_telemetry_recording_on_summarization_and_error(db, setup_npc):
    # Create conversation
    conv_res = client.post("/api/v1/conversations", json={"npc_slug": setup_npc.slug})
    assert conv_res.status_code == 201
    conv_id = conv_res.json()["id"]

    # Mock LLM provider to raise an exception to verify error handling and classification
    mock_provider = MagicMock()
    async def mock_resp_err(*args, **kwargs):
        raise ValueError("API connection timeout: host unreachable")
    mock_provider.generate_response.side_effect = mock_resp_err

    # Explicitly run summarization background task and check error logging
    rag_mock = MagicMock()
    mem_service = MemoryService(rag_mock)
    
    # We populate messages to ensure we have something to summarize
    for i in range(12):
        msg = Message(
            conversation_id=conv_id,
            sender="player" if i % 2 == 0 else "npc",
            content=f"Message index {i}"
        )
        db.add(msg)
    db.commit()

    with patch("app.services.llm.factory.get_llm_provider", return_value=mock_provider):
        with pytest.raises(ValueError):
            # Run summarization
            import asyncio
            asyncio.run(mem_service.run_summarization_and_promotion(db, uuid.UUID(conv_id)))

    # Verify error log exists in telemetry
    logs = db.query(LLMTelemetryLog).filter(
        LLMTelemetryLog.conversation_id == conv_id, 
        LLMTelemetryLog.action_type == "summarization"
    ).all()
    assert len(logs) == 1
    log = logs[0]
    assert log.error == "ValueError"  # Short classification should extract exception class name
    assert log.latency_ms == 0
    assert log.estimated_cost_usd == 0.0


def test_analytics_endpoints(db, setup_npc):
    # Populate a few synthetic logs manually to test analytics aggregations
    log1 = LLMTelemetryLog(
        conversation_id=None,
        action_type="dialogue",
        npc_slug=setup_npc.slug,
        model_used="local-rule-engine",
        llm_provider="local_mock",
        latency_ms=150,
        input_tokens=100,
        output_tokens=50,
        estimated_cost_usd=decimal.Decimal("0.000600"),
        safety_blocked=False,
        error=None
    )
    log2 = LLMTelemetryLog(
        conversation_id=None,
        action_type="summarization",
        npc_slug=setup_npc.slug,
        model_used="local-rule-engine",
        llm_provider="local_mock",
        latency_ms=800,
        input_tokens=1000,
        output_tokens=200,
        estimated_cost_usd=decimal.Decimal("0.011200"),
        safety_blocked=False,
        error="RateLimitError"
    )
    db.add(log1)
    db.add(log2)
    db.commit()

    # 1. Test Overview Endpoint
    res = client.get("/api/v1/analytics/overview")
    assert res.status_code == 200
    overview = res.json()
    assert "total_cost_usd" in overview
    assert "total_requests" in overview
    assert "avg_latency_ms" in overview
    assert overview["total_requests"] >= 3 # log1, log2, plus test_telemetry_recording_on_chat
    assert overview["total_cost_usd"] > 0.0
    
    # 2. Test Costs Endpoint
    res = client.get("/api/v1/analytics/costs")
    assert res.status_code == 200
    costs = res.json()
    assert isinstance(costs, list)
    npc_costs = [c for c in costs if c["npc_slug"] == setup_npc.slug]
    assert len(npc_costs) == 1
    assert npc_costs[0]["total_cost_usd"] > 0.0

    # 3. Test Memory Endpoint
    # Let's insert some memories first
    mem1 = NPCMemory(npc_id=setup_npc.id, memory_text="test memory active", importance_score=7.0, archived=False, chroma_indexed=True)
    mem2 = NPCMemory(npc_id=setup_npc.id, memory_text="test memory archived", importance_score=5.0, archived=True, chroma_indexed=True)
    db.add(mem1)
    db.add(mem2)
    db.commit()

    res = client.get("/api/v1/analytics/memory")
    assert res.status_code == 200
    mem_stats = res.json()
    assert mem_stats["active_memories"] >= 1
    assert mem_stats["archived_memories"] >= 1
    assert "average_importance_score" in mem_stats
    assert "failed_chroma_indexing_count" in mem_stats

    # 4. Test Logs Endpoint
    # Test logs without filters
    res = client.get("/api/v1/analytics/logs?limit=5")
    assert res.status_code == 200
    logs_data = res.json()
    assert "total" in logs_data
    assert len(logs_data["logs"]) > 0

    # Test logs with filtering
    res = client.get(f"/api/v1/analytics/logs?npc_slug={setup_npc.slug}&action_type=summarization")
    assert res.status_code == 200
    filtered_logs = res.json()["logs"]
    for l in filtered_logs:
        assert l["npc_slug"] == setup_npc.slug
        assert l["action_type"] == "summarization"

    # Test filtering by error
    res = client.get(f"/api/v1/analytics/logs?npc_slug={setup_npc.slug}&has_error=true")
    assert res.status_code == 200
    error_logs = res.json()["logs"]
    assert len(error_logs) > 0
    for l in error_logs:
        assert l["error"] is not None
