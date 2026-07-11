import pytest
from fastapi.testclient import TestClient
from main import app
from app.models.blueprint import GameBlueprint
from app.models.npc import NPCProfile
from app.models.quest import Quest, QuestObjective
from app.models.memory import NPCMemory
from app.models.world_state import WorldStateFlag
import uuid

client = TestClient(app)

@pytest.fixture
def make_blueprint(db_session):
    """Fixture to build blueprints with distinct game_project_ids for test isolation."""
    def _make(game_project_id: str, status: str = "approved") -> GameBlueprint:
        bp_id = uuid.uuid4()
        bp = GameBlueprint(
            id=bp_id,
            title="Blueprint: Frostpeak GDD",
            document_id=None,
            game_project_id=game_project_id,
            summary={
                "content": {"title": "Frostpeak", "description": "Frost game"},
                "citations": [], "confidence": "High", "warnings": []
            },
            narrative_direction={
                "content": {"themes": ["Eternal Winter"], "lore_background": "Cold lands"},
                "citations": [], "confidence": "High", "warnings": []
            },
            art_style_direction={
                "content": {"visual_theme": "Icy Dark Fantasy", "color_palette": ["#000", "#fff"]},
                "citations": [], "confidence": "High", "warnings": []
            },
            npc_archetypes={
                "content": {
                    "npcs": [
                        {"name": "NPC Eldrin", "archetype": "Mentoring wizard", "dialogue_style": "Slow and formal."}
                    ]
                },
                "citations": [], "confidence": "High", "warnings": []
            },
            npc_memory_design={
                "content": {
                    "memory_nodes": [
                        {"subject": "Ember Siege historical memories", "importance": 9.0}
                    ]
                },
                "citations": [], "confidence": "High", "warnings": []
            },
            level_design_suggestions={
                "content": {
                    "level_layout": "Volcanic vents,East Gate unlocked",
                    "interactive_elements": ["checkpoint-vent-alpha", "east-gate-locked"]
                },
                "citations": [], "confidence": "High", "warnings": []
            },
            quest_hooks={
                "content": {
                    "quests": [
                        {"title": "Reclaim Ash Pass Objective", "objective": "Reclaim the Ash Pass outpost."}
                    ]
                },
                "citations": [], "confidence": "High", "warnings": []
            },
            unity_runtime_preview={
                "content": {}, "citations": [], "confidence": "High", "warnings": []
            },
            status=status,
            materialization_manifest=None
        )
        db_session.add(bp)
        db_session.commit()
        db_session.refresh(bp)
        return bp
    return _make

def test_materialize_draft_rejected(db_session, make_blueprint):
    """Test draft blueprints are blocked from materialization."""
    project_id = f"project_{uuid.uuid4().hex[:6]}"
    bp = make_blueprint(project_id, "draft")
    
    response = client.post(
        f"/api/v1/blueprints/{bp.id}/materialize",
        headers={"X-Game-Project-ID": project_id}
    )
    assert response.status_code == 400
    assert "Only approved blueprints" in response.json()["detail"]

def test_materialize_first_run_creates_records(db_session, make_blueprint):
    """Test first run of materialize creates db rows and updates the manifest column."""
    project_id = f"project_{uuid.uuid4().hex[:6]}"
    bp = make_blueprint(project_id, "approved")

    response = client.post(
        f"/api/v1/blueprints/{bp.id}/materialize",
        headers={"X-Game-Project-ID": project_id}
    )
    assert response.status_code == 200
    report = response.json()
    assert report["status"] == "success"
    
    # Check creation counts
    assert len(report["npcs"]["created"]) == 1
    assert "eldrin" in report["npcs"]["created"]
    assert len(report["quests"]["created"]) == 1
    assert len(report["memories"]["created"]) == 1
    assert len(report["flags"]["created"]) == 2

    # Check manifest is saved to DB
    db_session.refresh(bp)
    manifest = bp.materialization_manifest
    assert manifest is not None
    assert "eldrin" in manifest["npcs"]
    assert len(manifest["quest_ids"]) == 1
    assert len(manifest["memory_ids"]) == 1
    assert "checkpoint-vent-alpha" in manifest["flag_keys"]
    assert manifest["last_materialized_at"] is not None

def test_materialize_second_run_idempotent(db_session, make_blueprint):
    """Test subsequent materialize runs do not duplicate rows."""
    project_id = f"project_{uuid.uuid4().hex[:6]}"
    bp = make_blueprint(project_id, "approved")

    # First run
    client.post(
        f"/api/v1/blueprints/{bp.id}/materialize",
        headers={"X-Game-Project-ID": project_id}
    )
    
    # Second run
    response = client.post(
        f"/api/v1/blueprints/{bp.id}/materialize",
        headers={"X-Game-Project-ID": project_id}
    )
    assert response.status_code == 200
    report = response.json()
    
    # Verify no new creations occurred
    assert len(report["npcs"]["created"]) == 0
    assert len(report["quests"]["created"]) == 0
    assert len(report["memories"]["created"]) == 0
    assert len(report["flags"]["created"]) == 0
    
    # Verify they were safely updated or skipped
    assert len(report["npcs"]["updated"]) == 1
    assert len(report["quests"]["updated"]) == 1
    assert len(report["memories"]["updated"]) == 1
    assert len(report["flags"]["updated"]) == 2

