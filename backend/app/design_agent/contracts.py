from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field


BLUEPRINT_SECTION_KEYS = (
    "summary",
    "narrative_direction",
    "art_style_direction",
    "npc_archetypes",
    "npc_memory_design",
    "level_design_suggestions",
    "gameplay_systems",
    "quest_hooks",
    "unity_runtime_preview",
)


class ResearchPlan(BaseModel):
    objective: str
    retrieval_query: str
    required_sections: list[str] = Field(default_factory=lambda: list(BLUEPRINT_SECTION_KEYS))


class BlueprintSection(BaseModel):
    content: dict[str, Any] = Field(default_factory=dict)
    citations: list[str] = Field(default_factory=list)
    confidence: Literal["High", "Medium", "Low"]
    warnings: list[str] = Field(default_factory=list)


class BlueprintContent(BaseModel):
    summary: BlueprintSection
    narrative_direction: BlueprintSection
    art_style_direction: BlueprintSection
    npc_archetypes: BlueprintSection
    npc_memory_design: BlueprintSection
    level_design_suggestions: BlueprintSection
    gameplay_systems: BlueprintSection
    quest_hooks: BlueprintSection
    unity_runtime_preview: BlueprintSection


class CritiqueFinding(BaseModel):
    severity: Literal["high", "medium", "low"]
    section: str
    issue: str
    recommendation: str


class CritiqueOutput(BaseModel):
    verdict: Literal["ready_for_review", "needs_revision"]
    findings: list[CritiqueFinding] = Field(default_factory=list)
    summary: str


class ResumeDecision(BaseModel):
    decision: Literal["approve", "reject"]
    reason: str | None = None
    reviewer_user_id: str | None = None
    reviewer_label: str = "local_developer"


class DesignAgentState(TypedDict, total=False):
    run_id: str
    game_project_id: str
    objective: str
    document_ids: list[str]
    max_revisions: int
    revision_count: int
    plan: dict[str, Any]
    evidence_snapshot_id: str
    evidence_items: list[dict[str, Any]]
    current_artifact_id: str
    current_artifact_version: int
    current_artifact: dict[str, Any]
    critique_id: str
    critique: dict[str, Any]
    review_decision: str
    rejection_reason: str
    final_artifact_id: str
    blueprint_id: str
