from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator
from app.design_agent.contracts import BlueprintSectionKey, ProposalConfirmation, ResumeDecision


class DesignAgentRunCreate(BaseModel):
    objective: str = Field(min_length=10, max_length=2000)
    document_ids: list[UUID] = Field(min_length=1, max_length=10)
    max_revisions: int = Field(default=2, ge=1, le=3)
    hosted_provider_consent: bool = False
    fresh_dialogue: bool = False
    defer_runtime: StrictBool = False
    allow_unspecified_memory: StrictBool = False
    dialogue_policy: str | None = Field(default=None, min_length=10, max_length=240)

    @model_validator(mode="after")
    def require_nonblank_dialogue_policy(self):
        if self.dialogue_policy is not None:
            self.dialogue_policy = self.dialogue_policy.strip()
            if len(self.dialogue_policy) < 10:
                raise ValueError("Describe the fixed repeat/reset policy in at least 10 characters, or leave it unset.")
        return self


class DesignAgentCritiqueRetryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    artifact_id: UUID
    failed_execution_id: UUID
    hosted_provider_consent: StrictBool = False


class DesignAgentReviewRequest(BaseModel):
    decision: Literal["approve", "reject"]
    reason: str | None = Field(default=None, max_length=4000)
    target_sections: list[BlueprintSectionKey] | None = Field(default=None, min_length=1, max_length=9)
    artifact_id: UUID | None = None
    confirmed_proposals: list[ProposalConfirmation] = Field(default_factory=list, max_length=64)
    acknowledge_degraded: StrictBool = False

    @model_validator(mode="after")
    def require_rejection_reason(self):
        if self.decision == "reject" and not (self.reason or "").strip():
            raise ValueError("A rejection reason is required.")
        if self.decision == "reject" and not self.target_sections:
            raise ValueError("Select the blueprint sections allowed to change.")
        if self.decision == "approve" and self.target_sections is not None:
            raise ValueError("Approval does not accept revision targets.")
        ResumeDecision.model_validate(self.model_dump())
        return self


class DesignAgentFindingResolutionCreate(BaseModel):
    """A human assertion with frozen references, never permission to approve."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    critique_id: UUID
    critique_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    artifact_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    evidence_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    finding_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    reason: str = Field(min_length=30, max_length=4000)
    artifact_path: str = Field(min_length=2, max_length=500, pattern=r"^/")
    evidence_chunk_id: str = Field(min_length=1, max_length=100)
    evidence_quote: str = Field(min_length=12, max_length=2000)


class DesignAgentFindingResolutionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    artifact_id: UUID
    artifact_version: int
    critique_id: UUID
    evidence_snapshot_id: UUID
    artifact_sha256: str
    critique_sha256: str
    evidence_sha256: str
    finding_id: str
    finding_index: int
    finding_content: dict[str, Any]
    disposition: Literal["not_a_defect"]
    reason: str
    artifact_path: str
    artifact_value: Any
    evidence_chunk_id: str
    evidence_quote: str
    reviewer_user_id: UUID | None
    reviewer_label: str
    created_at: datetime
    approval_effect: Literal["none"] = "none"


class DesignAgentFindingReviewItem(BaseModel):
    finding_id: str
    index: int
    finding: dict[str, Any]
    origin: Literal["model", "server", "unknown"] = "unknown"
    can_resolve: bool = False
    resolution_applies: bool = False
    status_message: str = "Finding origin is unknown."


class DesignAgentFindingReviewResponse(BaseModel):
    artifact_id: UUID
    critique_id: UUID
    evidence_snapshot_id: UUID
    artifact_sha256: str
    critique_sha256: str
    evidence_sha256: str
    findings: list[DesignAgentFindingReviewItem]
    resolutions: list[DesignAgentFindingResolutionResponse]
    can_record: bool = False
    critique_blocked: bool = True
    system_checks: dict[str, Any] | None = None
    approval_effect: Literal["none"] = "none"


class DesignAgentArtifactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    version: int
    artifact_type: str
    content: dict[str, Any]
    immutable: bool
    blueprint_id: UUID | None
    created_at: datetime


class DesignAgentCritiqueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    artifact_id: UUID
    content: dict[str, Any]
    provider_name: str
    model_name: str
    created_at: datetime


class DesignAgentEvidenceItemResponse(BaseModel):
    chunk_id: str
    document_id: str | None = None
    title: str = "Untitled source"
    content: str
    chunk_index: int | None = None


class DesignAgentEvidenceResponse(BaseModel):
    artifact_id: UUID
    snapshot_id: UUID
    revision: int
    items: list[DesignAgentEvidenceItemResponse]


class DesignAgentRunResponse(BaseModel):
    id: UUID
    game_project_id: str
    objective: str
    document_ids: list[str]
    status: str
    current_node: str | None
    provider_name: str
    degraded: bool = False
    defer_runtime: bool = False
    allow_unspecified_memory: bool = False
    retrieval_revision: int
    revision_count: int
    max_revisions: int
    consecutive_revision_failures: int = 0
    max_consecutive_revision_failures: int = 3
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    current_artifact: DesignAgentArtifactResponse | None = None
    critique: DesignAgentCritiqueResponse | None = None


class DesignAgentTraceItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    node_name: str
    attempt: int
    status: str
    provider_name: str | None
    model_name: str | None
    latency_ms: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    details: dict[str, Any]
    error: str | None
    started_at: datetime
    completed_at: datetime | None


class DesignAgentTraceResponse(BaseModel):
    run_id: UUID
    status: str
    items: list[DesignAgentTraceItem]


class DesignAgentRuntimeExportResponse(BaseModel):
    api_version: str = "1.0"
    run_id: UUID
    blueprint_id: UUID
    game_project_id: str
    runtime_data: dict[str, Any]


class CitationJudgment(BaseModel):
    section: str = Field(min_length=1, max_length=100)
    chunk_id: UUID
    relevant: bool
    note: str | None = Field(default=None, max_length=1000)


class ClaimJudgment(BaseModel):
    claim: str = Field(min_length=3, max_length=2000)
    supported: bool
    note: str | None = Field(default=None, max_length=1000)


class CritiqueJudgment(BaseModel):
    finding_index: int = Field(ge=0)
    useful: bool
    note: str | None = Field(default=None, max_length=1000)


class RevisionJudgment(BaseModel):
    requirement: str = Field(min_length=3, max_length=2000)
    applied: bool
    unrelated_regression: bool = False
    note: str | None = Field(default=None, max_length=1000)


class DesignAgentEvaluationCreate(BaseModel):
    """A compact, reusable evaluation rubric for any reviewed GDD run.

    ``cyberrakshak-v1`` remains accepted for historical scorecards; new runs
    should use the project-neutral default.
    """

    rubric_version: Literal["gdd-v1", "cyberrakshak-v1"] = "gdd-v1"
    citation_judgments: list[CitationJudgment] = Field(min_length=1)
    claim_judgments: list[ClaimJudgment] = Field(min_length=1)
    critique_judgments: list[CritiqueJudgment] = Field(min_length=1)
    revision_judgments: list[RevisionJudgment] = Field(min_length=1)


class DesignAgentEvaluationMetric(BaseModel):
    key: str
    label: str
    value: float
    numerator: int
    denominator: int
    target: str
    passed: bool
    source: Literal["human_review", "system_verified"]


class DesignAgentEvaluationResponse(BaseModel):
    id: UUID
    run_id: UUID
    game_project_id: str
    rubric_version: str
    evaluator_label: str
    metrics: list[DesignAgentEvaluationMetric]
    overall_score: float
    passed: bool
    created_at: datetime
