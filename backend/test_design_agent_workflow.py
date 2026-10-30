import json
import uuid

import httpx
import pytest

from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.api.v1.design_agent import get_design_agent_service
from app.config import settings
from app.design_agent.llm_provider import NODE_MODEL_CONFIG, NvidiaProvider
from app.design_agent.nvidia_provider import (
    NvidiaDesignAgentProvider,
    ResilientDesignAgentProvider,
)
from app.design_agent.provider import MockDesignAgentProvider
from app.design_agent.service import DesignAgentService
from app.design_agent.workflow import DesignAgentWorkflow
from app.models.blueprint import GameBlueprint
from app.models.design_agent import (
    DesignAgentArtifact,
    DesignAgentCritique,
    DesignAgentEvidenceSnapshot,
    DesignAgentJob,
    DesignAgentNodeExecution,
    DesignAgentReviewEvent,
    DesignAgentRun,
)
from app.models.document import Document, DocumentChunk
from app.models.design_decision import DesignDecision
from main import app

client = TestClient(app)


@pytest.mark.parametrize("mode", ["inline", "queued"])
def test_failed_critique_retries_exact_checkpoint_without_regeneration(db_session, monkeypatch, mode):
    import copy
    from app.design_agent.jobs import DesignAgentJobService
    from app.design_agent.llm_provider import NvidiaProviderError

    class RecoverableProvider(MockDesignAgentProvider):
        name = "nvidia"
        fail = True
        plans = generations = critiques = 0

        def plan(self, *args):
            self.plans += 1
            return super().plan(*args)

        def generate(self, *args):
            self.generations += 1
            return super().generate(*args)

        def critique(self, *args, **kwargs):
            self.critiques += 1
            if self.fail:
                raise NvidiaProviderError("Critique unavailable", code="provider_unavailable", attempts=3)
            return super().critique(*args, **kwargs)

    project = f"critique_recovery_{uuid.uuid4().hex[:8]}"
    document, chunks = create_source(db_session, project)
    rag, provider = CountingRAG(chunks), RecoverableProvider()
    service = make_service(db_session, rag, provider)
    app.dependency_overrides[get_design_agent_service] = lambda: service
    headers = {"X-Game-Project-ID": project}
    try:
        monkeypatch.setattr(settings, "DESIGN_AGENT_EXECUTION_MODE", "inline")
        started = client.post("/api/v1/design-agent/runs", headers=headers, json={
            "objective": "Create a cited reviewable design.", "document_ids": [str(document.id)],
            "hosted_provider_consent": True})
        assert started.status_code == 503
        run_id = started.json()["detail"]["run_id"]
        saved = client.get(f"/api/v1/design-agent/runs/{run_id}", headers=headers).json()
        artifact = copy.deepcopy(saved["current_artifact"])
        snapshot = db_session.query(DesignAgentEvidenceSnapshot).filter_by(run_id=uuid.UUID(run_id)).one()
        frozen = copy.deepcopy(snapshot.items)
        failed = db_session.query(DesignAgentNodeExecution).filter_by(run_id=uuid.UUID(run_id), node_name="critique").one()
        original_failure = failed.id
        body = {"artifact_id": artifact["id"], "failed_execution_id": str(failed.id), "hosted_provider_consent": True}
        url = f"/api/v1/design-agent/runs/{run_id}/retry-critique"
        assert client.post(url, headers=headers, json={**body, "hosted_provider_consent": False}).status_code == 409
        assert client.post(url, headers={"X-Game-Project-ID": "other-project"}, json=body).status_code == 404
        assert client.post(url, headers=headers, json={**body, "artifact_id": str(uuid.uuid4())}).status_code == 409
        assert client.post(url, headers=headers, json={**body, "failed_execution_id": str(uuid.uuid4())}).status_code == 409
        assert provider.critiques == 1
        active = DesignAgentJob(run_id=uuid.UUID(run_id), game_project_id=project, operation="start",
            idempotency_key=f"original:{run_id}", status="running", locked_by="original-worker")
        db_session.add(active)
        db_session.commit()
        assert client.post(url, headers=headers, json=body).status_code == 409
        assert provider.critiques == 1
        db_session.delete(active)
        db_session.commit()
        monkeypatch.setattr(settings, "DESIGN_AGENT_EXECUTION_MODE", mode)
        jobs = DesignAgentJobService(service.workflow.session_factory, workflow_factory=lambda _: service.workflow)
        for succeeds in (False, True):
            provider.fail = not succeeds
            executions = client.get(f"/api/v1/design-agent/runs/{run_id}/trace", headers=headers).json()["items"]
            body["failed_execution_id"] = next(item["id"] for item in reversed(executions) if item["node_name"] == "critique")
            response = client.post(url, headers=headers, json=body)
            if mode == "queued":
                assert response.status_code == 200 and response.json()["status"] == "review_queued"
                assert client.post(url, headers=headers, json=body).status_code == 409
                db_session.rollback()  # The shared test session outlives normal HTTP dependency cleanup.
                queued = db_session.query(DesignAgentJob).filter_by(idempotency_key=f"critique:{run_id}:{body['failed_execution_id']}").one()
                queued.status, queued.locked_by = "running", "current-owner"
                db_session.commit()
                prior_calls = provider.critiques
                with pytest.raises(ValueError):
                    service.workflow.retry_critique(uuid.UUID(run_id), uuid.UUID(artifact["id"]),
                        uuid.UUID(body["failed_execution_id"]), queued.id, "stale-owner")
                assert provider.critiques == prior_calls
                queued.status, queued.locked_by = "pending", None
                db_session.commit()
                assert jobs.process_one("recovery-test")
                assert not jobs.process_one("recovery-test"), "Failed critique recovery must not silently requeue"
            else:
                assert response.status_code == (200 if succeeds else 503), response.text
            # Even a replay arriving after failure cannot spend another attempt.
            assert client.post(url, headers=headers, json=body).status_code == 409
            current = client.get(f"/api/v1/design-agent/runs/{run_id}", headers=headers).json()
            assert current["status"] == ("awaiting_review" if succeeds else "failed")
            assert current["current_artifact"] == artifact and current["revision_count"] == 0
        db_session.expire_all()
        assert (provider.plans, provider.generations, provider.critiques, rag.calls) == (1, 1, 3, 1)
        assert db_session.query(DesignAgentArtifact).filter_by(run_id=uuid.UUID(run_id)).count() == 1
        assert db_session.query(DesignAgentEvidenceSnapshot).filter_by(run_id=uuid.UUID(run_id)).one().items == frozen
        assert db_session.query(DesignAgentCritique).filter_by(run_id=uuid.UUID(run_id)).count() == 1
        assert db_session.get(DesignAgentNodeExecution, original_failure).status == "failed"
        assert db_session.query(DesignAgentReviewEvent).filter_by(run_id=uuid.UUID(run_id)).count() == 0
    finally:
        app.dependency_overrides.pop(get_design_agent_service, None)


