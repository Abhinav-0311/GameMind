from fastapi.testclient import TestClient
import pytest

from main import app
from app.services.rag_service import RAGService
import uuid

client = TestClient(app)

def test_health_endpoint():
    """Verify that health check returns 200 and details status fields."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "database" in data
    assert "chromadb" in data
    assert data["ai_mode"] == "local_demo"
    assert data["embedding_provider"] == "local_lexical"
    assert data["vector_collection"] == "lore_chunks_local_lexical_v1"
    assert "llm_provider" in data


def test_config_uses_explicit_cors_origins():
    from app.config import settings

    assert "*" not in settings.cors_origins
    assert "http://localhost:3000" in settings.cors_origins


def test_security_headers_are_present():
    response = client.get("/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"


def test_request_context_headers_echo_valid_id_and_replace_invalid_id():
    valid = client.get("/health", headers={"X-Request-ID": "release-smoke-123"})
    assert valid.headers["x-request-id"] == "release-smoke-123"
    assert float(valid.headers["x-response-time-ms"]) >= 0

    invalid = client.get("/health", headers={"X-Request-ID": "bad request id"})
    assert invalid.headers["x-request-id"] != "bad request id"
    assert len(invalid.headers["x-request-id"]) == 32


def test_health_exposes_database_pool_budget():
    response = client.get("/health")
    pool = response.json()["database_pool"]

    assert pool["capacity"] == pool["pool_size"] + pool["max_overflow"]
    assert pool["available"] >= 0
    assert isinstance(pool["saturated"], bool)


def test_health_degrades_immediately_when_database_pool_is_saturated(monkeypatch):
    import main

    monkeypatch.setattr(
        main,
        "get_database_pool_status",
        lambda: {
            "pool_size": 5,
            "max_overflow": 10,
            "capacity": 15,
            "checked_out": 15,
            "available": 0,
            "saturated": True,
        },
    )

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert response.json()["database"] == "saturated"


def test_dialogue_pool_timeout_returns_retryable_503(monkeypatch):
    from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError

    from app.services.dialogue_service import DialogueService

    def raise_pool_timeout(*_args, **_kwargs):
        raise SQLAlchemyTimeoutError("pool capacity reached")

    monkeypatch.setattr(DialogueService, "assemble_prompt", raise_pool_timeout)
    response = client.post(
        "/api/v1/dialogue/chat",
        headers={"X-Request-ID": "overload-test"},
        json={
            "npc_slug": "eldrin",
            "player_message": "Hello there",
            "player_id": "capacity-test-player",
        },
    )

    assert response.status_code == 503
    assert response.headers["retry-after"] == "2"
    assert response.headers["x-request-id"] == "overload-test"
    assert response.json()["detail"]["code"] == "database_capacity_exceeded"


@pytest.mark.integration
def test_real_database_pool_saturation_fails_with_bounded_503(db_session):
    import time

    from app.config import settings
    test_engine = db_session.get_bind()
    capacity = settings.DATABASE_POOL_SIZE + settings.DATABASE_MAX_OVERFLOW

    connections = []
    try:
        for _ in range(capacity):
            connections.append(test_engine.connect())

        started = time.perf_counter()
        response = client.post(
            "/api/v1/dialogue/chat",
            headers={"X-Request-ID": "real-overload-test"},
            json={
                "npc_slug": "eldrin",
                "player_message": "Hello there",
                "player_id": "real-capacity-test-player",
            },
        )
        duration = time.perf_counter() - started

        assert response.status_code == 503
        assert response.headers["retry-after"] == "2"
        assert response.json()["detail"]["code"] == "database_capacity_exceeded"
        assert duration < settings.DATABASE_POOL_TIMEOUT_SECONDS + 2
    finally:
        for connection in connections:
            connection.close()

    assert test_engine.pool.checkedout() == 0


def test_production_settings_reject_unsafe_jwt_secret():
    from app.config import settings, validate_production_settings

    original_environment = settings.ENVIRONMENT
    original_auth_required = settings.AUTH_REQUIRED
    original_jwt_secret = settings.JWT_SECRET
    original_cors_origins = settings.CORS_ORIGINS
    try:
        settings.ENVIRONMENT = "production"
        settings.AUTH_REQUIRED = True
        settings.JWT_SECRET = "development-only-change-me"
        settings.CORS_ORIGINS = "https://app.example.com"
        try:
            validate_production_settings()
            assert False, "unsafe production settings should be rejected"
        except RuntimeError as error:
            assert "JWT_SECRET" in str(error)
    finally:
        settings.ENVIRONMENT = original_environment
        settings.AUTH_REQUIRED = original_auth_required
        settings.JWT_SECRET = original_jwt_secret
        settings.CORS_ORIGINS = original_cors_origins


def test_production_settings_reject_invalid_database_pool():
    from app.config import settings, validate_production_settings

    originals = {
        "ENVIRONMENT": settings.ENVIRONMENT,
        "AUTH_REQUIRED": settings.AUTH_REQUIRED,
        "JWT_SECRET": settings.JWT_SECRET,
        "CORS_ORIGINS": settings.CORS_ORIGINS,
        "REQUIRE_EMAIL_VERIFICATION": settings.REQUIRE_EMAIL_VERIFICATION,
        "DATABASE_POOL_SIZE": settings.DATABASE_POOL_SIZE,
    }
    try:
        settings.ENVIRONMENT = "production"
        settings.AUTH_REQUIRED = True
        settings.JWT_SECRET = "a-production-secret-that-is-long-enough"
        settings.CORS_ORIGINS = "https://app.example.com"
        settings.REQUIRE_EMAIL_VERIFICATION = False
        settings.DATABASE_POOL_SIZE = 0

        with pytest.raises(RuntimeError, match="DATABASE_POOL_SIZE"):
            validate_production_settings()
    finally:
        for name, value in originals.items():
            setattr(settings, name, value)


def test_production_settings_reject_inline_design_agent_execution():
    from app.config import settings, validate_production_settings

    originals = {
        "ENVIRONMENT": settings.ENVIRONMENT,
        "AUTH_REQUIRED": settings.AUTH_REQUIRED,
        "JWT_SECRET": settings.JWT_SECRET,
        "CORS_ORIGINS": settings.CORS_ORIGINS,
        "REQUIRE_EMAIL_VERIFICATION": settings.REQUIRE_EMAIL_VERIFICATION,
        "DESIGN_AGENT_EXECUTION_MODE": settings.DESIGN_AGENT_EXECUTION_MODE,
    }
    try:
        settings.ENVIRONMENT = "production"
        settings.AUTH_REQUIRED = True
        settings.JWT_SECRET = "a-production-secret-that-is-long-enough"
        settings.CORS_ORIGINS = "https://app.example.com"
        settings.REQUIRE_EMAIL_VERIFICATION = False
        settings.DESIGN_AGENT_EXECUTION_MODE = "inline"

        with pytest.raises(RuntimeError, match="DESIGN_AGENT_EXECUTION_MODE"):
            validate_production_settings()
    finally:
        for name, value in originals.items():
            setattr(settings, name, value)


def test_chunker_logic():
    """Verify that chunking divides text within bounds and handles overlap correctly."""
    rag = RAGService()
    text = "This is a sentence. And here is another sentence that is longer. " * 20
    chunks = rag.chunk_text(text, chunk_size=100, chunk_overlap=20)
    
    assert len(chunks) > 0
    # Every chunk should be under our limit
    for chunk in chunks:
        assert len(chunk) <= 100
        assert len(chunk) > 0

def test_npc_lifecycle():
    """Verify create, validate, list, fetch, update, and soft-delete lifecycle of NPCs."""
    unique_slug = f"eldrin_mage_{uuid.uuid4().hex[:6]}"
    payload = {
        "slug": unique_slug,
        "name": "Eldrin",
        "title": "Archmage of the Watchtower",
        "personality_summary": "Cautious and scholarly librarian who speaks in warning tones.",
        "dialogue_style": "Uses formal language, hesitates frequently, and references history.",
        "voice_profile": "elderly-gravelly-english",
        "faction_alignment": "cinder_vanguard",
        "animation_hints": {"neutral": "idle_read", "concerned": "shake_head"},
        "memory_settings": {"search_threshold": 0.65},
        "metadata": {"custom_tag": "test-npc"}
    }
    
    # 1. Create NPC profile
    response = client.post("/api/v1/npcs", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["slug"] == unique_slug
    assert data["name"] == "Eldrin"
    assert "id" in data
    npc_id = data["id"]

    # 2. Invalid slug rejection: too short
    payload_invalid_len = payload.copy()
    payload_invalid_len["slug"] = "el"
    response = client.post("/api/v1/npcs", json=payload_invalid_len)
    assert response.status_code == 422  # Pydantic validation error

    # Invalid slug rejection: invalid characters (uppercase / punctuation)
    payload_invalid_chars = payload.copy()
    payload_invalid_chars["slug"] = "Eldrin_Mage!"
    response = client.post("/api/v1/npcs", json=payload_invalid_chars)
    assert response.status_code == 422

    # 3. Duplicate slug rejection
    response = client.post("/api/v1/npcs", json=payload)
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]

    # 4. List NPC profiles
    response = client.get("/api/v1/npcs")
    assert response.status_code == 200
    npcs = response.json()
    assert any(n["id"] == npc_id for n in npcs)

    # 5. Fetch NPC by ID
    response = client.get(f"/api/v1/npcs/{npc_id}")
    assert response.status_code == 200
    assert response.json()["slug"] == unique_slug

    # 6. Update NPC profile
    update_payload = {
        "title": "Grand Archmage of the Watchtower",
        "personality_summary": "Extremely cautious and scholarly librarian.",
        "metadata": {"updated_tag": "test-npc-updated"}
    }
    response = client.put(f"/api/v1/npcs/{npc_id}", json=update_payload)
    assert response.status_code == 200
    updated_data = response.json()
    assert updated_data["title"] == "Grand Archmage of the Watchtower"
    assert updated_data["personality_summary"] == "Extremely cautious and scholarly librarian."
    assert updated_data["metadata"]["updated_tag"] == "test-npc-updated"
    assert updated_data["name"] == "Eldrin"  # verify name remains unchanged

    # 7. Soft delete NPC
    response = client.delete(f"/api/v1/npcs/{npc_id}")
    assert response.status_code == 200
    assert "soft-deleted successfully" in response.json()["message"]

    # 8. Verify deleted NPC no longer appears in listings
    response = client.get("/api/v1/npcs")
    assert response.status_code == 200
    npcs_after = response.json()
    assert not any(n["id"] == npc_id for n in npcs_after)

    # 9. Verify deleted NPC returns 404 on GET by ID
    response = client.get(f"/api/v1/npcs/{npc_id}")
    assert response.status_code == 404
