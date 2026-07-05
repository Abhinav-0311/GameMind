import logging
from unittest.mock import patch
from fastapi.testclient import TestClient
from main import app
from app.services.llm.factory import get_llm_provider
from app.services.llm.mock import MockLLMProvider
from test_dialogue import db_session, setup_data

client = TestClient(app)

def test_mock_provider_lore_awareness():
    """Verify that MockLLMProvider extracts character traits and lore context correctly."""
    system_prompt = (
        "Character Name: Eldrin\n"
        "Faction Alignment: Cinder Vanguard\n"
        "LORE CONTEXT:\n"
        "The Ember Siege destroyed the eastern watchtower.\n"
        "Eldrin witnessed the siege from Frostpeak.\n"
    )
    user_prompt = "What did you see at the siege?"
    
    provider = MockLLMProvider()
    
    import asyncio
    response, telemetry = asyncio.run(
        provider.generate_response(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_output_tokens=400,
            model_name="mock-model"
        )
    )
    
    assert "[Eldrin of the Cinder Vanguard]" in response
    assert "Based on the supplied lore context, I know:" in response
    assert "- The Ember Siege destroyed the eastern watchtower." in response
    assert "- Eldrin witnessed the siege from Frostpeak." in response
    assert "What did you see at the siege?" in response
    assert telemetry["latency_ms"] == 100
    assert telemetry["estimated_cost_usd"] == 0.0

def test_provider_factory_mock():
    """Verify that the factory returns MockLLMProvider when configured to 'mock'."""
    with patch("app.services.llm.factory.settings") as mock_settings:
        mock_settings.LLM_PROVIDER = "mock"
        provider = get_llm_provider()
        assert isinstance(provider, MockLLMProvider)

def test_provider_factory_unsupported_fallback(caplog):
    """Verify unsupported providers fall back to the local mock provider."""
    with patch("app.services.llm.factory.settings") as mock_settings:
        mock_settings.LLM_PROVIDER = "nvidia"
        
        with caplog.at_level(logging.WARNING):
            provider = get_llm_provider()
            
        assert isinstance(provider, MockLLMProvider)
        assert "Unsupported LLM_PROVIDER" in caplog.text

def test_api_chat_endpoint_mock_mode(db_session, setup_data):
    """Verify that the /chat endpoint generates responses and returns telemetry correctly."""
    # We patch settings to ensure LLM_PROVIDER = mock
    with patch("app.api.v1.dialogue.settings") as mock_settings:
        mock_settings.LLM_PROVIDER = "mock"
        mock_settings.LOCAL_MODEL_NAME = "mock-model"
        
        payload = {
            "npc_slug": setup_data["npc_slug"],
            "player_message": "Tell me about the Wind Tome.",
            "selected_chunk_ids": [setup_data["chunk1_id"]]
        }
        
        response = client.post("/api/v1/dialogue/chat", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["npc_slug"] == payload["npc_slug"]
        assert "response_text" in data
        assert "[Zephyr of the zephyr_sect]" in data["response_text"]
        assert "Based on the supplied lore context, I know:" in data["response_text"]
        assert "The Wind Tome describes Ember Siege" in data["response_text"]
        assert data["telemetry"]["latency_ms"] > 0
        assert data["telemetry"]["estimated_cost_usd"] == 0.0