@pytest.mark.parametrize("changed", ["artifact", "evidence", "provider", "queued_provider"])
def test_critique_retry_rejects_changed_frozen_data_before_provider(db_session, monkeypatch, changed):
    import copy
    from app.design_agent.llm_provider import NvidiaProviderError
    project = f"critique_binding_{uuid.uuid4().hex[:8]}"
    document, chunks = create_source(db_session, project)
    provider = MockDesignAgentProvider()
    calls = []

    def unavailable(*args, **kwargs):
        calls.append(True)
        raise NvidiaProviderError("Unavailable", code="provider_unavailable")

    monkeypatch.setattr(provider, "critique", unavailable)
    monkeypatch.setattr(settings, "DESIGN_AGENT_EXECUTION_MODE", "inline")
    service = make_service(db_session, CountingRAG(chunks), provider)
    app.dependency_overrides[get_design_agent_service] = lambda: service
    headers = {"X-Game-Project-ID": project}
    try:
        failed = client.post("/api/v1/design-agent/runs", headers=headers, json={
            "objective": "Create a cited reviewable design.", "document_ids": [str(document.id)]})
        run_id = uuid.UUID(failed.json()["detail"]["run_id"])
        artifact = db_session.query(DesignAgentArtifact).filter_by(run_id=run_id).one()
        snapshot = db_session.query(DesignAgentEvidenceSnapshot).filter_by(run_id=run_id).one()
        execution = db_session.query(DesignAgentNodeExecution).filter_by(run_id=run_id, node_name="critique").one()
        if changed == "artifact":
            altered = copy.deepcopy(artifact.content)
            altered["summary"]["warnings"].append("Changed after checkpoint")
            artifact.content = altered
        elif changed == "evidence":
            altered = copy.deepcopy(snapshot.items)
            altered[0]["content"] = "Changed after checkpoint"
            snapshot.items = altered
        elif changed == "provider":
            provider.name = "nvidia"
        db_session.commit()
        if changed == "queued_provider":
            monkeypatch.setattr(settings, "DESIGN_AGENT_EXECUTION_MODE", "queued")
        response = client.post(f"/api/v1/design-agent/runs/{run_id}/retry-critique", headers=headers,
            json={"artifact_id": str(artifact.id), "failed_execution_id": str(execution.id)})
        if changed == "queued_provider":
            assert response.status_code == 200
            provider.name = "nvidia"
            from app.design_agent.jobs import DesignAgentJobService
            worker = DesignAgentJobService(service.workflow.session_factory, workflow_factory=lambda _: service.workflow)
            assert worker.process_one("changed-provider")
        else:
            assert response.status_code == (409 if changed == "provider" else 503)
        assert calls == [True], "A stale checkpoint must fail locally, never invoke critique again"
        db_session.expire_all()
        assert db_session.get(DesignAgentRun, run_id).status == "failed"
        assert db_session.query(DesignAgentCritique).filter_by(run_id=run_id).count() == 0
    finally:
        app.dependency_overrides.pop(get_design_agent_service, None)


class CountingRAG:
    def __init__(self, chunks: list[DocumentChunk]):
        self.chunks = chunks
        self.calls = 0
        self.requests = []

    def query_lore(
        self,
        query_text: str,
        limit: int = 5,
        game_project_id: str = "default_project",
        document_ids: list[str] | None = None,
    ) -> list[dict]:
        self.calls += 1
        self.requests.append(
            {
                "query_text": query_text,
                "limit": limit,
                "game_project_id": game_project_id,
                "document_ids": document_ids,
            }
        )
        allowed = set(document_ids or [])
        return [
            {
                "chunk_id": str(chunk.id),
                "content": chunk.content,
                "document_id": str(chunk.document_id),
                "title": chunk.document.title,
                "chunk_index": chunk.chunk_index,
                "similarity": 0.91,
                "confidence": "High",
            }
            for chunk in self.chunks
            if not allowed or str(chunk.document_id) in allowed
        ][:limit]

    def query_lore_sections(
        self,
        section_queries: dict[str, str],
        limit_per_section: int = 3,
        game_project_id: str = "default_project",
        document_ids: list[str] | None = None,
    ) -> list[dict]:
        self.calls += 1
        self.requests.append(
            {
                "section_queries": section_queries,
                "limit_per_section": limit_per_section,
                "game_project_id": game_project_id,
                "document_ids": document_ids,
            }
        )
        allowed = set(document_ids or [])
        return [
            {
                "chunk_id": str(chunk.id),
                "content": chunk.content,
                "document_id": str(chunk.document_id),
                "title": chunk.document.title,
                "chunk_index": chunk.chunk_index,
                "game_project_id": game_project_id,
                "similarity": 0.91,
                "confidence": "High",
                "matched_sections": list(section_queries),
                "section_similarities": {
                    section_name: 0.91 for section_name in section_queries
                },
            }
            for chunk in self.chunks
            if not allowed or str(chunk.document_id) in allowed
        ]


class PlanCapturingMockProvider(MockDesignAgentProvider):
    def __init__(self):
        super().__init__()
        self.generation_plans: list[dict] = []

    def generate(self, plan: dict, evidence: list[dict]):
        self.generation_plans.append(plan)
        return super().generate(plan, evidence)


