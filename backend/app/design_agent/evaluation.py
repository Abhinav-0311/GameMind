from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.design_agent.schemas import (
    DesignAgentEvaluationCreate,
    DesignAgentEvaluationMetric,
    DesignAgentEvaluationResponse,
)
from app.models.design_agent import (
    DesignAgentArtifact,
    DesignAgentCritique,
    DesignAgentEvaluation,
    DesignAgentEvidenceSnapshot,
    DesignAgentReviewEvent,
    DesignAgentRun,
    checkpoints,
)
from app.models.user import User


METRIC_LABELS = {
    "citation_relevance": "Citation relevance",
    "unsupported_claim_rate": "Unsupported-claim rate",
    "critique_usefulness": "Critique usefulness",
    "revision_correctness": "Revision correctness",
    "approval_persistence": "Approval persistence",
}


def _metric(
    key: str,
    numerator: int,
    denominator: int,
    target: str,
    passed: bool,
    source: str,
) -> dict[str, Any]:
    return {
        "key": key,
        "label": METRIC_LABELS[key],
        "value": round(numerator / denominator, 4),
        "numerator": numerator,
        "denominator": denominator,
        "target": target,
        "passed": passed,
        "source": source,
    }


def build_scorecard(
    payload: DesignAgentEvaluationCreate,
    approval_persisted: bool,
) -> tuple[list[dict[str, Any]], float, bool]:
    relevant = sum(item.relevant for item in payload.citation_judgments)
    unsupported = sum(not item.supported for item in payload.claim_judgments)
    useful = sum(item.useful for item in payload.critique_judgments)
    correct_revisions = sum(
        item.applied and not item.unrelated_regression
        for item in payload.revision_judgments
    )

    citation_total = len(payload.citation_judgments)
    claim_total = len(payload.claim_judgments)
    critique_total = len(payload.critique_judgments)
    revision_total = len(payload.revision_judgments)
    citation_score = relevant / citation_total
    unsupported_rate = unsupported / claim_total
    critique_score = useful / critique_total
    revision_score = correct_revisions / revision_total
    approval_score = 1.0 if approval_persisted else 0.0

    metrics = [
        _metric(
            "citation_relevance",
            relevant,
            citation_total,
            ">= 0.80",
            citation_score >= 0.80,
            "human_review",
        ),
        _metric(
            "unsupported_claim_rate",
            unsupported,
            claim_total,
            "<= 0.10",
            unsupported_rate <= 0.10,
            "human_review",
        ),
        _metric(
            "critique_usefulness",
            useful,
            critique_total,
            ">= 0.75",
            critique_score >= 0.75,
            "human_review",
        ),
        _metric(
            "revision_correctness",
            correct_revisions,
            revision_total,
            "1.00",
            revision_score == 1.0,
            "human_review",
        ),
        _metric(
            "approval_persistence",
            1 if approval_persisted else 0,
            1,
            "1.00",
            approval_persisted,
            "system_verified",
        ),
    ]
    overall_score = round(
        (
            citation_score
            + (1.0 - unsupported_rate)
            + critique_score
            + revision_score
            + approval_score
        )
        / 5,
        4,
    )
    return metrics, overall_score, all(metric["passed"] for metric in metrics)


