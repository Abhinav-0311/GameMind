import pytest
from fastapi.testclient import TestClient
from main import app
from app.services.rag_service import RAGService
from app.models.document import Document
from app.models.blueprint import GameBlueprint
import uuid

client = TestClient(app)

@pytest.fixture
def uploaded_document(db_session):
    """Fixture to upload a sample GDD document for testing."""
    rag = RAGService()
    
    file_name = f"gdd_test_{uuid.uuid4().hex[:6]}.txt"
    file_bytes = (
        b"# GDD Summary\n"
        b"Overview: A game about exploring cold towers.\n"
        b"# Art Style\n"
        b"Visual Theme: Stylized dark fantasy visual elements.\n"
        b"# NPC Profiles\n"
        b"NPC Eldrin: A wise old librarian archmage.\n"
        b"# Level Design\n"
        b"Level Geothermal Vents: active vents and locked East Gate.\n"
        b"# Quest Hooks\n"
        b"Quest Hook 1: Objective: Reclaim Ash Pass."
    )
    
    doc = rag.process_document(
        db=db_session,
        file_name=file_name,
        file_bytes=file_bytes,
        content_type="text/plain",
        game_project_id="test_project_alpha"
    )
    return doc

def test_generate_blueprint_success(uploaded_document):
    """Test generating a game blueprint from an existing GDD document succeeds."""
    response = client.post(
        "/api/v1/blueprints/generate",
        json={"document_id": str(uploaded_document.id)},
        headers={"X-Game-Project-ID": "test_project_alpha"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == f"Blueprint: {uploaded_document.title}"
    assert data["game_project_id"] == "test_project_alpha"
    assert data["status"] == "draft"
    
    # Assert all 8 sections are populated
    for section in ["summary", "narrative_direction", "art_style_direction", "npc_archetypes", 
                    "npc_memory_design", "level_design_suggestions", "quest_hooks", "unity_runtime_preview"]:
        assert section in data
        assert "content" in data[section]
        assert "citations" in data[section]
        assert "confidence" in data[section]
        assert "warnings" in data[section]


def test_generate_blueprint_uses_selected_supporting_sources(db_session):
    """A supporting NPC sheet may enrich the blueprint without replacing its primary GDD."""
    rag = RAGService()
    project_id = f"multi_source_{uuid.uuid4().hex[:8]}"
    primary = rag.process_document(
        db=db_session,
        file_name="main_gdd.md",
        file_bytes=b"# GDD\nOverview: Explore an ancient observatory.",
        content_type="text/markdown",
        game_project_id=project_id,
    )
    npc_sheet = rag.process_document(
        db=db_session,
        file_name="npc_sheet.md",
        file_bytes=b"# NPC Profiles\nNPC Lyra: A practical observatory keeper.",
        content_type="text/markdown",
        game_project_id=project_id,
    )

    response = client.post(
        "/api/v1/blueprints/generate",
        headers={"X-Game-Project-ID": project_id},
        json={"document_id": str(primary.id), "supporting_document_ids": [str(npc_sheet.id)]},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["document_id"] == str(primary.id)
    assert data["source_document_ids"] == [str(primary.id), str(npc_sheet.id)]
    assert data["npc_archetypes"]["content"]["npcs"][0]["name"] == "Lyra"


def test_generate_blueprint_rejects_cross_project_supporting_source(db_session):
    rag = RAGService()
    primary = rag.process_document(
        db=db_session,
        file_name="owner_gdd.md",
        file_bytes=b"# GDD\nOverview: A private game.",
        content_type="text/markdown",
        game_project_id="multi_owner",
    )
    foreign = rag.process_document(
        db=db_session,
        file_name="foreign_lore.md",
        file_bytes=b"# Lore\nPrivate world history.",
        content_type="text/markdown",
        game_project_id="multi_foreign",
    )

    response = client.post(
        "/api/v1/blueprints/generate",
        headers={"X-Game-Project-ID": "multi_owner"},
        json={"document_id": str(primary.id), "supporting_document_ids": [str(foreign.id)]},
    )
    assert response.status_code == 404

def test_approve_blueprint_success(uploaded_document):
    """Test approving a game blueprint updates its status to 'approved'."""
    # 1. Generate
    gen_response = client.post(
        "/api/v1/blueprints/generate",
        json={"document_id": str(uploaded_document.id)},
        headers={"X-Game-Project-ID": "test_project_alpha"}
    )
    blueprint_id = gen_response.json()["id"]

    # 2. Approve
    app_response = client.put(
        f"/api/v1/blueprints/{blueprint_id}/approve",
        headers={"X-Game-Project-ID": "test_project_alpha"}
    )
    assert app_response.status_code == 200
    assert app_response.json()["status"] == "approved"

def test_export_blueprint_success(uploaded_document):
    """Test exporting a game blueprint yields valid Unity runtime JSON."""
    # 1. Generate
    gen_response = client.post(
        "/api/v1/blueprints/generate",
        json={"document_id": str(uploaded_document.id)},
        headers={"X-Game-Project-ID": "test_project_alpha"}
    )
    blueprint_id = gen_response.json()["id"]

    # 2. Export
    exp_response = client.get(
        f"/api/v1/blueprints/{blueprint_id}/export",
        headers={"X-Game-Project-ID": "test_project_alpha"}
    )
    assert exp_response.status_code == 200
    data = exp_response.json()
    assert data["api_version"] == "1.0"
    assert data["game_project_id"] == "test_project_alpha"
    assert "runtime_data" in data
    
    # Verify runtime elements are present
    runtime = data["runtime_data"]
    assert "game_summary" in runtime
    assert "art_style" in runtime
    assert "npcs" in runtime
    assert "levels" in runtime
    assert "quests" in runtime

def test_project_scoping_enforcement(uploaded_document):
    """Test that blueprints enforce strict project-scoped ownership boundaries."""
    # Try generating a blueprint with a different game_project_id (X-Game-Project-ID: project_beta)
    # This should fail because the document belongs to test_project_alpha
    gen_response = client.post(
        "/api/v1/blueprints/generate",
        json={"document_id": str(uploaded_document.id)},
        headers={"X-Game-Project-ID": "project_beta"}
    )
    assert gen_response.status_code == 404
    assert "not owned by this project" in gen_response.json()["detail"]

def test_missing_input_warnings_and_citations(uploaded_document):
    """Test that missing GDD section content generates template warnings and correct citations."""
    response = client.post(
        "/api/v1/blueprints/generate",
        json={"document_id": str(uploaded_document.id)},
        headers={"X-Game-Project-ID": "test_project_alpha"}
    )
    assert response.status_code == 201
    data = response.json()
    
    # Summary should be high confidence (present in GDD text)
    assert data["summary"]["confidence"] == "High"
    assert len(data["summary"]["citations"]) > 0
    
    # NPC Memory should trigger template fallback warning since the text did not contain memory keywords
    assert data["npc_memory_design"]["confidence"] == "Low"
    assert len(data["npc_memory_design"]["warnings"]) > 0
    assert "No key event memory configurations" in data["npc_memory_design"]["warnings"][0]

def test_blueprint_extracts_only_explicit_npc_profiles(uploaded_document):
    """NPC extraction must not turn general lore prose into fake NPC records."""
    response = client.post(
        "/api/v1/blueprints/generate",
        json={"document_id": str(uploaded_document.id)},
        headers={"X-Game-Project-ID": "test_project_alpha"}
    )
    assert response.status_code == 201
    data = response.json()

    npcs = data["npc_archetypes"]["content"]["npcs"]
    assert len(npcs) == 1
    assert npcs[0]["name"] == "Eldrin"
    assert "wise old librarian archmage" in npcs[0]["dialogue_style"]

def test_blueprint_generates_distinct_quest_titles(uploaded_document):
    """Quest titles should be derived from objectives instead of duplicate generic names."""
    response = client.post(
        "/api/v1/blueprints/generate",
        json={"document_id": str(uploaded_document.id)},
        headers={"X-Game-Project-ID": "test_project_alpha"}
    )
    assert response.status_code == 201
    data = response.json()

    quests = data["quest_hooks"]["content"]["quests"]
    titles = [quest["title"] for quest in quests]
    assert titles == ["Reclaim Ash Pass"]
    assert len(titles) == len(set(titles))

def test_blueprint_extracts_source_art_and_level_details(uploaded_document):
    """Structured fields should preserve facts from the GDD instead of generic styling defaults."""
    response = client.post(
        "/api/v1/blueprints/generate",
        json={"document_id": str(uploaded_document.id)},
        headers={"X-Game-Project-ID": "test_project_alpha"},
    )
    assert response.status_code == 201
    data = response.json()

    art = data["art_style_direction"]["content"]
    assert art["visual_theme"] == "Stylized dark fantasy visual elements"
    assert art["color_palette"] == []

    levels = data["level_design_suggestions"]["content"]
    assert "Level Geothermal Vents" in levels["level_layout"]
    assert any("vents" in element.lower() for element in levels["interactive_elements"])
    assert any("east gate" in element.lower() for element in levels["interactive_elements"])

def test_blueprint_leaves_unsupported_sections_empty(db_session):
    """A sparse GDD must produce warnings, not fabricated lore, NPCs, quests, or level data."""
    rag = RAGService()
    document = rag.process_document(
        db=db_session,
        file_name=f"sparse_{uuid.uuid4().hex[:6]}.txt",
        file_bytes=b"# Small Prototype\nA two-button puzzle game for one player.",
        content_type="text/plain",
        game_project_id="test_project_alpha",
    )

    response = client.post(
        "/api/v1/blueprints/generate",
        json={"document_id": str(document.id)},
        headers={"X-Game-Project-ID": "test_project_alpha"},
    )
    assert response.status_code == 201
    data = response.json()

    assert data["narrative_direction"]["content"] == {"themes": [], "lore_background": None}
    assert data["art_style_direction"]["content"] == {
        "visual_theme": None,
        "color_palette": [],
        "visual_notes": [],
    }
    assert data["npc_archetypes"]["content"]["npcs"] == []
    assert data["npc_memory_design"]["content"]["memory_nodes"] == []
    assert data["level_design_suggestions"]["content"] == {
        "level_layout": None,
        "interactive_elements": [],
    }
    assert data["quest_hooks"]["content"]["quests"] == []
    assert all(section["warnings"] for section in [
        data["narrative_direction"],
        data["art_style_direction"],
        data["npc_archetypes"],
        data["npc_memory_design"],
        data["level_design_suggestions"],
        data["quest_hooks"],
    ])

def test_blueprint_extracts_npcs_and_quests_from_markdown_tables(db_session):
    """Common compact GDD tables should become structured, source-backed runtime data."""
    rag = RAGService()
    document = rag.process_document(
        db=db_session,
        file_name=f"table_gdd_{uuid.uuid4().hex[:6]}.md",
        file_bytes=(
            b"# Characters\n"
            b"| Name | Role | Dialogue Style |\n"
            b"| --- | --- | --- |\n"
            b"| Mira | Systems engineer | Direct and practical |\n"
            b"| Orren | Archivist | Patient and reflective |\n\n"
            b"# Quest Plan\n"
            b"| Title | Objective | Reward |\n"
            b"| --- | --- | --- |\n"
            b"| Restore Power | Activate three substations | 80 credits |\n"
            b"| Map the Ruins | Survey the flooded archive | Access key |\n"
        ),
        content_type="text/markdown",
        game_project_id="test_project_alpha",
    )

    response = client.post(
        "/api/v1/blueprints/generate",
        json={"document_id": str(document.id)},
        headers={"X-Game-Project-ID": "test_project_alpha"},
    )
    assert response.status_code == 201
    data = response.json()

    assert data["npc_archetypes"]["content"]["npcs"] == [
        {"name": "Mira", "archetype": "Systems engineer", "dialogue_style": "Direct and practical"},
        {"name": "Orren", "archetype": "Archivist", "dialogue_style": "Patient and reflective"},
    ]
    assert data["quest_hooks"]["content"]["quests"] == [
        {"id": "q_0", "title": "Restore Power", "objective": "Activate three substations", "reward": "80 credits"},
        {"id": "q_1", "title": "Map the Ruins", "objective": "Survey the flooded archive", "reward": "Access key"},
    ]
    assert data["npc_archetypes"]["citations"]
    assert data["quest_hooks"]["citations"]


def test_blueprint_extracts_characters_and_missions_from_explicit_gdd_headings(db_session):
    """Long-form GDD headings should yield source-backed runtime candidates."""
    rag = RAGService()
    document = rag.process_document(
        db=db_session,
        file_name=f"long_form_{uuid.uuid4().hex[:6]}.md",
        file_bytes=(
            b"# Narrative\nA grounded security adventure.\n\n"
            b"## Main Characters\n"
            b"### Ada\nAda is the player character and a careful systems apprentice.\n\n"
            b"### Beacon\nBeacon is Ada's guide and gives concise warnings.\n\n"
            b"## Story Mode Level Plan\n"
            b"### Level 1: Signal Yard\nFocus: restore the disabled relay and avoid patrol drones.\n\n"
            b"### Level 2: Archive Gate\nFocus: solve the access-control puzzle and recover the audit record.\n"
        ),
        content_type="text/markdown",
        game_project_id="test_project_alpha",
    )

    response = client.post(
        "/api/v1/blueprints/generate",
        json={"document_id": str(document.id)},
        headers={"X-Game-Project-ID": "test_project_alpha"},
    )

    assert response.status_code == 201
    data = response.json()
    assert [npc["name"] for npc in data["npc_archetypes"]["content"]["npcs"]] == ["Ada", "Beacon"]
    assert [quest["title"] for quest in data["quest_hooks"]["content"]["quests"]] == ["Signal Yard", "Archive Gate"]
    assert data["npc_archetypes"]["citations"]
    assert data["quest_hooks"]["citations"]


def test_explicit_quest_records_override_inferred_level_plan_quests(db_session):
    """Dedicated quest definitions must win over level-plan fallback extraction."""
    rag = RAGService()
    document = rag.process_document(
        db=db_session,
        file_name=f"explicit_quests_{uuid.uuid4().hex[:6]}.md",
        file_bytes=(
            b"# Story Mode Level Plan\n"
            b"### Level 1: Signal Yard\n"
            b"Focus: restore the disabled relay and avoid patrol drones.\n\n"
            b"# Quest Contracts\n"
            b"| Quest | Objective | Reward |\n"
            b"| --- | --- | --- |\n"
            b"| Restore the Relay | Activate the signal relay | Access key |\n"
        ),
        content_type="text/markdown",
        game_project_id="test_project_alpha",
    )

    response = client.post(
        "/api/v1/blueprints/generate",
        json={"document_id": str(document.id)},
        headers={"X-Game-Project-ID": "test_project_alpha"},
    )

    assert response.status_code == 201
    quests = response.json()["quest_hooks"]["content"]["quests"]
    assert quests == [{
        "id": "q_0",
        "title": "Restore the Relay",
        "objective": "Activate the signal relay",
        "reward": "Access key",
    }]

def test_blueprint_extracts_explicit_gameplay_systems(db_session):
    """Gameplay sections should remain empty unless the GDD labels actual mechanics or rules."""
    rag = RAGService()
    document = rag.process_document(
        db=db_session,
        file_name=f"systems_gdd_{uuid.uuid4().hex[:6]}.md",
        file_bytes=(
            b"# Gameplay Loop\n"
            b"Core loop: Explore derelict stations, scan artifacts, craft upgrades, and return safely.\n\n"
            b"# Progression\n"
            b"Players earn research points to unlock navigation modules.\n\n"
            b"# Constraints\n"
            b"The player can carry only two power cells at once.\n"
        ),
        content_type="text/markdown",
        game_project_id="test_project_alpha",
    )

    response = client.post(
        "/api/v1/blueprints/generate",
        json={"document_id": str(document.id)},
        headers={"X-Game-Project-ID": "test_project_alpha"},
    )
    assert response.status_code == 201
    systems = response.json()["gameplay_systems"]

    assert systems["confidence"] == "High"
    assert systems["content"] == {
        "core_loop": ["Explore derelict stations, scan artifacts, craft upgrades, and return safely."],
        "progression": ["Players earn research points to unlock navigation modules."],
        "design_constraints": ["The player can carry only two power cells at once."],
        "technical_constraints": [],
        "accessibility": [],
        "platforms_controls": [],
        "economy": [],
    }
    assert systems["citations"]


def test_blueprint_extracts_explicit_production_requirements(db_session):
    """Practical GDD requirements must stay source-backed and expose missing coverage."""
    rag = RAGService()
    document = rag.process_document(
        db=db_session,
        file_name=f"production_gdd_{uuid.uuid4().hex[:6]}.md",
        file_bytes=(
            b"# Economy\nCredits are earned from contracts and spent on ship repairs.\n\n"
            b"# Platforms and Controls\nTarget platform: Windows PC. Keyboard, mouse, and controller input are required.\n\n"
            b"# Accessibility\nInclude subtitles, remappable controls, and color blind safe objective markers.\n\n"
            b"# Technical Constraints\nMaintain 60 FPS on the target device and support offline saves.\n"
        ),
        content_type="text/markdown",
        game_project_id="test_project_alpha",
    )

    response = client.post(
        "/api/v1/blueprints/generate",
        json={"document_id": str(document.id)},
        headers={"X-Game-Project-ID": "test_project_alpha"},
    )

    assert response.status_code == 201
    systems = response.json()["gameplay_systems"]
    assert systems["content"]["economy"] == ["Credits are earned from contracts and spent on ship repairs."]
    assert systems["content"]["platforms_controls"] == ["Target platform: Windows PC. Keyboard, mouse, and controller input are required."]
    assert systems["content"]["accessibility"] == ["Include subtitles, remappable controls, and color blind safe objective markers."]
    assert systems["content"]["technical_constraints"] == ["Maintain 60 FPS on the target device and support offline saves."]
    assert any("gameplay loop" in warning for warning in systems["warnings"])


def test_blueprint_extracts_explicit_must_should_could_scope_without_reprioritizing(db_session):
    """MVP scope must preserve the GDD's own categories rather than inventing a roadmap."""
    rag = RAGService()
    document = rag.process_document(
        db=db_session,
        file_name=f"scope_{uuid.uuid4().hex[:6]}.md",
        file_bytes=(
            b"# Production scope\n"
            b"## Must-have, should-have, could-have\n"
            b"### Must-have\n- One polished story level\n- Scripted companion dialogue\n"
            b"### Should-have\n- Polished story level\n- Weekly challenge mode\n"
            b"### Could-have\n- Optional VR challenge\n"
        ),
        content_type="text/markdown",
        game_project_id="test_project_alpha",
    )

    response = client.post(
        "/api/v1/blueprints/generate",
        json={"document_id": str(document.id)},
        headers={"X-Game-Project-ID": "test_project_alpha"},
    )

    assert response.status_code == 201
    systems = response.json()["gameplay_systems"]
    assert systems["content"]["mvp_scope"] == {
        "must_have": ["One polished story level", "Scripted companion dialogue"],
        "should_have": ["Weekly challenge mode"],
        "could_have": ["Optional VR challenge"],
    }
    assert systems["citations"]