class IncompleteNvidiaProvider(MockDesignAgentProvider):
    name = "nvidia"

    def generate(self, plan: dict, evidence: list[dict]):
        result = super().generate(plan, evidence)
        content = result.content
        if not content["npc_archetypes"]["content"]["npcs"]:
            content["npc_archetypes"]["content"]["npcs"] = [{
                "name": "Mira",
                "archetype": "Scout mentor",
                "dialogue_style": "Brief and practical.",
                "source_chunk_ids": [evidence[0]["chunk_id"]],
                "dialogue_hooks": [],
                "relationship_notes": [],
                "implementation_notes": [],
                "assumptions": [],
            }]
        for npc in content["npc_archetypes"]["content"]["npcs"]:
            npc["dialogue_hooks"] = []
        return result


def create_source(db_session, game_project_id: str) -> tuple[Document, list[DocumentChunk]]:
    document = Document(
        title="Reference Game Design Document.md",
        content_type="text/markdown",
        source_kind="gdd",
        game_project_id=game_project_id,
    )
    db_session.add(document)
    db_session.flush()
    chunks = [
        DocumentChunk(
            document_id=document.id,
            chunk_index=0,
            content=(
                "The player defends a digital city through nine security missions. "
                "Level progression introduces reconnaissance, phishing defense, and incident response. "
                "Mira is the player's scout mentor."
            ),
        ),
        DocumentChunk(
            document_id=document.id,
            chunk_index=1,
            content=(
                "Mentor NPCs explain evidence-backed cybersecurity choices. "
                "Quest outcomes change trust and unlock the final investigation."
            ),
        ),
    ]
    db_session.add_all(chunks)
    db_session.commit()
    db_session.refresh(document)
    return document, chunks


def make_service(
    db_session,
    rag: CountingRAG,
    provider=None,
) -> DesignAgentService:
    factory = sessionmaker(
        bind=db_session.get_bind(),
        autocommit=False,
        autoflush=False,
    )
    return DesignAgentService(
        DesignAgentWorkflow(
            database_url=settings.DATABASE_URL,
            session_factory=factory,
            provider=provider or MockDesignAgentProvider(),
            rag_service=rag,
        )
    )


