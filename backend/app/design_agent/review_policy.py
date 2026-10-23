"""Server-only approval projection. Never rewrite independent review/audit records."""
import copy

from fastapi import HTTPException

from app.design_agent.contracts import CritiqueOutput
from app.design_agent.finding_reviews import DesignFindingReviewService, _finding_artifact_value, content_digest
from app.design_agent.grounding import complete_design_critique, critic_reference_errors, validate_design_approval
from app.models.design_agent import DesignAgentCritique, DesignAgentEvidenceSnapshot, DesignAgentFindingResolution


def requires_design_quality_review(run, confirmed_proposals=None):
    config = run.model_config or {}
    return bool(run.provider_name == "nvidia" or confirmed_proposals
                or config.get("fresh_dialogue") or config.get("defer_runtime") is True
                or config.get("allow_unspecified_memory") is True)


def canonical_review_request(request):
    request = request or {}
    return {"objective": request.get("objective", ""),
            "fresh_dialogue": bool(request.get("fresh_dialogue")),
            "dialogue_policy": request.get("dialogue_policy"),
            **({"resolved_decisions": copy.deepcopy(request["resolved_decisions"])} if request.get("resolved_decisions") else {}),
            **({"defer_runtime": True} if request.get("defer_runtime") is True else {}),
            **({"allow_unspecified_memory": True} if request.get("allow_unspecified_memory") is True else {}),
            **({"design_contract_version": 2} if type(request.get("design_contract_version")) is int
               and request["design_contract_version"] == 2 else {})}


def saved_review_request(run):
    return canonical_review_request({**(run.model_config or {}), "objective": run.objective})


def build_review_provenance(raw_review, content, evidence, request, *, clean):
    """Called by the NVIDIA adapter, not populated from model JSON or API input."""
    return {"version": 1, "clean": clean is True, "artifact_sha256": content_digest(content),
            "evidence_sha256": content_digest(evidence),
            "request_sha256": content_digest(canonical_review_request(request)),
            "model_output": CritiqueOutput.model_validate(raw_review).model_dump()}


def _resolved_indexes(db, run, artifact, snapshot, critique, raw, records=None):
    fingerprints, findings = DesignFindingReviewService._identities(artifact, critique, snapshot)
    if records is None:
        records = db.query(DesignAgentFindingResolution).filter_by(
            game_project_id=run.game_project_id, run_id=run.id, artifact_id=artifact.id,
            critique_id=critique.id).all()
    resolved = set()
    for record in records:
        if not isinstance(record.finding_index, int) or not 0 <= record.finding_index < len(raw["findings"]):
            continue  # Deterministic findings are never model-origin findings.
        selected = findings[record.finding_index]
        fields = {**fingerprints, "game_project_id": run.game_project_id, "run_id": run.id,
                  "artifact_id": artifact.id, "artifact_version": artifact.version,
                  "critique_id": critique.id, "evidence_snapshot_id": snapshot.id,
                  "finding_id": selected["finding_id"], "finding_content": selected["finding"],
                  "disposition": "not_a_defect"}
        if (any(getattr(record, key) != value for key, value in fields.items())
                or not record.reviewer_user_id or not record.created_at
                or not record.reason or len(record.reason.strip()) < 30):
            continue
        excerpt = next((item for item in snapshot.items if item.get("chunk_id") == record.evidence_chunk_id), None)
        if (excerpt is None or not record.evidence_quote or len(record.evidence_quote) < 12
                or record.evidence_quote not in excerpt.get("content", "")):
            continue
        try:
            if not record.artifact_path or not record.artifact_path.startswith("/"):
                continue
            value = _finding_artifact_value(artifact.content, selected["finding"], record.artifact_path)
            if content_digest(value) != content_digest(record.artifact_value):
                continue
        except HTTPException:
            continue
        resolved.add(record.finding_index)
    return resolved


def _trusted_model_review(artifact, snapshot, critique, request):
    original = critique.content
    provenance = original.get("model_review_provenance")
    # Legacy, recovered and fallback reviews cannot acquire trusted origins later.
    if (critique.provider_name != "nvidia" or not isinstance(provenance, dict)
            or provenance.get("version") != 1 or provenance.get("clean") is not True):
        return None
    try:
        raw = CritiqueOutput.model_validate(provenance["model_output"]).model_dump()
        if request.get("design_contract_version") == 2 and critic_reference_errors(raw, artifact.content, snapshot.items):
            return None  # Invalid review contracts cannot be dismissed through human finding resolutions.
        expected = build_review_provenance(raw, artifact.content, snapshot.items, request, clean=True)
        reconstructed = complete_design_critique(raw, artifact.content, evidence=snapshot.items, review_request=request)
    except (ValueError, KeyError, TypeError):
        return None
    if provenance != expected or original != {**reconstructed, "model_review_provenance": expected}:
        return None
    return raw