def test_materialize_skips_malformed_npc_fragments(db_session, make_blueprint):
    """Blueprint prose fragments must not become runtime NPC profiles."""
    project_id = f"project_{uuid.uuid4().hex[:6]}"
    bp = make_blueprint(project_id, "approved")
    bp.npc_archetypes = {
        "content": {
            "npcs": [
                {
                    "name": "The story centers ar",
                    "archetype": "Extracted prose fragment",
                    "dialogue_style": "Invalid generated fragment."
                },
                {
                    "name": "**NPC Eldrin**",
                    "archetype": "Mentoring wizard",
                    "dialogue_style": "Slow and formal."
                },
            ]
        },
        "citations": [],
        "confidence": "High",
        "warnings": []
    }
    db_session.commit()

    response = client.post(
        f"/api/v1/blueprints/{bp.id}/materialize",
        headers={"X-Game-Project-ID": project_id}
    )

    assert response.status_code == 200
    report = response.json()
    assert "The story centers ar" in report["npcs"]["skipped"]
    assert "eldrin" in report["npcs"]["created"]
    assert any("Skipped malformed NPC entry" in warning for warning in report["warnings"])

    slugs = [npc.slug for npc in db_session.query(NPCProfile).filter(NPCProfile.game_project_id == project_id).all()]
    assert slugs == ["eldrin"]

def test_materialize_skips_user_created_data(db_session, make_blueprint):
    """Test user-created records are skipped and warn, never overwritten."""
    project_id = f"project_{uuid.uuid4().hex[:6]}"
    bp = make_blueprint(project_id, "approved")

    # Pre-create a manual user NPC with slug eldrin
    user_npc = NPCProfile(
        id=uuid.uuid4(),
        slug="eldrin",
        name="User Custom Eldrin",
        personality_summary="User defined text.",
        game_project_id=project_id
    )
    db_session.add(user_npc)
    
    # Pre-create a manual user Quest with the same title
    user_quest = Quest(
        id=uuid.uuid4(),
        title="Reclaim Ash Pass Objective",
        description="User defined quest desc.",
        npc_slug="eldrin",
        game_project_id=project_id
    )
    db_session.add(user_quest)
    db_session.commit()
    
    # Trigger materialize
    response = client.post(
        f"/api/v1/blueprints/{bp.id}/materialize",
        headers={"X-Game-Project-ID": project_id}
    )
    assert response.status_code == 200
    report = response.json()
    
    # NPC and Quest must be reported as skipped
    assert "eldrin" in report["npcs"]["skipped"]
    assert "Reclaim Ash Pass Objective" in report["quests"]["skipped"]
    assert len(report["warnings"]) >= 2
    assert "already exists in database and is not owned by this blueprint" in report["warnings"][0]

    # Verify db values remain untouched
    db_session.refresh(user_npc)
    assert user_npc.name == "User Custom Eldrin"
    assert user_npc.personality_summary == "User defined text."

    db_session.refresh(user_quest)
    assert user_quest.description == "User defined quest desc."

def test_runtime_bundle_returns_manifest_only(db_session, make_blueprint):
    """Test runtime bundle returns only the entities linked in the manifest."""
    project_id = f"project_{uuid.uuid4().hex[:6]}"
    bp = make_blueprint(project_id, "approved")

    # 1. Materialize blueprint
    client.post(
        f"/api/v1/blueprints/{bp.id}/materialize",
        headers={"X-Game-Project-ID": project_id}
    )
    
    # 2. Add a separate user NPC and Quest (unrelated to the blueprint)
    unrelated_npc = NPCProfile(
        id=uuid.uuid4(),
        slug="npc-gardener",
        name="Gardener",
        personality_summary="Loves flowers.",
        game_project_id=project_id
    )
    db_session.add(unrelated_npc)
    
    unrelated_quest = Quest(
        id=uuid.uuid4(),
        title="Water the plants",
        description="Water 3 plants.",
        npc_slug="npc-gardener",
        game_project_id=project_id
    )
    db_session.add(unrelated_quest)
    db_session.commit()
    
    # 3. Retrieve runtime bundle
    response = client.get(
        f"/api/v1/blueprints/{bp.id}/runtime-bundle",
        headers={"X-Game-Project-ID": project_id}
    )
    assert response.status_code == 200
    bundle = response.json()
    
    # Confirm it returns exactly the manifest-linked items only (no gardener)
    npcs = [npc["slug"] for npc in bundle["npcs"]]
    assert "eldrin" in npcs
    assert "npc-gardener" not in npcs
    
    quests = [q["title"] for q in bundle["quests"]]
    assert "Reclaim Ash Pass Objective" in quests
    assert "Water the plants" not in quests
    manifest_quest = next(q for q in bundle["quests"] if q["title"] == "Reclaim Ash Pass Objective")
    assert manifest_quest["objectives"]
    assert manifest_quest["objectives"][0]["description"] == "Reclaim the Ash Pass outpost."