def start_run(service: DesignAgentService, document_id: uuid.UUID, game_project_id: str, max_revisions: int = 2):
    app.dependency_overrides[get_design_agent_service] = lambda: service
    response = client.post(
        "/api/v1/design-agent/runs",
        headers={"X-Game-Project-ID": game_project_id},
        json={
            "objective": "Generate a cited, reviewable game design blueprint.",
            "document_ids": [str(document_id)],
            "max_revisions": max_revisions,
            "hosted_provider_consent": True,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.parametrize("initialization_failure", [False, True])
def test_failed_start_returns_saved_scoped_run_without_restarting(db_session, monkeypatch, initialization_failure):
    from app.design_agent.llm_provider import NvidiaProviderError

    class FailingPlanner(MockDesignAgentProvider):
        name = "nvidia"
        calls = 0

        def plan(self, objective, document_ids):
            self.calls += 1
            raise NvidiaProviderError("Planner unavailable", code="provider_timeout", attempts=3)

    project_id = f"failed_start_{uuid.uuid4().hex[:8]}"
    document, chunks = create_source(db_session, project_id)
    provider = FailingPlanner()
    service = make_service(db_session, CountingRAG(chunks), provider)
    if initialization_failure:
        def fail_start(_run):
            raise RuntimeError("private failure")
        monkeypatch.setattr(service.workflow, "start", fail_start)
    app.dependency_overrides[get_design_agent_service] = lambda: service
    headers = {"X-Game-Project-ID": project_id}
    try:
        response = client.post("/api/v1/design-agent/runs", headers=headers, json={
            "objective": "Create a source-backed small design slice.",
            "document_ids": [str(document.id)], "hosted_provider_consent": True,
        })
        assert response.status_code == 503
        detail = response.json()["detail"]
        assert isinstance(detail, dict), "Failure must identify the persisted run"
        assert "private failure" not in response.text
        run_id = detail["run_id"]
        saved = client.get(f"/api/v1/design-agent/runs/{run_id}", headers=headers)
        assert saved.status_code == 200
        assert saved.json()["status"] == "failed"
        assert saved.json()["current_artifact"] is None
        assert saved.json()["critique"] is None
        assert len(client.get("/api/v1/design-agent/runs", headers=headers).json()) == 1
        assert client.get(f"/api/v1/design-agent/runs/{run_id}", headers={"X-Game-Project-ID": "other-project"}).status_code == 404
        trace = client.get(f"/api/v1/design-agent/runs/{run_id}/trace", headers=headers).json()
        if not initialization_failure:
            assert trace["items"][0]["details"]["token_usage_scope"] == "unavailable"
        assert provider.calls == (0 if initialization_failure else 1)
    finally:
        app.dependency_overrides.pop(get_design_agent_service, None)


@pytest.mark.parametrize("recovered", [False, True])
def test_normal_review_api_persists_compact_dialogue_revision_and_recritiques(db_session, recovered):
    """Real durable flow with a fake hosted transport, not a separate feature."""
    from app.design_agent.llm_provider import CompletionResult

    class DialogueFixtureProvider(MockDesignAgentProvider):
        name = "nvidia"

        def __init__(self):
            self.revision_calls = 0
            self.critique_calls = 0

        def generate(self, plan, evidence):
            result = super().generate(plan, evidence)
            result.content["npc_archetypes"]["content"]["npcs"] = [{
                "name": "Mira", "archetype": "Mentor", "dialogue_style": "Brief warnings",
                "source_chunk_ids": [evidence[0]["chunk_id"]], "dialogue_hooks": ["Stay alert."],
            }]
            return result

        def complete(self, request):
            self.revision_calls += 1
            assert request.response_model.__name__ == "NPCDialogueRevisionOutput"
            content = request.response_model.model_validate({
                "npc_archetypes": {"patches": [{
                    "name": "Mira", "source_chunk_ids": [str(chunks[0].id)], "assumptions": [],
                    "dialogue_triggers": [{
                        "trigger": "threat_encounter", "situation": "Player approaches a threat",
                        "text": "Read the evidence before making your move.",
                        "repeat_policy": "Once per threat encounter; reset after leaving the encounter.",
                    }],
                }]},
            }).model_dump()
            if recovered:
                from test_design_agent_llm_provider import _completion
                with httpx.Client(transport=httpx.MockTransport(
                    lambda _: _completion(json.dumps(content)[:-1]),
                )) as transport:
                    return NvidiaProvider(
                        base_url="https://example.invalid/v1", timeout_seconds=1,
                        repair_enabled=False, client=transport, key_reader=lambda _: "test-only",
                    ).complete(request)
            return CompletionResult(content=content, provider_name="nvidia", model_name="fixture")

        def revise(self, artifact, evidence, rejection_reason, target_sections=None, *, review_request=None):
            return NvidiaDesignAgentProvider(llm_provider=self).revise(
                artifact, evidence, rejection_reason, target_sections, review_request=review_request)

        def critique(self, artifact, evidence, *, review_request=None):
            self.critique_calls += 1
            return super().critique(artifact, evidence, review_request=review_request)

    project_id = f"dialogue_review_{uuid.uuid4().hex[:8]}"
    document, chunks = create_source(db_session, project_id)
    rag = CountingRAG(chunks)
    provider = DialogueFixtureProvider()
    service = make_service(db_session, rag, provider=provider)
    try:
        run = start_run(service, document.id, project_id)
        assert run["draft_evaluation"]["artifact_id"] == run["current_artifact"]["id"]
        response = client.post(
            f"/api/v1/design-agent/runs/{run['id']}/review",
            headers={"X-Game-Project-ID": project_id},
            json={"decision": "reject", "reason": "Improve Mira's dialogue for threat encounters.",
                  "target_sections": ["npc_archetypes"]},
        )
        assert response.status_code == 200, response.text
        revised = response.json()
        assert revised["status"] == "awaiting_review" and revised["revision_count"] == 1
        assert revised["draft_evaluation"]["artifact_id"] == revised["current_artifact"]["id"]
        assert revised["draft_evaluation"]["artifact_id"] != run["draft_evaluation"]["artifact_id"]
        assert provider.revision_calls == 1 and provider.critique_calls == 2
        assert rag.calls == 1
        after = revised["current_artifact"]["content"]
        before = run["current_artifact"]["content"]
        assert all(after[key] == before[key] for key in before if key != "npc_archetypes")
        npc = after["npc_archetypes"]["content"]["npcs"][0]
        assert any("trigger mappings" in item for item in npc["assumptions"])
        assert any("Manual check:" in note for note in npc["implementation_notes"])
        assert npc["dialogue_triggers"][0]["text"] in npc["dialogue_triggers"][0]["manual_test"]
        if recovered:
            assert any("closing-delimiter recovery" in warning for warning in after["npc_archetypes"]["warnings"])
            assert any("closing-delimiter recovery" in item for item in npc["assumptions"])
            trace = client.get(
                f"/api/v1/design-agent/runs/{run['id']}/trace",
                headers={"X-Game-Project-ID": project_id},
            )
            assert trace.status_code == 200, trace.text
            revision = next(item for item in trace.json()["items"] if item["node_name"] == "revise")
            assert revision["details"]["local_recovery"] is True
            assert revision["details"]["recovery_requires_review"] is True
            assert revision["details"]["repair_attempts"] == 0
        assert db_session.query(DesignAgentEvidenceSnapshot).filter_by(run_id=uuid.UUID(run["id"])).count() == 1
        assert db_session.query(DesignAgentArtifact).filter_by(run_id=uuid.UUID(run["id"])).count() == 2
        assert db_session.query(GameBlueprint).filter_by(game_project_id=project_id).count() == 0
        approval = client.post(
            f"/api/v1/design-agent/runs/{run['id']}/review",
            headers={"X-Game-Project-ID": project_id}, json={"decision": "approve"},
        )
        assert approval.status_code == 409, approval.text
    finally:
        app.dependency_overrides.pop(get_design_agent_service, None)


def test_planner_section_queries_reach_scoped_retrieval_and_trace(db_session):
    from app.design_agent.contracts import BLUEPRINT_SECTION_KEYS
    from app.design_agent.llm_provider import CompletionResult

    queries = {section: f"reference evidence for {section}" for section in BLUEPRINT_SECTION_KEYS}
    queries["npc_archetypes"] = "Mira mentor dialogue voice"

    class PlannerTransport:
        def complete(self, request):
            return CompletionResult(
                content=request.response_model.model_validate({
                    "retrieval_query": "reference game design",
                    "section_queries": queries,
                }).model_dump(),
                provider_name="nvidia", model_name="fake-planner",
            )

    class PlannedMockProvider(MockDesignAgentProvider):
        def plan(self, objective, document_ids):
            return NvidiaDesignAgentProvider(llm_provider=PlannerTransport()).plan(objective, document_ids)

    project_id = f"planned_retrieval_{uuid.uuid4().hex[:8]}"
    document, chunks = create_source(db_session, project_id)
    rag = CountingRAG(chunks)
    service = make_service(db_session, rag, provider=PlannedMockProvider())
    try:
        run = start_run(service, document.id, project_id)
        assert rag.requests == [{
            "section_queries": queries, "limit_per_section": 3,
            "game_project_id": project_id, "document_ids": [str(document.id)],
        }]
        trace = client.get(
            f"/api/v1/design-agent/runs/{run['id']}/trace",
            headers={"X-Game-Project-ID": project_id},
        )
        assert trace.status_code == 200
        planning = next(item for item in trace.json()["items"] if item["node_name"] == "plan")
        assert planning["details"]["section_query_source"] == "planner"
    finally:
        app.dependency_overrides.pop(get_design_agent_service, None)


def test_run_pauses_with_durable_checkpoint_and_trace(db_session):
    project_id = f"agent_trace_{uuid.uuid4().hex[:8]}"
    document, chunks = create_source(db_session, project_id)
    rag = CountingRAG(chunks)
    service = make_service(db_session, rag)

    try:
        run = start_run(service, document.id, project_id)
        assert run["status"] == "awaiting_review"
        assert run["current_node"] == "human_review"
        assert run["retrieval_revision"] == 1
        assert run["current_artifact"]["artifact_type"] == "draft"
        assert run["critique"]["content"]["findings"]
        assert rag.calls == 1

        trace_response = client.get(
            f"/api/v1/design-agent/runs/{run['id']}/trace",
            headers={"X-Game-Project-ID": project_id},
        )
        assert trace_response.status_code == 200
        trace = trace_response.json()["items"]
        assert [item["node_name"] for item in trace[:5]] == [
            "plan",
            "retrieve_evidence",
            "generate_blueprint",
            "critique",
            "human_review",
        ]
        assert trace[-1]["status"] == "waiting"
        assert all(item["cost_usd"] == 0 for item in trace)

        checkpoint_count = db_session.execute(
            __import__("sqlalchemy").text(
                "SELECT COUNT(*) FROM checkpoints WHERE thread_id = :thread_id"
            ),
            {"thread_id": f"design-agent:{run['id']}"},
        ).scalar()
        assert checkpoint_count > 0
    finally:
        app.dependency_overrides.pop(get_design_agent_service, None)


def test_nvidia_run_requires_explicit_consent_before_workflow_starts(db_session):
    project_id = f"agent_consent_{uuid.uuid4().hex[:8]}"
    document, chunks = create_source(db_session, project_id)
    service = make_service(db_session, CountingRAG(chunks), provider=IncompleteNvidiaProvider())
    app.dependency_overrides[get_design_agent_service] = lambda: service

    try:
        response = client.post(
            "/api/v1/design-agent/runs",
            headers={"X-Game-Project-ID": project_id},
            json={
                "objective": "Generate a cited, reviewable game design blueprint.",
                "document_ids": [str(document.id)],
            },
        )
        assert response.status_code == 409
        assert "Explicit consent" in response.json()["detail"]
        assert db_session.query(DesignAgentRun).filter(DesignAgentRun.game_project_id == project_id).count() == 0
    finally:
        app.dependency_overrides.pop(get_design_agent_service, None)


def test_resolved_selected_decisions_are_passed_to_generation_and_traced(db_session):
    project_id = f"agent_decisions_{uuid.uuid4().hex[:8]}"
    document, chunks = create_source(db_session, project_id)
    selected_decision = DesignDecision(
        game_project_id=project_id,
        document_id=document.id,
        category="mvp_scope",
        title="MVP scope",
        decision="Ship the tutorial before the open-world expansion.",
        status="resolved",
    )
    other_document, _ = create_source(db_session, project_id)
    unselected_decision = DesignDecision(
        game_project_id=project_id,
        document_id=other_document.id,
        category="unselected_scope",
        title="Unselected scope",
        decision="This must not influence the selected GDD run.",
        status="resolved",
    )
    db_session.add_all([selected_decision, unselected_decision])
    db_session.commit()
    rag = CountingRAG(chunks)
    provider = PlanCapturingMockProvider()
    service = make_service(db_session, rag, provider)

    try:
        run = start_run(service, document.id, project_id)
        assert provider.generation_plans[0]["resolved_decisions"] == [
            {
                "decision_id": str(selected_decision.id),
                "document_id": str(document.id),
                "title": "MVP scope",
                "guidance": None,
                "decision": "Ship the tutorial before the open-world expansion.",
            }
        ]
        trace = client.get(
            f"/api/v1/design-agent/runs/{run['id']}/trace",
            headers={"X-Game-Project-ID": project_id},
        ).json()["items"]
        retrieval = next(item for item in trace if item["node_name"] == "retrieve_evidence")
        assert retrieval["details"]["resolved_decision_count"] == 1
        assert retrieval["details"]["resolved_decision_ids"] == [str(selected_decision.id)]
    finally:
        app.dependency_overrides.pop(get_design_agent_service, None)


@pytest.mark.parametrize("contract_version", [1, 2])
def test_frozen_resolved_decision_survives_critique_and_rejection(db_session, contract_version):
    import copy
    from app.design_agent.provider import ProviderResult
    from app.design_agent.review_policy import saved_review_request
    from test_design_contract_v2 import governed_artifact
    from test_nvidia_design_agent_provider import BlueprintCapturingProvider

    project_id = f"decision_review_{uuid.uuid4().hex[:8]}"
    document, chunks = create_source(db_session, project_id)
    rule = "Save only at checkpoints."
    assert all(rule not in chunk.content for chunk in chunks)
    decision = DesignDecision(game_project_id=project_id, document_id=document.id,
        category="save_policy", title="Save policy", status="resolved", decision=rule)
    db_session.add(decision)
    db_session.commit()
    frozen = [{"decision_id": str(decision.id), "document_id": str(document.id),
               "title": "Save policy", "guidance": None, "decision": rule}]
    content = governed_artifact()
    for section in content.values():
        section["citations"] = [str(chunks[0].id)]
        for key in ("npcs", "quests"):
            for record in section["content"].get(key, []):
                record["source_chunk_ids"] = [str(chunks[0].id)]
    content["gameplay_systems"]["content"]["systems"].append({"name": "Saving", "description": rule})
    revised = copy.deepcopy(content)
    revised["gameplay_systems"]["content"]["systems"][0]["description"] = "Clear the guards, then raise the flag."
    wire = {"verdict": "ready_for_review", "summary": "Controlled offline critique.", "findings": [],
            "review_mode": "defect_detection", "source_coverage": {key: "covered" for key in content}}

    class ReviewCompletions(BlueprintCapturingProvider):
        def complete(self, request):
            self.content = revised if request.node_name == "revise" else wire
            return super().complete(request)

    class ReviewProvider(NvidiaDesignAgentProvider):
        def configuration(self):
            return {**super().configuration(), "design_contract_version": contract_version}

        def plan(self, *args):
            return MockDesignAgentProvider().plan(*args)

        def generate(self, plan, evidence):
            assert plan["resolved_decisions"] == frozen
            return ProviderResult(content=copy.deepcopy(content), model_name="offline-fixture", provider_name=self.name)

    completions = ReviewCompletions(wire)
    rag = CountingRAG(chunks)
    service = make_service(db_session, rag, ReviewProvider(llm_provider=completions))
    try:
        run = start_run(service, document.id, project_id)
        # Editing the live decision must not replace the run's frozen direction.
        decision.decision = "Allow saving anywhere."
        db_session.commit()
        response = client.post(f"/api/v1/design-agent/runs/{run['id']}/review",
            headers={"X-Game-Project-ID": project_id}, json={"decision": "reject",
                "reason": "Clarify the training gameplay sequence.", "target_sections": ["gameplay_systems"]})
        assert response.status_code == 200, response.text
        after = response.json()
        assert after["status"] == "awaiting_review" and after["revision_count"] == 1
        assert after["current_artifact"]["content"]["gameplay_systems"]["content"]["systems"][1] == {
            "name": "Saving", "description": rule}
        assert [request.node_name for request in completions.requests] == ["critique", "revise", "critique"]
        for request in completions.requests:
            prompt = request.messages[1]["content"]
            human = json.loads(prompt.split("Human request (requirements, not source facts): ", 1)[1].split("\n", 1)[0])
            assert human.get("resolved_decisions") == frozen, request.node_name
            if request.node_name == "critique":
                assert "absence from the GDD alone is not an unsupported-rule defect" in prompt
        for review in (run["critique"], after["critique"]):
            assert not any(item["section"] == "gameplay_systems" and "unsupported" in item["issue"].lower()
                           for item in review["content"]["findings"])
        db_session.expire_all()
        saved = db_session.get(DesignAgentRun, uuid.UUID(run["id"]))
        assert saved_review_request(saved)["resolved_decisions"] == frozen
        assert rag.calls == 1
    finally:
        app.dependency_overrides.pop(get_design_agent_service, None)


def test_incomplete_nvidia_draft_reaches_review_but_cannot_be_approved(db_session):
    from app.design_agent.provider import ProviderResult

    class OverlookingCritic(IncompleteNvidiaProvider):
        def generate(self, plan, evidence):
            result = super().generate(plan, evidence)
            result.content["gameplay_systems"]["content"] = {}
            return result

        def critique(self, artifact, evidence, *, review_request=None):
            return ProviderResult(content={"verdict": "ready_for_review", "findings": [],
                                           "summary": "Model overlooked missing content."},
                                  provider_name=self.name, model_name="local-critique-fixture")

    project_id = f"agent_incomplete_{uuid.uuid4().hex[:8]}"
    document, chunks = create_source(db_session, project_id)
    service = make_service(db_session, CountingRAG(chunks), OverlookingCritic())

    try:
        run = start_run(service, document.id, project_id)
        assert run["status"] == "awaiting_review"
        assert run["critique"] is not None
        review = run["critique"]["content"]
        assert review["verdict"] == "needs_revision"
        assert "gameplay_systems" in review["quality_scorecard"]["incomplete_sections"]
        assert any(item["section"] == "gameplay_systems" and item["severity"] == "high"
                   for item in review["findings"])

        approval = client.post(
            f"/api/v1/design-agent/runs/{run['id']}/review",
            headers={"X-Game-Project-ID": project_id},
            json={"decision": "approve"},
        )
        assert approval.status_code == 409
        assert "needs revision before approval" in approval.json()["detail"]
        assert db_session.query(GameBlueprint).filter(
            GameBlueprint.game_project_id == project_id
        ).count() == 0
    finally:
        app.dependency_overrides.pop(get_design_agent_service, None)


def test_nvidia_critique_verdict_blocks_approval_before_structural_finalization(db_session):
    project_id = f"agent_critique_gate_{uuid.uuid4().hex[:8]}"
    document, chunks = create_source(db_session, project_id)
    service = make_service(db_session, CountingRAG(chunks), IncompleteNvidiaProvider())

    try:
        run = start_run(service, document.id, project_id)
        critique = db_session.query(DesignAgentCritique).filter(
            DesignAgentCritique.run_id == uuid.UUID(run["id"])
        ).one()
        critique.content = {
            **critique.content,
            "verdict": "needs_revision",
            "quality_scorecard": {"passed": True, "blockers": []},
        }
        db_session.commit()

        approval = client.post(
            f"/api/v1/design-agent/runs/{run['id']}/review",
            headers={"X-Game-Project-ID": project_id},
            json={"decision": "approve"},
        )

        assert approval.status_code == 409
        assert "Independent critique must be resolved" in approval.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_design_agent_service, None)


def test_rejection_reuses_evidence_and_restart_resume_completes(db_session, monkeypatch):
    project_id = f"agent_resume_{uuid.uuid4().hex[:8]}"
    document, chunks = create_source(db_session, project_id)
    db_session.add(DesignDecision(document_id=document.id, game_project_id=project_id,
        category="controls", title="Recorded control choice", status="resolved", decision="Keyboard controls"))
    db_session.commit()
    rag = CountingRAG(chunks)
    first_service = make_service(db_session, rag)

    try:
        run = start_run(first_service, document.id, project_id)
        run_id = run["id"]
        first_snapshot_id = db_session.query(DesignAgentEvidenceSnapshot.id).filter(
            DesignAgentEvidenceSnapshot.run_id == uuid.UUID(run_id)
        ).scalar()

        rejection = client.post(
            f"/api/v1/design-agent/runs/{run_id}/review",
            headers={"X-Game-Project-ID": project_id},
            json={
                "decision": "reject",
                "reason": "Add Level 10: Incident Response.",
                "target_sections": ["level_design_suggestions"],
            },
        )
        assert rejection.status_code == 200, rejection.text
        revised = rejection.json()
        assert revised["status"] == "awaiting_review"
        assert revised["revision_count"] == 1
        assert revised["current_artifact"]["artifact_type"] == "revision"
        assert revised["current_artifact"]["content"]["level_design_suggestions"][
            "content"
        ]["review_adjustments"] == [
            "Add Level 10: Incident Response."
        ]
        assert (
            revised["current_artifact"]["content"]["level_design_suggestions"]
            != run["current_artifact"]["content"]["level_design_suggestions"]
        )
        assert rag.calls == 1
        assert db_session.query(DesignAgentEvidenceSnapshot).filter(
            DesignAgentEvidenceSnapshot.run_id == uuid.UUID(run_id)
        ).count() == 1
        assert db_session.query(DesignAgentEvidenceSnapshot.id).filter(
            DesignAgentEvidenceSnapshot.run_id == uuid.UUID(run_id)
        ).scalar() == first_snapshot_id

        # A new workflow/service object simulates an application restart. It has
        # no in-memory graph state and must resume from PostgreSQL.
        restarted_service = make_service(db_session, rag)
        app.dependency_overrides[get_design_agent_service] = lambda: restarted_service
        approval = client.post(
            f"/api/v1/design-agent/runs/{run_id}/review",
            headers={"X-Game-Project-ID": project_id},
            json={"decision": "approve"},
        )
        assert approval.status_code == 200, approval.text
        completed = approval.json()
        assert completed["status"] == "completed"
        assert completed["current_artifact"]["artifact_type"] == "final"
        assert completed["current_artifact"]["immutable"] is True
        assert completed["current_artifact"]["blueprint_id"]
        assert rag.calls == 1

        blueprint = db_session.query(GameBlueprint).filter(
            GameBlueprint.id == uuid.UUID(completed["current_artifact"]["blueprint_id"])
        ).one()
        assert blueprint.status == "approved"

        brief = client.get(
            f"/api/v1/design-agent/runs/{run_id}/exports/technical-brief",
            headers={"X-Game-Project-ID": project_id},
        )
        assert brief.status_code == 200
        assert "# Agent Blueprint:" in brief.text
        assert "## Sources" in brief.text
        assert "Recorded control choice" in brief.text and "Keyboard controls" in brief.text

        monkeypatch.setattr("app.services.design_decision_service.DesignDecisionService.coverage",
                            lambda *args: {"items": [{"title": "Unapproved live change",
                                "decision": "Add a new delivery prerequisite", "evidence_status": "resolved"}]})
        document.title = "Renamed after approval"
        db_session.commit()
        repeated = client.get(f"/api/v1/design-agent/runs/{run_id}/exports/technical-brief",
                              headers={"X-Game-Project-ID": project_id})
        assert repeated.status_code == 200, repeated.text
        assert "Unapproved live change" not in repeated.text
        assert repeated.text == brief.text
        assert "## Frozen evidence" in repeated.text
        assert completed["current_artifact"]["id"] in repeated.text
        assert str(first_snapshot_id) in repeated.text

        frozen_summary = blueprint.summary
        blueprint.summary = {"content": {"description": "Unapproved blueprint rewrite"}}
        blueprint.unity_runtime_preview = {"content": {"generation_mode": "unapproved rewrite"}}
        db_session.commit()
        drifted = client.get(f"/api/v1/design-agent/runs/{run_id}/exports/technical-brief",
                             headers={"X-Game-Project-ID": project_id})
        assert drifted.status_code == 200, drifted.text
        assert frozen_summary["content"]["description"] in drifted.text
        assert "Unapproved blueprint rewrite" not in drifted.text

        runtime = client.get(
            f"/api/v1/design-agent/runs/{run_id}/exports/runtime",
            headers={"X-Game-Project-ID": project_id},
        )
        assert runtime.status_code == 200
        assert runtime.json()["runtime_data"]["generation_mode"] == "mock"

        duplicate_review = client.post(
            f"/api/v1/design-agent/runs/{run_id}/review",
            headers={"X-Game-Project-ID": project_id},
            json={"decision": "approve"},
        )
        assert duplicate_review.status_code == 409
        assert db_session.query(DesignAgentArtifact).filter(
            DesignAgentArtifact.run_id == uuid.UUID(run_id),
            DesignAgentArtifact.artifact_type == "final",
        ).count() == 1
        assert db_session.query(DesignAgentReviewEvent).filter(
            DesignAgentReviewEvent.run_id == uuid.UUID(run_id)
        ).count() == 2
        from types import SimpleNamespace
        monkeypatch.setattr(restarted_service, "_final_blueprint", lambda *_: (
            db_session.get(DesignAgentRun, uuid.UUID(run_id)), blueprint,
            SimpleNamespace(evidence_snapshot_id=uuid.uuid4())))
        missing = client.get(f"/api/v1/design-agent/runs/{run_id}/exports/technical-brief",
                             headers={"X-Game-Project-ID": project_id})
        assert missing.status_code == 409 and "frozen evidence" in missing.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_design_agent_service, None)