def _approval_projection(db, run, artifact, snapshot, critique, request, records=None):
    original = critique.content
    raw = _trusted_model_review(artifact, snapshot, critique, request)
    if raw is None:
        return original
    if not raw["findings"]:
        return original  # No model findings to dismiss; do not query audit storage.
    resolved = _resolved_indexes(db, run, artifact, snapshot, critique, raw, records)
    projected = copy.deepcopy(raw)
    projected["findings"] = [item for index, item in enumerate(raw["findings"]) if index not in resolved]
    if raw["findings"] and len(resolved) == len(raw["findings"]):
        projected["verdict"] = "ready_for_review"
    # Re-add deterministic findings even if a model duplicated one or a human
    # recorded a dispute against it. Pure approval still recomputes all checks.
    return complete_design_critique(projected, artifact.content, evidence=snapshot.items, review_request=request)


def finding_review_policy(db, run, artifact, snapshot, critique, records):
    """Read-only UI explanation from the same policy used by actual approval."""
    request = saved_review_request(run)
    raw = _trusted_model_review(artifact, snapshot, critique, request)
    resolved = _resolved_indexes(db, run, artifact, snapshot, critique, raw, records) if raw else set()
    invalid_draft = False
    server = None
    try:
        server = complete_design_critique({"verdict": "ready_for_review", "summary": "System checks", "findings": []},
                                         artifact.content, evidence=snapshot.items, review_request=request)
        server_keys = {(item["section"], item["issue"]) for item in server["findings"]}
    except ValueError:
        # Keep historical/incomplete drafts readable without treating their
        # missing schema as trusted finding origins or approval evidence.
        invalid_draft = True
        server_keys = set()
    _, findings = DesignFindingReviewService._identities(artifact, critique, snapshot)
    for item in findings:
        finding = item["finding"]
        origin = ("server" if (finding["section"], finding["issue"]) in server_keys else
                  "model" if raw is not None and item["index"] < len(raw["findings"]) else "unknown")
        applies = origin == "model" and item["index"] in resolved
        recorded = any(record.finding_id == item["finding_id"] for record in records)
        message = ("Human-reviewed, not AI-verified. Applies only to this exact draft and frozen evidence." if applies else
                   "System check. A human resolution cannot remove this blocker." if origin == "server" else
                   "Finding origin is unknown or stale. A new critique is needed before this finding can be dismissed." if origin == "unknown" else
                   "The recorded review no longer applies. It cannot be overwritten; request a new critique." if recorded else
                   "Compare the exact draft field with frozen evidence before recording your judgment.")
        item.update(origin=origin, resolution_applies=applies, can_resolve=origin == "model" and not recorded and not invalid_draft,
                    status_message=message)
    projected = _approval_projection(db, run, artifact, snapshot, critique, request, records)
    blocked = invalid_draft or (server is not None and server["verdict"] != "ready_for_review") or projected.get("verdict") != "ready_for_review" or any(
        item.get("severity") == "high" for item in projected.get("findings", []))
    return findings, blocked, server


def validate_persisted_design_approval(db, run, artifact, confirmed_proposals=None, *, expected=None):
    """Shared API/worker/finalize gate; reload current persisted review and evidence."""
    if artifact is None or artifact.immutable or artifact.artifact_type == "final":
        raise ValueError("Review the current draft; the approval is stale.")
    if artifact.run_id != run.id or artifact.game_project_id != run.game_project_id:
        raise ValueError("Review the current workspace draft; the approval is stale.")
    snapshot = db.query(DesignAgentEvidenceSnapshot).filter(
        DesignAgentEvidenceSnapshot.id == artifact.evidence_snapshot_id,
        DesignAgentEvidenceSnapshot.run_id == run.id,
        DesignAgentEvidenceSnapshot.game_project_id == run.game_project_id).first()
    critique = db.query(DesignAgentCritique).filter(
        DesignAgentCritique.artifact_id == artifact.id, DesignAgentCritique.run_id == run.id,
        DesignAgentCritique.game_project_id == run.game_project_id).order_by(
            DesignAgentCritique.created_at.desc(), DesignAgentCritique.id.desc()).first()
    if snapshot is None or critique is None:
        raise ValueError("The draft's independent critique or frozen evidence is unavailable.")
    if expected is not None and any(expected[key] != value for key, value in (
            ("content", artifact.content), ("evidence", snapshot.items), ("critique", critique.content))):
        raise ValueError("Review the current draft, critique and evidence; the approval is stale.")
    request = saved_review_request(run)
    projected = _approval_projection(db, run, artifact, snapshot, critique, request)
    return validate_design_approval(artifact.content, snapshot.items, projected, confirmed_proposals,
                                    review_request=request)
