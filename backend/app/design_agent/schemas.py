from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DesignAgentRunCreate(BaseModel):
    objective: str = Field(min_length=10, max_length=2000)
    document_ids: list[UUID] = Field(min_length=1, max_length=10)
    max_revisions: int = Field(default=2, ge=1, le=3)


class DesignAgentReviewRequest(BaseModel):
    decision: Literal["approve", "reject"]
    reason: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def require_rejection_reason(self):
        if self.decision == "reject" and not (self.reason or "").strip():
            raise ValueError("A rejection reason is required.")
        return self


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


class DesignAgentRunResponse(BaseModel):
    id: UUID
    game_project_id: str
    objective: str
    document_ids: list[str]
    status: str
    current_node: str | None
    provider_name: str
    degraded: bool = False
    retrieval_revision: int
    revision_count: int
    max_revisions: int
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
    rubric_version: Literal["cyberrakshak-v1"] = "cyberrakshak-v1"
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