@pytest.mark.parametrize("execution_mode", ["inline", "queued"])
@pytest.mark.parametrize("revision_count,max_revisions", [(1, 1), (2, 2), (3, 2)])
def test_exhausted_revision_budget_rejects_without_mutation(
    db_session, monkeypatch, execution_mode, revision_count, max_revisions,
):
    project_id = f"agent_budget_{uuid.uuid4().hex[:8]}"
    document, chunks = create_source(db_session, project_id)
    rag = CountingRAG(chunks)
    service = make_service(db_session, rag)
    try:
        monkeypatch.setattr(settings, "DESIGN_AGENT_EXECUTION_MODE", "inline")
        started = start_run(service, document.id, project_id, max_revisions=max_revisions)
        run_id = uuid.UUID(started["id"])
        for index in range(max_revisions):
            revised = client.post(
                f"/api/v1/design-agent/runs/{run_id}/review",
                headers={"X-Game-Project-ID": project_id},
                json={"decision": "reject", "reason": f"Add Level {10 + index}: Incident Response.",
                      "target_sections": ["level_design_suggestions"]},
            )
            assert revised.status_code == 200, revised.text
            assert revised.json()["revision_count"] == index + 1
        db_session.expire_all()
        run = db_session.get(DesignAgentRun, run_id)
        run.revision_count = revision_count
        run.max_revisions = max_revisions
        db_session.commit()
        models = [DesignAgentArtifact, DesignAgentEvidenceSnapshot, DesignAgentReviewEvent,
                  DesignAgentNodeExecution, DesignAgentJob]
        before = [db_session.query(model).filter_by(run_id=run_id).count() for model in models]
        monkeypatch.setattr(settings, "DESIGN_AGENT_EXECUTION_MODE", execution_mode)
        for _ in range(2):
            response = client.post(
                f"/api/v1/design-agent/runs/{run_id}/review",
                headers={"X-Game-Project-ID": project_id},
                json={"decision": "reject", "reason": "Improve the level plan.",
                      "target_sections": ["level_design_suggestions"]},
            )
            assert response.status_code == 409, response.text
            assert "revision budget is exhausted" in response.json()["detail"]
        db_session.expire_all()
        run = db_session.get(DesignAgentRun, run_id)
        assert run.status == "awaiting_review"
        assert run.revision_count == revision_count
        assert [db_session.query(model).filter_by(run_id=run_id).count() for model in models] == before
        assert rag.calls == 1
    finally:
        app.dependency_overrides.pop(get_design_agent_service, None)


