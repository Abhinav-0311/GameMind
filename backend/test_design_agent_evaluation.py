import uuid
import copy

from fastapi.testclient import TestClient

from app.api.v1.design_agent import get_design_agent_service
from app.design_agent.contracts import CritiqueOutput
from app.design_agent.evaluation import build_scorecard
from app.design_agent.provider import MockDesignAgentProvider, ProviderResult
from app.design_agent.schemas import DesignAgentEvaluationCreate
from app.models.design_agent import DesignAgentEvaluation
from app.models.document import Document, DocumentChunk
from main import app
from test_design_agent_workflow import CountingRAG, make_service


client = TestClient(app)


class CyberRakshakEvaluationProvider(MockDesignAgentProvider):
    """Deterministic quality fixture with an intentional first-draft defect."""

    level_titles = [
        "Training Sandbox",
        "Password Vault",
        "Phishing Office",
        "Malware Warehouse",
        "Firewall Fortress",
        "QR Market",
        "Social Engineering Plaza",
        "Ransomware Ruins",
        "The Reveal",
        "Hunt Jay",
    ]

    def generate(self, plan, evidence):
        result = super().generate(plan, evidence)
        content = copy.deepcopy(result.content)
        content["level_design_suggestions"]["content"]["levels"] = [
            {"number": 1, "title": "Training Sandbox"},
            {"number": 9, "title": "The Reveal"},
        ]
        content["level_design_suggestions"]["warnings"] = [
            "The final Hunt Jay level is missing from the first draft."
        ]
        return ProviderResult(
            content=content,
            model_name=result.model_name,
            usage=result.usage,
            provider_name=result.provider_name,
        )

    def critique(self, artifact, evidence):
        levels = artifact["level_design_suggestions"]["content"].get("levels", [])
        complete = len(levels) == 10 and levels[-1]["title"] == "Hunt Jay"
        critique = CritiqueOutput(
            verdict="ready_for_review" if complete else "needs_revision",
            findings=[
                {
                    "severity": "low" if complete else "high",
                    "section": "level_design_suggestions",
                    "issue": (
                        "The revised artifact preserves all ten named levels."
                        if complete
                        else "The level plan omits Level 10: Hunt Jay."
                    ),
                    "recommendation": (
                        "Confirm the complete level order before approval."
                        if complete
                        else "Restore all ten levels from Training Sandbox through Hunt Jay."
                    ),
                }
            ],
            summary=(
                "The requested level correction is present."
                if complete
                else "The first draft has incomplete level coverage."
            ),
        )
        return ProviderResult(
            content=critique.model_dump(),
            model_name=self.model_name,
            usage=self._usage(artifact, evidence),
            provider_name=self.name,
        )

    def revise(self, artifact, evidence, rejection_reason):
        result = super().revise(artifact, evidence, rejection_reason)
        content = copy.deepcopy(result.content)
        content["level_design_suggestions"]["content"]["levels"] = [
            {"number": index, "title": title}
            for index, title in enumerate(self.level_titles, start=1)
        ]
        content["level_design_suggestions"]["warnings"] = []
        return ProviderResult(
            content=content,
            model_name=result.model_name,
            usage=result.usage,
            provider_name=result.provider_name,
        )


def create_cyberrakshak_source(
    db_session,
    game_project_id: str,
) -> tuple[Document, list[DocumentChunk]]:
    document = Document(
        title="CyberRakshak: The Ethical Hacker",
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
                "CyberRakshak is a story-driven low-poly 3D platformer. "
                "The player controls Adi, a cybersecurity intern guided by Jay "
                "and the PATCH companion through ethical hacking simulations."
            ),
        ),
        DocumentChunk(
            document_id=document.id,
            chunk_index=1,
            content=(
                "The story has ten levels. Level 9, The Reveal, exposes Jay's "
                "betrayal. Level 10, Hunt Jay, combines threats while Adi works "
                "with cyber police to expose him."
            ),
        ),
        DocumentChunk(
            document_id=document.id,
            chunk_index=2,
            content=(
                "PATCH provides hints, warnings, mission reactions, and short "
                "cybersecurity explanations. PATCH should be funny and helpful "
                "rather than teacher-like."
            ),
        ),
        DocumentChunk(
            document_id=document.id,
            chunk_index=3,
            content=(
                "The core loop is enter a mission, choose stealth, bold, puzzle, "
                "or speed, retrieve evidence, expose the vulnerability, escape, "
                "receive a rating, and unlock the next mission."
            ),
        ),
    ]
    db_session.add_all(chunks)
    db_session.commit()
    db_session.refresh(document)
    return document, chunks


def test_scorecard_thresholds_fail_honestly():
    payload = DesignAgentEvaluationCreate(
        citation_judgments=[
            {
                "section": "summary",
                "chunk_id": uuid.uuid4(),
                "relevant": False,
            },
        ],
        claim_judgments=[
            {"claim": "An unsupported claim.", "supported": False},
        ],
        critique_judgments=[
            {"finding_index": 0, "useful": False},
        ],
        revision_judgments=[
            {
                "requirement": "Correct the level plan.",
                "applied": False,
                "unrelated_regression": True,
            },
        ],
    )

    metrics, overall, passed = build_scorecard(payload, approval_persisted=False)

    assert overall == 0
    assert passed is False
    assert all(metric["passed"] is False for metric in metrics)
    assert metrics[1]["key"] == "unsupported_claim_rate"
    assert metrics[1]["value"] == 1


