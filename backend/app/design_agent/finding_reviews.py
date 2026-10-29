"""Evidence-linked human finding disputes. No provider, graph or approval effects."""
import copy
import hashlib
import json
import re
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.orm import Session

from app.design_agent.schemas import (
    DesignAgentFindingResolutionCreate, DesignAgentFindingResolutionResponse,
    DesignAgentFindingReviewResponse,
)
from app.models.design_agent import (
    DesignAgentArtifact, DesignAgentCritique, DesignAgentEvidenceSnapshot,
    DesignAgentFindingResolution, DesignAgentRun,
)
from app.models.user import ProjectMembership, User


def content_digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def _artifact_value(content, path: str):
    value = content
    for part in path.split("/")[1:]:
        if re.search(r"~(?![01])", part):
            raise HTTPException(422, "Invalid artifact JSON pointer escape.")
        key = part.replace("~1", "/").replace("~0", "~")
        if isinstance(value, dict) and key in value:
            value = value[key]
        elif isinstance(value, list) and re.fullmatch(r"0|[1-9][0-9]*", key) and int(key) < len(value):
            value = value[int(key)]
        else:
            raise HTTPException(422, "The artifact path does not identify an existing draft field.")
    return copy.deepcopy(value)


def _finding_artifact_value(content, finding, path: str):
    value = _artifact_value(content, path)
    reference = finding.get("reference")
    if reference is not None and (
        not isinstance(reference, dict) or reference.get("artifact_path") != path
        or "artifact_value" not in reference or content_digest(value) != content_digest(reference["artifact_value"])
    ):
        raise HTTPException(422, "Review exactly the current draft field referenced by this finding.")
    return value