class DesignAgentEvaluationService:
    @staticmethod
    def _run(db: Session, run_id: UUID, game_project_id: str) -> DesignAgentRun:
        run = db.query(DesignAgentRun).filter(
            DesignAgentRun.id == run_id,
            DesignAgentRun.game_project_id == game_project_id,
        ).first()
        if run is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Design-agent run not found in the active workspace.",
            )
        return run

    @staticmethod
    def _response(evaluation: DesignAgentEvaluation) -> DesignAgentEvaluationResponse:
        return DesignAgentEvaluationResponse(
            id=evaluation.id,
            run_id=evaluation.run_id,
            game_project_id=evaluation.game_project_id,
            rubric_version=evaluation.rubric_version,
            evaluator_label=evaluation.evaluator_label,
            metrics=[
                DesignAgentEvaluationMetric.model_validate(metric)
                for metric in evaluation.metrics
            ],
            overall_score=float(evaluation.overall_score),
            passed=evaluation.passed,
            created_at=evaluation.created_at,
        )

    def get(
        self,
        db: Session,
        run_id: UUID,
        game_project_id: str,
    ) -> DesignAgentEvaluationResponse:
        self._run(db, run_id, game_project_id)
        evaluation = db.query(DesignAgentEvaluation).filter(
            DesignAgentEvaluation.run_id == run_id,
            DesignAgentEvaluation.game_project_id == game_project_id,
        ).first()
        if evaluation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No quality scorecard has been recorded for this run.",
            )
        return self._response(evaluation)

    def create(
        self,
        db: Session,
        run_id: UUID,
        game_project_id: str,
        payload: DesignAgentEvaluationCreate,
        current_user: User | None,
    ) -> DesignAgentEvaluationResponse:
        run = self._run(db, run_id, game_project_id)
        if run.status != "completed":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A quality scorecard can only be recorded for a completed run.",
            )
        if db.query(DesignAgentEvaluation.id).filter(
            DesignAgentEvaluation.run_id == run_id
        ).first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This run already has an immutable quality scorecard.",
            )

        final_artifact = db.query(DesignAgentArtifact).filter(
            DesignAgentArtifact.run_id == run_id,
            DesignAgentArtifact.game_project_id == game_project_id,
            DesignAgentArtifact.artifact_type == "final",
            DesignAgentArtifact.immutable.is_(True),
        ).one_or_none()
        if final_artifact is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The completed run does not have one immutable final artifact.",
            )

        snapshot = db.query(DesignAgentEvidenceSnapshot).filter(
            DesignAgentEvidenceSnapshot.id == final_artifact.evidence_snapshot_id,
            DesignAgentEvidenceSnapshot.game_project_id == game_project_id,
        ).one()
        evidence_ids = {
            str(item.get("chunk_id"))
            for item in snapshot.items
            if item.get("chunk_id")
        }
        cited_pairs = {
            (section_name, str(chunk_id))
            for section_name, section in final_artifact.content.items()
            for chunk_id in section.get("citations", [])
        }
        cited_ids = {chunk_id for _, chunk_id in cited_pairs}
        judged_citations = [
            (item.section, str(item.chunk_id))
            for item in payload.citation_judgments
        ]
        if len(judged_citations) != len(set(judged_citations)):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Each section-citation pair must be judged exactly once.",
            )
        if not cited_pairs or set(judged_citations) != cited_pairs:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Citation judgments must cover every section-citation pair in the final artifact exactly once.",
            )
        if not cited_ids.issubset(evidence_ids):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The final artifact cites chunks outside its frozen evidence snapshot.",
            )

        critique = db.query(DesignAgentCritique).filter(
            DesignAgentCritique.run_id == run_id,
            DesignAgentCritique.game_project_id == game_project_id,
        ).order_by(DesignAgentCritique.created_at.desc()).first()
        findings = (critique.content if critique else {}).get("findings", [])
        judged_findings = [item.finding_index for item in payload.critique_judgments]
        if len(judged_findings) != len(set(judged_findings)):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Each critique finding must be judged exactly once.",
            )
        if not findings or set(judged_findings) != set(range(len(findings))):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Critique judgments must cover every finding from the latest critique exactly once.",
            )

        review_events = db.query(DesignAgentReviewEvent).filter(
            DesignAgentReviewEvent.run_id == run_id,
            DesignAgentReviewEvent.game_project_id == game_project_id,
        ).all()
        has_rejection = any(event.decision == "reject" for event in review_events)
        has_approval = any(event.decision == "approve" for event in review_events)
        if run.revision_count < 1 or not has_rejection:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Revision correctness requires a run with at least one rejected artifact and revision.",
            )

        checkpoint_count = db.execute(
            select(func.count())
            .select_from(checkpoints)
            .where(checkpoints.c.thread_id == f"design-agent:{run.id}")
        ).scalar_one()
        approval_persisted = bool(
            run.status == "completed"
            and run.completed_at
            and has_approval
            and final_artifact.blueprint_id
            and final_artifact.immutable
            and checkpoint_count > 0
        )
        metrics, overall_score, passed = build_scorecard(
            payload,
            approval_persisted,
        )
        evaluation = DesignAgentEvaluation(
            run_id=run.id,
            evaluator_user_id=current_user.id if current_user else None,
            evaluator_label=current_user.email if current_user else "local_developer",
            rubric_version=payload.rubric_version,
            annotations=payload.model_dump(mode="json"),
            metrics=metrics,
            overall_score=overall_score,
            passed=passed,
            game_project_id=game_project_id,
        )
        db.add(evaluation)
        db.commit()
        db.refresh(evaluation)
        return self._response(evaluation)