def test_exhausted_review_allows_separately_queued_fresh_run(db_session, monkeypatch):
    project_id = f"agent_fresh_{uuid.uuid4().hex[:8]}"
    document, chunks = create_source(db_session, project_id)
    service = make_service(db_session, CountingRAG(chunks))
    try:
        monkeypatch.setattr(settings, "DESIGN_AGENT_EXECUTION_MODE", "inline")
        started = start_run(service, document.id, project_id)
        old_id = uuid.UUID(started["id"])
        old_run = db_session.get(DesignAgentRun, old_id)
        old_run.revision_count = old_run.max_revisions
        db_session.commit()
        monkeypatch.setattr(settings, "DESIGN_AGENT_EXECUTION_MODE", "queued")
        hosted_service = make_service(db_session, CountingRAG(chunks), IncompleteNvidiaProvider())
        app.dependency_overrides[get_design_agent_service] = lambda: hosted_service
        missing_consent = client.post(
            "/api/v1/design-agent/runs", headers={"X-Game-Project-ID": project_id},
            json={"objective": "Create a separately consented fresh draft.",
                  "document_ids": [str(document.id)], "hosted_provider_consent": False},
        )
        assert missing_consent.status_code == 409
        assert "Explicit consent" in missing_consent.json()["detail"]
        assert db_session.query(DesignAgentRun).filter_by(game_project_id=project_id).count() == 1
        fresh = start_run(hosted_service, document.id, project_id)
        assert fresh["id"] != started["id"]
        assert fresh["status"] == "queued"
        assert fresh["revision_count"] == 0
        assert db_session.get(DesignAgentRun, uuid.UUID(fresh["id"])).model_config["hosted_provider_consent"] is True
        db_session.expire_all()
        assert db_session.get(DesignAgentRun, old_id).status == "awaiting_review"
        assert db_session.query(DesignAgentArtifact).filter_by(run_id=old_id).count() == 1
        assert db_session.query(DesignAgentJob).filter_by(run_id=old_id).count() == 0
        assert db_session.query(DesignAgentJob).filter_by(run_id=uuid.UUID(fresh["id"])).count() == 1
    finally:
        app.dependency_overrides.pop(get_design_agent_service, None)


