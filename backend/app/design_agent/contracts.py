from typing import Any, Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field, field_validator


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

SECTION_RETRIEVAL_FOCUS = {
    "summary": "game overview premise genre player role target platform",
    "narrative_direction": "story narrative lore history factions conflict themes ending",
    "art_style_direction": "art style visual direction palette environment character aesthetic",
    "npc_archetypes": "characters NPC roles personality dialogue relationship companion antagonist",
    "npc_memory_design": "NPC memory continuity reactions choices trust relationship persistent events",
    "level_design_suggestions": "level mission stage progression objectives environment Level 1 Level 10",
    "gameplay_systems": "core gameplay loop mechanics controls scoring progression combat puzzle stealth",
    "quest_hooks": "quests missions objectives rewards side quests story tasks",
    "unity_runtime_preview": "Unity engine platform runtime integration build target prefabs scenes data",
}
BlueprintSectionKey = Literal[
    "summary",
    "narrative_direction",
    "art_style_direction",
    "npc_archetypes",
    "npc_memory_design",
    "level_design_suggestions",
    "gameplay_systems",
    "quest_hooks",
    "unity_runtime_preview",
]


def build_section_queries(
    objective: str,
    retrieval_query: str,
) -> dict[BlueprintSectionKey, str]:
    """Create stable section queries without spending another model call."""
    # The selected document IDs already provide game context. Repeating a broad
    # objective in every query makes introductory chunks rank for every section.
    _ = objective, retrieval_query
    return {
        section: focus
        for section, focus in SECTION_RETRIEVAL_FOCUS.items()
    }


class ResearchPlan(BaseModel):
    objective: str
    retrieval_query: str
    required_sections: list[BlueprintSectionKey] = Field(
        default_factory=lambda: list(BLUEPRINT_SECTION_KEYS)
    )
    section_queries: dict[BlueprintSectionKey, str] = Field(
        default_factory=lambda: build_section_queries("", "")
    )

    @field_validator("required_sections")
    @classmethod
    def require_complete_blueprint_scope(
        cls,
        value: list[BlueprintSectionKey],
    ) -> list[BlueprintSectionKey]:
        if set(value) != set(BLUEPRINT_SECTION_KEYS):
            raise ValueError(
                "Research plans must include every GameMind blueprint section."
            )
        return list(BLUEPRINT_SECTION_KEYS)

    @field_validator("section_queries")
    @classmethod
    def require_query_for_each_section(
        cls,
        value: dict[BlueprintSectionKey, str],
    ) -> dict[BlueprintSectionKey, str]:
        if set(value) != set(BLUEPRINT_SECTION_KEYS):
            raise ValueError("Research plans must include one query for every blueprint section.")
        if any(not query.strip() for query in value.values()):
            raise ValueError("Blueprint section queries cannot be empty.")
        return value


class RetrievalPlanOutput(BaseModel):
    """Only the semantic retrieval decision belongs to the planner model."""

    retrieval_query: str = Field(min_length=3, max_length=500)


class BlueprintSection(BaseModel):
    content: dict[str, Any] = Field(default_factory=dict)
    citations: list[str] = Field(default_factory=list)
    confidence: Literal["High", "Medium", "Low"]
    warnings: list[str] = Field(default_factory=list)


class NPCDesignCandidate(BaseModel):
    """A reviewable NPC brief, not an active runtime NPC record."""

    name: str
    archetype: str
    dialogue_style: str
    source_chunk_ids: list[str] = Field(min_length=1)
    dialogue_hooks: list[str] = Field(default_factory=list)
    relationship_notes: list[str] = Field(default_factory=list)
    implementation_notes: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class QuestDesignCandidate(BaseModel):
    """A reviewable quest brief that preserves the legacy materializer fields."""

    id: str
    title: str
    objective: str
    source_chunk_ids: list[str] = Field(min_length=1)
    reward: str | None = None
    objectives: list[str] = Field(default_factory=list)
    failure_states: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    dialogue_hooks: list[str] = Field(default_factory=list)
    implementation_notes: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    runtime: "QuestRuntimeBinding | None" = None


class QuestRuntimeObjectiveBinding(BaseModel):
    """Explicit engine binding; never inferred from natural-language objectives."""

    description: str = Field(min_length=1)
    target_type: str = Field(min_length=1, max_length=50)
    target_id: str = Field(min_length=1, max_length=100)
    quantity_required: int = Field(ge=1)


class QuestRuntimeBinding(BaseModel):
    """The complete runtime semantics required by the legacy Quest tables."""

    npc_slug: str = Field(min_length=1, max_length=100)
    difficulty: str = Field(min_length=1, max_length=50)
    gold_reward: int = Field(ge=0)
    xp_reward: int = Field(ge=0)
    objectives: list[QuestRuntimeObjectiveBinding] = Field(min_length=1)


class NPCDesignContent(BaseModel):
    """The only valid container for developer-facing NPC artifacts."""

    model_config = ConfigDict(extra="forbid")

    npcs: list[NPCDesignCandidate]


class QuestDesignContent(BaseModel):
    """The only valid container for developer-facing quest artifacts."""

    model_config = ConfigDict(extra="forbid")

    quests: list[QuestDesignCandidate]


class NPCBlueprintSection(BlueprintSection):
    content: NPCDesignContent


class QuestBlueprintSection(BlueprintSection):
    content: QuestDesignContent


class FocusedDeveloperPack(BaseModel):
    """Small, evidence-scoped artifacts generated after the broad blueprint."""

    npc_archetypes: NPCBlueprintSection
    quest_hooks: QuestBlueprintSection


class PatchDialogueLine(BaseModel):
    text: str = Field(min_length=8)
    source_chunk_ids: list[str] = Field(min_length=1)


class PatchDialoguePack(BaseModel):
    lines: list[PatchDialogueLine] = Field(min_length=1, max_length=3)


class ActionableQuestCandidate(QuestDesignCandidate):
    objectives: list[str] = Field(min_length=1, max_length=4)
    failure_states: list[str] = Field(min_length=1, max_length=3)
    dependencies: list[str] = Field(min_length=1, max_length=3)


class FocusedQuestPack(BaseModel):
    quests: list[ActionableQuestCandidate] = Field(min_length=1, max_length=1)


class BlueprintContent(BaseModel):
    summary: BlueprintSection
    narrative_direction: BlueprintSection
    art_style_direction: BlueprintSection
    npc_archetypes: NPCBlueprintSection
    npc_memory_design: BlueprintSection
    level_design_suggestions: BlueprintSection
    gameplay_systems: BlueprintSection
    quest_hooks: QuestBlueprintSection
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
    resolved_decisions: list[dict[str, Any]]
    current_artifact_id: str
    current_artifact_version: int
    current_artifact: dict[str, Any]
    critique_id: str
    critique: dict[str, Any]
    review_decision: str
    rejection_reason: str
    final_artifact_id: str
    blueprint_id: str