class DesignFindingReviewService:
    @staticmethod
    def _load(db: Session, run_id: UUID, artifact_id: UUID, project: str, *, write=False):
        query = db.query(DesignAgentRun).filter_by(id=run_id, game_project_id=project)
        run = (query.with_for_update() if write else query).first()
        artifact = db.query(DesignAgentArtifact).filter_by(id=artifact_id, run_id=run_id, game_project_id=project).first()
        if run is None or artifact is None:
            raise HTTPException(404, "Draft not found in the active workspace.")
        if write:
            latest = db.query(DesignAgentArtifact).filter_by(run_id=run_id, game_project_id=project).order_by(DesignAgentArtifact.version.desc()).first()
            if run.status != "awaiting_review" or latest.id != artifact.id or artifact.immutable or artifact.artifact_type == "final":
                raise HTTPException(409, "Record finding reviews only against the current unapproved draft at its review checkpoint.")
        critique = db.query(DesignAgentCritique).filter_by(run_id=run_id, artifact_id=artifact_id, game_project_id=project).order_by(
            DesignAgentCritique.created_at.desc(), DesignAgentCritique.id.desc()).first()
        snapshot = db.query(DesignAgentEvidenceSnapshot).filter_by(
            id=artifact.evidence_snapshot_id, run_id=run_id, game_project_id=project).first()
        if critique is None or snapshot is None:
            raise HTTPException(409, "The draft's critique or frozen evidence is unavailable.")
        return artifact, critique, snapshot

    @staticmethod
    def _identities(artifact, critique, snapshot):
        fingerprints = {"artifact_sha256": content_digest(artifact.content),
                        "critique_sha256": content_digest(critique.content),
                        "evidence_sha256": content_digest(snapshot.items)}
        findings = [{"index": index, "finding": finding,
                     "finding_id": content_digest([str(critique.id), fingerprints["critique_sha256"], index, finding])}
                    for index, finding in enumerate(critique.content.get("findings", []))]
        return fingerprints, findings

    def list(self, db: Session, run_id: UUID, artifact_id: UUID, project: str, user: User | None = None):
        from app.design_agent.review_policy import finding_review_policy
        artifact, critique, snapshot = self._load(db, run_id, artifact_id, project)
        fingerprints, findings = self._identities(artifact, critique, snapshot)
        try:
            records = db.query(DesignAgentFindingResolution).filter_by(
                run_id=run_id, artifact_id=artifact_id, game_project_id=project).order_by(
                DesignAgentFindingResolution.created_at, DesignAgentFindingResolution.id).all()
        except ProgrammingError as error:
            db.rollback()
            if getattr(error.orig, "pgcode", None) == "42P01":
                raise HTTPException(503, "Finding reviews are unavailable until the prepared database migration is applied.") from error
            raise
        run = db.query(DesignAgentRun).filter_by(id=run_id, game_project_id=project).first()
        latest = db.query(DesignAgentArtifact).filter_by(run_id=run_id, game_project_id=project).order_by(
            DesignAgentArtifact.version.desc()).first()
        member = db.query(ProjectMembership).filter_by(user_id=user.id, game_project_id=project).first() if user and user.is_active else None
        can_record = bool(member and member.role in {"owner", "editor"} and run.status == "awaiting_review"
                          and latest.id == artifact.id and not artifact.immutable and artifact.artifact_type != "final")
        findings, blocked, system_checks = finding_review_policy(db, run, artifact, snapshot, critique, records)
        return DesignAgentFindingReviewResponse(
            artifact_id=artifact.id, critique_id=critique.id, evidence_snapshot_id=snapshot.id, **fingerprints, findings=findings,
            can_record=can_record, critique_blocked=blocked, system_checks=system_checks,
            resolutions=[DesignAgentFindingResolutionResponse.model_validate(row) for row in records])

    def create(self, db: Session, run_id: UUID, artifact_id: UUID, project: str,
               payload: DesignAgentFindingResolutionCreate, user: User | None):
        if user is None or not user.is_active:
            raise HTTPException(401, "Sign in to record a finding review.")
        membership = db.query(ProjectMembership).filter_by(user_id=user.id, game_project_id=project).first()
        if membership is None or membership.role not in {"owner", "editor"}:
            raise HTTPException(403, "Only workspace owners and editors can record finding reviews.")
        artifact, critique, snapshot = self._load(db, run_id, artifact_id, project, write=True)
        fingerprints, findings = self._identities(artifact, critique, snapshot)
        if payload.critique_id != critique.id or any(getattr(payload, key) != value for key, value in fingerprints.items()):
            raise HTTPException(409, "Draft, critique or frozen evidence changed. Reload before reviewing the finding.")
        selected = next((item for item in findings if item["finding_id"] == payload.finding_id), None)
        if selected is None:
            raise HTTPException(409, "The selected finding is unavailable or stale.")
        excerpt = next((item for item in snapshot.items if item.get("chunk_id") == payload.evidence_chunk_id), None)
        if excerpt is None or payload.evidence_quote not in excerpt.get("content", ""):
            raise HTTPException(422, "Quote an exact passage from this draft's frozen evidence.")
        value = _finding_artifact_value(artifact.content, selected["finding"], payload.artifact_path)
        fields = dict(run_id=run_id, artifact_id=artifact_id, artifact_version=artifact.version,
                      game_project_id=project, critique_id=critique.id, evidence_snapshot_id=snapshot.id,
                      **fingerprints, finding_id=payload.finding_id, finding_index=selected["index"],
                      finding_content=copy.deepcopy(selected["finding"]), disposition="not_a_defect",
                      reason=payload.reason, artifact_path=payload.artifact_path, artifact_value=value,
                      evidence_chunk_id=payload.evidence_chunk_id, evidence_quote=payload.evidence_quote)
        existing = db.query(DesignAgentFindingResolution).filter_by(
            critique_id=critique.id, finding_id=payload.finding_id, game_project_id=project).first()
        if existing is not None:
            if any(getattr(existing, key) != expected for key, expected in fields.items()):
                raise HTTPException(409, "This finding already has a different recorded review. Audit records cannot be overwritten.")
            return DesignAgentFindingResolutionResponse.model_validate(existing)
        record = DesignAgentFindingResolution(**fields, reviewer_user_id=user.id, reviewer_label=user.email)
        db.add(record)
        try:
            db.commit()
        except IntegrityError as error:
            db.rollback()
            raise HTTPException(409, "The finding review changed concurrently. Reload before retrying.") from error
        db.refresh(record)
        return DesignAgentFindingResolutionResponse.model_validate(record)
