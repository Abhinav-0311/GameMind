"""A syntactically valid empty blueprint is not a successful JSON repair."""
import json

import pytest

from app.design_agent.contracts import BLUEPRINT_SECTION_KEYS, BlueprintContent
from app.design_agent.grounding import assess_artifact_quality
from app.design_agent.llm_provider import NvidiaStructuredOutputError
from test_json_closer_recovery import invoke
from test_revision_completeness_guards import complete_artifact


def empty_blueprint():
    content = complete_artifact()
    for section in BLUEPRINT_SECTION_KEYS:
        content[section] = {"content": {}, "citations": [], "confidence": "Low", "warnings": ["Human input required"]}
    content["npc_archetypes"]["content"] = {"npcs": []}
    content["quest_hooks"]["content"] = {"quests": []}
    return content


def test_a_repair_cannot_succeed_by_discarding_all_design_content():
    with pytest.raises(NvidiaStructuredOutputError) as caught:
        invoke('{"summary":', model=BlueprintContent, repair=True,
               repaired_raw=json.dumps(empty_blueprint()))
    assert caught.value.attempts == 2
    assert caught.value.code == "structured_output_invalid"
    assert "private-source-never-log" not in json.dumps(caught.value.diagnostics)


def test_a_real_content_bearing_schema_repair_still_succeeds():
    original = complete_artifact()
    original["summary"]["confidence"] = "invalid-confidence"
    result, requests = invoke(json.dumps(original), model=BlueprintContent, repair=True,
                              repaired_raw=json.dumps(complete_artifact()))
    assert len(requests) == 2
    assert result.content == complete_artifact()
    assert result.metadata["repair_attempts"] == 1


def test_empty_design_gets_no_positive_contradiction_or_overall_quality_score():
    score = assess_artifact_quality(empty_blueprint())
    assert score["overall_score"] == 0.0
    assert next(item for item in score["metrics"] if item["key"] == "consistency")["value"] == 0.0
    assert score["passed"] is False


@pytest.mark.parametrize("repair_kind", ["empty", "discarded_quests"])
def test_normal_workflow_rejects_destructive_repair_without_persisting_a_draft(db_session, repair_kind):
    """Exercise the normal API/checkpoint boundary with no network calls."""
    import uuid

    import httpx

    from app.api.v1.design_agent import get_design_agent_service
    from app.design_agent.llm_provider import NvidiaProvider
    from app.design_agent.nvidia_provider import NvidiaDesignAgentProvider
    from app.design_agent.provider import MockDesignAgentProvider
    from app.models.blueprint import GameBlueprint
    from app.models.design_agent import (
        DesignAgentArtifact, DesignAgentCritique, DesignAgentEvidenceSnapshot,
        DesignAgentRun,
    )
    from main import app
    from test_design_agent_llm_provider import _completion
    from test_design_agent_workflow import CountingRAG, client, create_source, make_service

    project_id = f"empty_repair_{uuid.uuid4().hex[:8]}"
    document, chunks = create_source(db_session, project_id)
    original = complete_artifact(source_id=str(chunks[0].id))
    repaired = json.loads(json.dumps(original))
    original["summary"]["confidence"] = "invalid-confidence"
    repaired["quest_hooks"]["content"]["quests"] = []
    calls = []

    def handler(request):
        calls.append(request)
        if repair_kind == "empty":
            return _completion('{"summary":' if len(calls) == 1 else json.dumps(empty_blueprint()))
        return _completion(json.dumps(original if len(calls) == 1 else repaired))

    class RepairFixtureProvider(MockDesignAgentProvider):
        name = "nvidia"
        critique_calls = 0

        def generate(self, plan, evidence):
            with httpx.Client(transport=httpx.MockTransport(handler)) as transport:
                provider = NvidiaProvider(
                    base_url="https://example.invalid/v1", timeout_seconds=1,
                    repair_enabled=True, client=transport,
                    key_reader=lambda _: "credential-never-log", sleep=lambda _: None,
                )
                return NvidiaDesignAgentProvider(llm_provider=provider).generate(plan, evidence)

        def critique(self, artifact, evidence, *, review_request=None):
            self.critique_calls += 1
            return super().critique(artifact, evidence, review_request=review_request)

    provider = RepairFixtureProvider()
    service = make_service(db_session, CountingRAG(chunks), provider)
    headers = {"X-Game-Project-ID": project_id}
    app.dependency_overrides[get_design_agent_service] = lambda: service
    try:
        response = client.post("/api/v1/design-agent/runs", headers=headers, json={
            "objective": "Generate a cited, reviewable design.",
            "document_ids": [str(document.id)], "hosted_provider_consent": True,
        })
        assert response.status_code == 502, response.text
        run = db_session.query(DesignAgentRun).filter_by(game_project_id=project_id).one()
        assert run.status == "failed" and run.current_node == "generate_blueprint"
        assert len(calls) == 2 and provider.critique_calls == 0
        assert db_session.query(DesignAgentArtifact).filter_by(run_id=run.id).count() == 0
        assert db_session.query(DesignAgentCritique).filter_by(run_id=run.id).count() == 0
        assert db_session.query(DesignAgentEvidenceSnapshot).filter_by(run_id=run.id).count() == 1
        assert db_session.query(GameBlueprint).filter_by(game_project_id=project_id).count() == 0
        trace = client.get(f"/api/v1/design-agent/runs/{run.id}/trace", headers=headers)
        assert trace.status_code == 200, trace.text
        execution = next(item for item in trace.json()["items"] if item["node_name"] == "generate_blueprint")
        assert execution["status"] == "failed"
        assert execution["details"]["failure_code"] == "structured_output_invalid"
        assert execution["details"]["request_attempts"] == 2
        assert "credential-never-log" not in json.dumps(trace.json())
        export = client.get(f"/api/v1/design-agent/runs/{run.id}/exports/runtime", headers=headers)
        assert export.status_code == 409, export.text
    finally:
        app.dependency_overrides.pop(get_design_agent_service, None)
