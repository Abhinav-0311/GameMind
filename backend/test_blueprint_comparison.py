import uuid

from fastapi.testclient import TestClient

from app.models.blueprint import GameBlueprint
from main import app


client = TestClient(app)


def _section(content):
    return {"content": content, "citations": [], "confidence": "High", "warnings": []}


def _blueprint(project_id, title, summary):
    return GameBlueprint(
        id=uuid.uuid4(), title=title, game_project_id=project_id,
        summary=_section(summary), narrative_direction=_section({}), art_style_direction=_section({}),
        npc_archetypes=_section({"npcs": []}), npc_memory_design=_section({"memory_nodes": []}),
        level_design_suggestions=_section({}), gameplay_systems=_section({}), quest_hooks=_section({"quests": []}),
        unity_runtime_preview=_section({}), status="draft",
    )


def test_blueprint_comparison_returns_only_changed_sections(db_session):
    project_id = f"comparison_{uuid.uuid4().hex[:8]}"
    base = _blueprint(project_id, "Base", {"title": "Original"})
    revised = _blueprint(project_id, "Revised", {"title": "Revised"})
    db_session.add_all([base, revised])
    db_session.commit()

    response = client.get(f"/api/v1/blueprints/{base.id}/compare/{revised.id}", headers={"X-Game-Project-ID": project_id})

    assert response.status_code == 200
    assert response.json()["changed_sections"] == [
        {"section": "Game summary", "status": "changed", "before_warnings": 0, "after_warnings": 0}
    ]
