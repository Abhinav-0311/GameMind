import uuid

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.models.graph import WorldEntity, WorldRelationship
from app.models.memory import NPCMemory
from app.models.npc import NPCProfile
from app.services.event_simulation import EventChainSimulator
from app.services.memory_service import MemoryService
from main import app


@pytest.fixture
def auth_required():
    original = settings.AUTH_REQUIRED
    settings.AUTH_REQUIRED = True
    try:
        yield
    finally:
        settings.AUTH_REQUIRED = original


def test_narrative_and_memory_sync_require_a_session(auth_required):
    client = TestClient(app)

    assert client.get("/api/v1/narrative/forecast").status_code == 401
    assert client.post("/api/v1/narrative/orchestrate/tick").status_code == 401
    assert client.post("/api/v1/memories/sync").status_code == 401


def test_narrative_rejects_an_authenticated_user_without_workspace_membership(auth_required):
    owner_client = TestClient(app)
    outsider_client = TestClient(app)
    password = "correct-horse-battery-staple"

    assert owner_client.post(
        "/api/v1/auth/register",
        json={"email": f"owner-{uuid.uuid4().hex[:10]}@example.com", "password": password},
    ).status_code == 201
    workspace = owner_client.post(
        "/api/v1/projects/", json={"name": f"Narrative workspace {uuid.uuid4().hex[:6]}"}
    )
    assert workspace.status_code == 201

    assert outsider_client.post(
        "/api/v1/auth/register",
        json={"email": f"outsider-{uuid.uuid4().hex[:10]}@example.com", "password": password},
    ).status_code == 201

    response = outsider_client.get(
        "/api/v1/narrative/forecast",
        headers={"X-Game-Project-ID": workspace.json()["id"]},
    )
    assert response.status_code == 403


def test_event_simulation_reads_only_the_selected_workspace(db_session):
    project_a = f"project-a-{uuid.uuid4().hex[:8]}"
    project_b = f"project-b-{uuid.uuid4().hex[:8]}"
    shared_slug = f"opening-{uuid.uuid4().hex[:8]}"
    target_a = f"target-a-{uuid.uuid4().hex[:8]}"
    target_b = f"target-b-{uuid.uuid4().hex[:8]}"

    source_a = WorldEntity(slug=shared_slug, entity_type="event", game_project_id=project_a)
    destination_a = WorldEntity(slug=target_a, entity_type="event", game_project_id=project_a)
    source_b = WorldEntity(slug=shared_slug, entity_type="event", game_project_id=project_b)
    destination_b = WorldEntity(slug=target_b, entity_type="event", game_project_id=project_b)
    db_session.add_all([source_a, destination_a, source_b, destination_b])
    db_session.flush()
    db_session.add_all([
        WorldRelationship(
            source_id=source_a.id,
            target_id=destination_a.id,
            rel_type="next",
            game_project_id=project_a,
        ),
        WorldRelationship(
            source_id=source_b.id,
            target_id=destination_b.id,
            rel_type="next",
            game_project_id=project_b,
        ),
    ])
    db_session.commit()

    simulation = EventChainSimulator.simulate_narrative_paths(
        db_session, [shared_slug], game_project_id=project_a
    )

    assert target_a in simulation["path"]
    assert target_b not in simulation["path"]


def test_memory_sync_filters_to_the_selected_workspace(db_session):
    memory_service = MemoryService.__new__(MemoryService)
    indexed = []

    npc_a = NPCProfile(
        slug=f"npc-a-{uuid.uuid4().hex[:8]}",
        name="NPC A",
        personality_summary="Scoped test NPC.",
        game_project_id="workspace-a",
    )
    npc_b = NPCProfile(
        slug=f"npc-b-{uuid.uuid4().hex[:8]}",
        name="NPC B",
        personality_summary="Scoped test NPC.",
        game_project_id="workspace-b",
    )
    db_session.add_all([npc_a, npc_b])
    db_session.flush()
    memory_a = NPCMemory(npc_id=npc_a.id, memory_text="A only", game_project_id="workspace-a")
    memory_b = NPCMemory(npc_id=npc_b.id, memory_text="B only", game_project_id="workspace-b")
    db_session.add_all([memory_a, memory_b])
    db_session.commit()

    memory_service.index_memory_in_chroma = lambda _db, memory: indexed.append(memory.id)

    result = memory_service.sync_unindexed_memories(db_session, game_project_id="workspace-a")

    assert result == {"processed": 1, "failed": 0}
    assert indexed == [memory_a.id]