def test_cyberrakshak_end_to_end_scorecard_persists_after_restart(db_session):
    project_id = f"cyberrakshak_eval_{uuid.uuid4().hex[:8]}"
    document, chunks = create_cyberrakshak_source(db_session, project_id)
    rag = CountingRAG(chunks)
    provider = CyberRakshakEvaluationProvider()
    first_service = make_service(db_session, rag, provider=provider)
    app.dependency_overrides[get_design_agent_service] = lambda: first_service

    try:
        started = client.post(
            "/api/v1/design-agent/runs",
            headers={"X-Game-Project-ID": project_id},
            json={
                "objective": (
                    "Create a cited CyberRakshak blueprint and verify the complete "
                    "ten-level story progression."
                ),
                "document_ids": [str(document.id)],
                "max_revisions": 2,
            },
        )
        assert started.status_code == 201, started.text
        run_id = started.json()["id"]

        rejected = client.post(
            f"/api/v1/design-agent/runs/{run_id}/review",
            headers={"X-Game-Project-ID": project_id},
            json={
                "decision": "reject",
                "reason": (
                    "The level section must explicitly preserve all ten levels, "
                    "including Level 9 The Reveal and Level 10 Hunt Jay."
                ),
            },
        )
        assert rejected.status_code == 200, rejected.text
        assert rejected.json()["status"] == "awaiting_review"
        assert rejected.json()["revision_count"] == 1
        assert rag.calls == 1

        restarted_service = make_service(db_session, rag, provider=provider)
        app.dependency_overrides[get_design_agent_service] = lambda: restarted_service
        approved = client.post(
            f"/api/v1/design-agent/runs/{run_id}/review",
            headers={"X-Game-Project-ID": project_id},
            json={"decision": "approve"},
        )
        assert approved.status_code == 200, approved.text
        completed = approved.json()
        assert completed["status"] == "completed"
        assert completed["current_artifact"]["immutable"] is True
        assert rag.calls == 1
        levels = completed["current_artifact"]["content"][
            "level_design_suggestions"
        ]["content"]["levels"]
        assert len(levels) == 10
        assert levels[8]["title"] == "The Reveal"
        assert levels[9]["title"] == "Hunt Jay"

        cited_pairs = sorted(
            (section_name, chunk_id)
            for section_name, section in completed["current_artifact"]["content"].items()
            for chunk_id in section["citations"]
        )
        findings = completed["critique"]["content"]["findings"]
        evaluation_payload = {
            "rubric_version": "cyberrakshak-v1",
            "citation_judgments": [
                {
                    "section": section_name,
                    "chunk_id": chunk_id,
                    "relevant": True,
                    "note": "The cited chunk directly supports the reviewed section.",
                }
                for section_name, chunk_id in cited_pairs
            ],
            "claim_judgments": [
                {
                    "claim": "CyberRakshak is a story-driven low-poly 3D platformer.",
                    "supported": True,
                },
                {
                    "claim": "Adi is guided by Jay and PATCH.",
                    "supported": True,
                },
                {
                    "claim": "The story progression contains ten levels.",
                    "supported": True,
                },
            ],
            "critique_judgments": [
                {
                    "finding_index": index,
                    "useful": True,
                    "note": "The finding identifies a concrete human confirmation gap.",
                }
                for index in range(len(findings))
            ],
            "revision_judgments": [
                {
                    "requirement": (
                        "Preserve all ten levels, including The Reveal and Hunt Jay."
                    ),
                    "applied": True,
                    "unrelated_regression": False,
                }
            ],
        }
        evaluated = client.post(
            f"/api/v1/design-agent/runs/{run_id}/evaluation",
            headers={"X-Game-Project-ID": project_id},
            json=evaluation_payload,
        )
        assert evaluated.status_code == 201, evaluated.text
        scorecard = evaluated.json()
        assert scorecard["passed"] is True
        assert scorecard["overall_score"] == 1
        assert [metric["key"] for metric in scorecard["metrics"]] == [
            "citation_relevance",
            "unsupported_claim_rate",
            "critique_usefulness",
            "revision_correctness",
            "approval_persistence",
        ]
        assert all(metric["passed"] for metric in scorecard["metrics"])
        assert scorecard["metrics"][-1]["source"] == "system_verified"

        db_session.expire_all()
        reloaded = client.get(
            f"/api/v1/design-agent/runs/{run_id}/evaluation",
            headers={"X-Game-Project-ID": project_id},
        )
        assert reloaded.status_code == 200
        assert reloaded.json() == scorecard
        assert db_session.query(DesignAgentEvaluation).filter(
            DesignAgentEvaluation.run_id == uuid.UUID(run_id)
        ).count() == 1

        duplicate = client.post(
            f"/api/v1/design-agent/runs/{run_id}/evaluation",
            headers={"X-Game-Project-ID": project_id},
            json=evaluation_payload,
        )
        assert duplicate.status_code == 409

        cross_project = client.get(
            f"/api/v1/design-agent/runs/{run_id}/evaluation",
            headers={"X-Game-Project-ID": f"other_{project_id}"},
        )
        assert cross_project.status_code == 404
    finally:
        app.dependency_overrides.pop(get_design_agent_service, None)