def test_runtime_bundle_falls_back_to_matching_records_when_manifest_empty(db_session, make_blueprint):
    """Unity demo bundles still load when a materialization skipped duplicate matching records."""
    project_id = f"project_{uuid.uuid4().hex[:6]}"
    bp = make_blueprint(project_id, "approved")

    existing_npc = NPCProfile(
        id=uuid.uuid4(),
        slug="eldrin",
        name="Eldrin",
        personality_summary="Existing runtime NPC.",
        dialogue_style="Slow and formal.",
        game_project_id=project_id
    )
    db_session.add(existing_npc)

    existing_quest = Quest(
        id=uuid.uuid4(),
        title="Reclaim Ash Pass Objective",
        description="Existing runtime quest.",
        npc_slug="eldrin",
        game_project_id=project_id
    )
    db_session.add(existing_quest)
    db_session.add(QuestObjective(
        id=uuid.uuid4(),
        quest_id=existing_quest.id,
        objective_index=0,
        description="Reclaim the Ash Pass outpost.",
        target_type="retrieve",
        target_id="key",
        quantity_required=1
    ))

    db_session.add(NPCMemory(
        id=uuid.uuid4(),
        npc_id=existing_npc.id,
        memory_text="Ember Siege historical memories",
        memory_type="episodic",
        importance_score=9.0,
        chroma_indexed=False,
        archived=False,
        game_project_id=project_id
    ))

    db_session.add(WorldStateFlag(
        game_project_id=project_id,
        flag_key="checkpoint-vent-alpha",
        flag_value="unlocked",
        is_active=True,
        priority=1
    ))
    db_session.add(WorldStateFlag(
        game_project_id=project_id,
        flag_key="east-gate-locked",
        flag_value="unlocked",
        is_active=True,
        priority=1
    ))
    db_session.commit()

    materialize_response = client.post(
        f"/api/v1/blueprints/{bp.id}/materialize",
        headers={"X-Game-Project-ID": project_id}
    )
    assert materialize_response.status_code == 200
    db_session.refresh(bp)
    assert bp.materialization_manifest["last_materialized_at"] is not None
    assert bp.materialization_manifest["npcs"] == []
    assert bp.materialization_manifest["quest_ids"] == []
    assert bp.materialization_manifest["memory_ids"] == []
    assert bp.materialization_manifest["flag_keys"] == []

    response = client.get(
        f"/api/v1/blueprints/{bp.id}/runtime-bundle",
        headers={"X-Game-Project-ID": project_id}
    )
    assert response.status_code == 200
    bundle = response.json()
    assert [npc["slug"] for npc in bundle["npcs"]] == ["eldrin"]
    assert [quest["title"] for quest in bundle["quests"]] == ["Reclaim Ash Pass Objective"]
    assert [memory["memory_text"] for memory in bundle["memories"]] == ["Ember Siege historical memories"]
    assert sorted(flag["flag_key"] for flag in bundle["world_flags"]) == [
        "checkpoint-vent-alpha",
        "east-gate-locked",
    ]

def test_latest_runtime_bundle_returns_newest_materialized_blueprint(make_blueprint):
    """Unity can auto-load the newest materialized bundle without a pasted blueprint ID."""
    project_id = f"project_{uuid.uuid4().hex[:6]}"
    bp = make_blueprint(project_id, "approved")

    materialize_response = client.post(
        f"/api/v1/blueprints/{bp.id}/materialize",
        headers={"X-Game-Project-ID": project_id}
    )
    assert materialize_response.status_code == 200

    response = client.get(
        "/api/v1/blueprints/runtime/latest-bundle",
        headers={"X-Game-Project-ID": project_id}
    )
    assert response.status_code == 200
    bundle = response.json()
    assert bundle["blueprint_id"] == str(bp.id)
    assert bundle["game_project_id"] == project_id
    assert [npc["slug"] for npc in bundle["npcs"]] == ["eldrin"]

def test_latest_runtime_bundle_requires_materialized_blueprint(make_blueprint):
    project_id = f"project_{uuid.uuid4().hex[:6]}"
    make_blueprint(project_id, "approved")

    response = client.get(
        "/api/v1/blueprints/runtime/latest-bundle",
        headers={"X-Game-Project-ID": project_id}
    )
    assert response.status_code == 404
    assert "No materialized blueprint" in response.json()["detail"]

def test_project_isolation(make_blueprint):
    """Test materialize and bundle block unauthorized cross-project access."""
    project_id = f"project_{uuid.uuid4().hex[:6]}"
    bp = make_blueprint(project_id, "approved")

    # Try calling materialize with game_project_id = project_gamma
    response = client.post(
        f"/api/v1/blueprints/{bp.id}/materialize",
        headers={"X-Game-Project-ID": "project_gamma"}
    )
    assert response.status_code == 404
    
    # Try getting bundle with project_gamma
    response_bundle = client.get(
        f"/api/v1/blueprints/{bp.id}/runtime-bundle",
        headers={"X-Game-Project-ID": "project_gamma"}
    )
    assert response_bundle.status_code == 404