def test_exhausted_budget_does_not_block_valid_approval(db_session, monkeypatch):
    project_id = f"agent_approve_budget_{uuid.uuid4().hex[:8]}"
    document, chunks = create_source(db_session, project_id)
    service = make_service(db_session, CountingRAG(chunks))
    try:
        monkeypatch.setattr(settings, "DESIGN_AGENT_EXECUTION_MODE", "inline")
        started = start_run(service, document.id, project_id)
        run = db_session.get(DesignAgentRun, uuid.UUID(started["id"]))
        run.revision_count = run.max_revisions
        db_session.commit()
        response = client.post(
            f"/api/v1/design-agent/runs/{run.id}/review",
            headers={"X-Game-Project-ID": project_id}, json={"decision": "approve"},
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "completed"
    finally:
        app.dependency_overrides.pop(get_design_agent_service, None)


def test_run_is_project_scoped_and_rejection_requires_reason(db_session):
    project_id = f"agent_scope_{uuid.uuid4().hex[:8]}"
    other_project_id = f"agent_other_{uuid.uuid4().hex[:8]}"
    document, chunks = create_source(db_session, project_id)
    service = make_service(db_session, CountingRAG(chunks))

    try:
        run = start_run(service, document.id, project_id)
        cross_project = client.get(
            f"/api/v1/design-agent/runs/{run['id']}",
            headers={"X-Game-Project-ID": other_project_id},
        )
        assert cross_project.status_code == 404

        invalid_rejection = client.post(
            f"/api/v1/design-agent/runs/{run['id']}/review",
            headers={"X-Game-Project-ID": project_id},
            json={"decision": "reject", "reason": "   "},
        )
        assert invalid_rejection.status_code == 422

        export_before_approval = client.get(
            f"/api/v1/design-agent/runs/{run['id']}/exports/runtime",
            headers={"X-Game-Project-ID": project_id},
        )
        assert export_before_approval.status_code == 409
    finally:
        app.dependency_overrides.pop(get_design_agent_service, None)


def test_unavailable_nvidia_fallback_is_visible_in_run_and_trace(db_session):
    project_id = f"agent_fallback_{uuid.uuid4().hex[:8]}"
    document, chunks = create_source(db_session, project_id)
    provider = ResilientDesignAgentProvider(
        primary=NvidiaDesignAgentProvider(
            llm_provider=NvidiaProvider(
                base_url="https://integrate.api.nvidia.com/v1",
                timeout_seconds=1,
                retry_backoff_seconds=0,
                repair_enabled=True,
                key_reader=lambda _name: None,
                sleep=lambda _seconds: None,
            )
        ),
        fallback=MockDesignAgentProvider(),
    )
    service = make_service(db_session, CountingRAG(chunks), provider=provider)

    try:
        run = start_run(service, document.id, project_id)

        assert run["status"] == "awaiting_review"
        assert run["provider_name"] == "nvidia"
        assert run["degraded"] is True
        assert run["critique"]["provider_name"] == "mock"
        persisted_run = db_session.query(DesignAgentRun).filter(
            DesignAgentRun.id == uuid.UUID(run["id"])
        ).one()
        assert (
            persisted_run.model_config["models"]["plan"]["model"]
                == NODE_MODEL_CONFIG["plan"].model
        )
        assert "api_key" not in persisted_run.model_config

        trace_response = client.get(
            f"/api/v1/design-agent/runs/{run['id']}/trace",
            headers={"X-Game-Project-ID": project_id},
        )
        assert trace_response.status_code == 200
        provider_nodes = [
            item
            for item in trace_response.json()["items"]
            if item["node_name"] in {"plan", "generate_blueprint", "critique"}
        ]
        assert len(provider_nodes) == 3
        assert all(item["status"] == "degraded" for item in provider_nodes)
        assert all(item["provider_name"] == "mock" for item in provider_nodes)
        assert all(item["details"]["fallback_from"] == "nvidia" for item in provider_nodes)
        assert all(item["details"]["failure_code"] == "api_key_missing" for item in provider_nodes)
        assert all("primary_latency_ms" in item["details"] for item in provider_nodes)
        assert all(
            item["latency_ms"] >= item["details"]["primary_latency_ms"]
            for item in provider_nodes
        )
    finally:
        app.dependency_overrides.pop(get_design_agent_service, None)
