from copy import deepcopy
from typing import Annotated, Any, Literal, TypedDict, Union, get_args, get_origin
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, create_model, field_validator, model_serializer, model_validator
from pydantic.json_schema import SkipJsonSchema


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
    "summary": "game summary overview high concept premise genre",
    "narrative_direction": "story narrative lore history factions conflict themes ending",
    "art_style_direction": "art style visual direction aesthetic colour palette environment character textures lighting",
    "npc_archetypes": "characters NPC roles personality voice dialogue style support companion mentor antagonist",
    "npc_memory_design": "NPC memory dialogue reactions player behaviour repeated mistakes choices relationships state",
    "level_design_suggestions": "level design mission sequence progression tutorial environments locations traversal unlock prerequisites",
    "gameplay_systems": "core gameplay loop mechanics systems player actions stealth combat puzzles scoring detection health",
    "quest_hooks": "level plan mission sequence tutorial progression unlock prerequisites quests objectives rewards failure states",
    "unity_runtime_preview": "runtime integration engine platform build targets client events configuration dialogue memory quest state",
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
    """Game-neutral fallback for local and older single-query planners."""
    queries = dict(SECTION_RETRIEVAL_FOCUS)
    # Use the planner's broad query once, not in every section where it would
    # make introductory chunks crowd out character, level and quest passages.
    context = " ".join((retrieval_query or objective).split())
    if context:
        queries["summary"] = f"{queries['summary']} {context}"[:500]
    return queries


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
    """The planner owns bounded search queries, never workflow scope or evidence."""

    model_config = ConfigDict(str_strip_whitespace=True)

    retrieval_query: str = Field(min_length=3, max_length=500)
    section_queries: dict[
        BlueprintSectionKey, Annotated[str, Field(min_length=3, max_length=500)]
    ] = Field(default_factory=dict)

    @field_validator("section_queries")
    @classmethod
    def require_complete_section_queries_when_supplied(cls, value):
        # Empty preserves compatibility with older single-query completions.
        return ResearchPlan.require_query_for_each_section(value) if value else value


class HostedRetrievalPlanOutput(BaseModel):
    """Fresh hosted plans require all queries; legacy single-query parsing stays separate."""

    model_config = ConfigDict(str_strip_whitespace=True)

    section_queries: dict[
        BlueprintSectionKey, Annotated[str, Field(min_length=3, max_length=500)]
    ] = Field(json_schema_extra={
        "properties": {section: {"type": "string", "minLength": 3, "maxLength": 500,
                                 "not": {"enum": ["null", "none", "n/a"]},
                                 "description": "Focused search terms, not a runtime binding or null placeholder."}
                       for section in BLUEPRINT_SECTION_KEYS},
        "required": list(BLUEPRINT_SECTION_KEYS),
        "additionalProperties": False,
    })

    @field_validator("section_queries")
    @classmethod
    def require_hosted_search_queries(cls, value):
        ResearchPlan.require_query_for_each_section(value)
        if any(query.casefold() in {"null", "none", "n/a"} for query in value.values()):
            raise ValueError("Blueprint section queries must be search terms, not null placeholders.")
        return value


class BlueprintSection(BaseModel):
    content: dict[str, Any] = Field(default_factory=dict)
    citations: list[str] = Field(default_factory=list)
    confidence: Literal["High", "Medium", "Low"]
    warnings: list[str] = Field(default_factory=list)


class DialogueEligibility(BaseModel):
    """Design predicates only; never executable game bindings."""

    # Guided decoding must see the coupled rules, not just four independent enums.
    model_config = ConfigDict(extra="forbid", json_schema_extra={
        "anyOf": [{"properties": {
            "stage": {"enum": stages},
            "quest_id": ({"type": "null"} if lifecycle is None else
                         {"type": "string", "pattern": r"\S"}),
            "lifecycle": {"const": lifecycle},
            "progress": {"enum": progress},
        }, "required": ["stage", "quest_id", "lifecycle", "progress"]} for stages, lifecycle, progress in (
            (["greeting", "other"], None, ["any"]),
            (["greeting", "other", "progress"], "active", ["incomplete"]),
            (["greeting", "other"], "active", ["any"]),
            (["greeting", "other"], "failed", ["incomplete", "any"]),
            (["greeting", "other", "completion"], "completed", ["complete"]),
        )],
    })
    stage: Literal["greeting", "progress", "completion", "other"]
    quest_id: str | None
    lifecycle: Literal["active", "failed", "completed"] | None
    progress: Literal["incomplete", "complete", "any"]

    @model_validator(mode="after")
    def consistent_state(self):
        if self.quest_id is None:
            if self.lifecycle is not None or self.progress != "any" or self.stage in {"progress", "completion"}:
                raise ValueError("Quest dialogue needs an explicit quest and lifecycle.")
        elif (not self.quest_id.strip() or self.lifecycle is None
              or (self.lifecycle == "completed" and self.progress != "complete")
              or (self.lifecycle != "completed" and self.progress == "complete")):
            raise ValueError("Dialogue eligibility declares an inconsistent quest state.")
        if self.stage == "progress" and (self.lifecycle, self.progress) != ("active", "incomplete"):
            raise ValueError("Progress dialogue requires an active, incomplete attempt.")
        if self.stage == "completion" and (self.lifecycle, self.progress) != ("completed", "complete"):
            raise ValueError("Completion dialogue requires a completed attempt.")
        return self


class DialogueTriggerMapping(BaseModel):
    """A proposed event/line pair, not a verified or active engine binding."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    trigger: str = Field(min_length=1, max_length=120)
    situation: str = Field(min_length=1, max_length=500)
    text: str = Field(min_length=1, max_length=1000)
    repeat_policy: str = Field(min_length=1, max_length=500)
    eligibility: DialogueEligibility | None = None
    manual_test: SkipJsonSchema[str] = Field(
        default="", min_length=1, max_length=2500,
        description="Server-derived from situation, exact spoken text and proposed repeat/reset policy. Omit from model output.",
    )

    @model_validator(mode="after")
    def derive_manual_test(self) -> "DialogueTriggerMapping":
        # Never trust duplicate model-authored text or a stale revision test.
        # This produces test instructions, not evidence that the test was run.
        setup = self.situation
        if self.eligibility:
            condition = self.eligibility
            setup += (f"; eligibility stage={condition.stage}, quest={condition.quest_id}, "
                      f"lifecycle={condition.lifecycle}, progress={condition.progress}")
        self.manual_test = (
            f"Setup: {setup}. Action: interact. Expect: {self.text} Repeat: {self.repeat_policy} "
            "Action: interact outside this situation; expect this trigger suppressed. "
            "Stated resets only; recheck situation eligibility; replay is not automatic. "
            "If suppressed with no allowed reset, verify it stays suppressed."
        )
        return self

    @model_serializer(mode="wrap")
    def preserve_legacy_shape(self, handler):
        result = handler(self)
        if self.eligibility is None:
            result.pop("eligibility", None)
        return result


class DialogueRevisionPair(BaseModel):
    """Compact proposal; duplicated hooks and manual steps are server-derived."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    trigger: str = Field(min_length=1, max_length=120)
    situation: str = Field(min_length=1, max_length=300)
    text: str = Field(min_length=1, max_length=700)
    repeat_policy: str = Field(min_length=1, max_length=240)


class NPCDialoguePatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1)
    source_chunk_ids: list[str] = Field(min_length=1, max_length=3)
    dialogue_triggers: list[DialogueRevisionPair] = Field(min_length=1, max_length=3)
    assumptions: list[str] = Field(default_factory=list, max_length=3)


class NPCDialoguePatchSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patches: list[NPCDialoguePatch] = Field(min_length=1, max_length=2)


class NPCDialogueRevisionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    npc_archetypes: NPCDialoguePatchSection


class NPCDesignCandidate(BaseModel):
    """A reviewable NPC brief, not an active runtime NPC record."""

    name: str
    archetype: str
    dialogue_style: str
    source_chunk_ids: list[str] = Field(min_length=1)
    dialogue_hooks: SkipJsonSchema[list[str]] = Field(default_factory=list)
    dialogue_triggers: list[DialogueTriggerMapping] = Field(default_factory=list, max_length=3)
    relationship_notes: list[str] = Field(default_factory=list)
    implementation_notes: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    fresh_dialogue: SkipJsonSchema[bool] = False

    @model_validator(mode="after")
    def derive_omitted_hooks(self) -> "NPCDesignCandidate":
        # New completions own one set of spoken lines. Explicit historical
        # hooks remain untouched so ambiguous saved drafts still fail closed.
        if "dialogue_hooks" not in self.model_fields_set and self.dialogue_triggers:
            self.dialogue_hooks = [mapping.text for mapping in self.dialogue_triggers]
        return self


def _quest_action_schema(schema: dict) -> None:
    # Raw \S patterns can consume JSON quotes in native decoders; enforce readability locally.
    schema.pop("pattern", None)


QuestEventAction = Annotated[str, Field(
    min_length=3, max_length=1000, pattern=r"\S+\s+\S+", json_schema_extra=_quest_action_schema,
)]


class QuestObjectiveState(BaseModel):
    """Proposed event sets ONLY this objective flag true while active.

    Flags start false and persist independently until explicit restart. Event
    descriptions are human-reviewed design intent, never executable expressions.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    objective: str = Field(min_length=1, max_length=1000)
    flag: str = Field(pattern=r"^[a-z][a-z0-9_]{0,79}$")
    event: str = Field(min_length=1, max_length=1000)

    @field_validator("flag")
    @classmethod
    def separate_lifecycle(cls, value: str) -> str:
        if value in {"quest", "quest_state", "lifecycle", "active", "failed", "completed"}:
            raise ValueError("An objective flag cannot replace quest lifecycle state.")
        return value


class QuestCompletionState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    required_flags: list[str] = Field(min_length=1)
    mode: Literal["all"]
    reevaluate_on: Literal["each_objective_update"]
    lifecycle: Literal["completed"]


class QuestFailureState(BaseModel):
    """While active, a proposed failure event changes lifecycle, not progress."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    events: list[Annotated[str, Field(min_length=1, max_length=1000)]] = Field(min_length=1)
    lifecycle: Literal["failed"]


class QuestRestartState(BaseModel):
    """Explicit new attempt atomically clears listed flags and reactivates."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    event: str = Field(min_length=1, max_length=1000)
    lifecycle: Literal["active"]
    clear_flags: list[str] = Field(min_length=1)


class QuestStateContract(BaseModel):
    """Version 1: independent boolean objectives; not a runtime binding.

    An attempt starts active with all flags false. Each objective event sets
    only its flag true while active, then reevaluates ALL required flags.
    Completion/failure end the active attempt; objective events cannot mutate
    a terminal attempt. Explicit restart starts active with every flag false.
    Ordered/prerequisite quests need separate designer review; v1 does not
    infer ordering, engine IDs, reward dispatch or event wiring from prose.
    """

    model_config = ConfigDict(extra="forbid")

    version: Literal["1"]
    objectives: list[QuestObjectiveState] = Field(min_length=1)
    completion: QuestCompletionState
    failure: QuestFailureState | None = None
    restart: QuestRestartState | None = None
    event_actions: dict[str, QuestEventAction] | None = None

    @model_validator(mode="after")
    def require_all_objective_flags(self) -> "QuestStateContract":
        flags = [item.flag for item in self.objectives]
        if len(flags) != len(set(flags)):
            raise ValueError("Quest objective flags must be distinct.")
        required = self.completion.required_flags
        if len(required) != len(set(required)) or set(required) != set(flags):
            raise ValueError("Completion must require all and only the distinct objective flags.")
        if self.restart:
            cleared = self.restart.clear_flags
            if len(cleared) != len(set(cleared)) or set(cleared) != set(flags):
                raise ValueError("Restart must clear all and only the distinct objective flags.")
        if self.event_actions is not None:
            events = [item.event for item in self.objectives]
            events += self.failure.events if self.failure else []
            events += [self.restart.event] if self.restart else []
            if len(events) != len(set(events)) or set(events) != set(self.event_actions):
                raise ValueError("Event actions must describe every distinct declared event, without extra keys.")
            if any(len(action.split()) < 2 for action in self.event_actions.values()):
                raise ValueError("Describe each observable event action, not just an identifier.")
        return self

    @model_serializer(mode="wrap")
    def preserve_legacy_shape(self, handler):
        result = handler(self)
        if self.event_actions is None:
            result.pop("event_actions", None)
        return result


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
    state_contract: QuestStateContract | None = None
    runtime: "QuestRuntimeBinding | None" = None

    @model_validator(mode="after")
    def match_state_objectives(self) -> "QuestDesignCandidate":
        if self.state_contract:
            expected = [" ".join(value.split()).casefold() for value in self.objectives]
            actual = [" ".join(item.objective.split()).casefold() for item in self.state_contract.objectives]
            if len(expected) != len(set(expected)) or sorted(expected) != sorted(actual):
                raise ValueError("State contract must cover every quest objective exactly once.")
            if self.failure_states and not self.state_contract.failure:
                raise ValueError("State contract needs failure events for the declared failure states.")
        return self


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

    @model_validator(mode="after")
    def dialogue_quest_references(self):
        quests = {quest.id: quest for quest in self.quest_hooks.content.quests}
        for npc in self.npc_archetypes.content.npcs:
            for mapping in npc.dialogue_triggers:
                condition = mapping.eligibility
                if condition and condition.quest_id is not None:
                    quest = quests.get(condition.quest_id)
                    if quest is None or quest.state_contract is None:
                        raise ValueError("Dialogue eligibility must reference a declared typed quest.")
                    if condition.lifecycle == "failed" and quest.state_contract.failure is None:
                        raise ValueError("Failed dialogue requires a declared failure transition.")
        return self


class GeneratedNPCDesignCandidate(NPCDesignCandidate):
    """Reject misplaced section metadata rather than silently dropping it."""

    model_config = ConfigDict(extra="forbid")


class GeneratedNPCDesignContent(NPCDesignContent):
    npcs: list[GeneratedNPCDesignCandidate]


class GeneratedNPCBlueprintSection(NPCBlueprintSection):
    content: GeneratedNPCDesignContent


class GeneratedQuestDesignCandidate(QuestDesignCandidate):
    """New hosted output must declare state, never silently upgrade a legacy draft."""

    state_contract: QuestStateContract


class GeneratedQuestDesignContent(QuestDesignContent):
    quests: list[GeneratedQuestDesignCandidate]


class GeneratedQuestBlueprintSection(QuestBlueprintSection):
    content: GeneratedQuestDesignContent


class GeneratedBlueprintContent(BlueprintContent):
    npc_archetypes: GeneratedNPCBlueprintSection
    quest_hooks: GeneratedQuestBlueprintSection


class GovernedDialogueTrigger(DialogueTriggerMapping):
    eligibility: DialogueEligibility


class GovernedNPC(GeneratedNPCDesignCandidate):
    dialogue_triggers: list[GovernedDialogueTrigger] = Field(max_length=3)


class GovernedNPCContent(GeneratedNPCDesignContent):
    npcs: list[GovernedNPC]


class GovernedNPCSection(GeneratedNPCBlueprintSection):
    content: GovernedNPCContent


class GovernedQuestState(QuestStateContract):
    event_actions: dict[str, QuestEventAction]


class GovernedQuest(GeneratedQuestDesignCandidate):
    objectives: list[str] = Field(min_length=1)
    state_contract: GovernedQuestState


class GovernedQuestContent(GeneratedQuestDesignContent):
    quests: list[GovernedQuest]


class GovernedQuestSection(GeneratedQuestBlueprintSection):
    content: GovernedQuestContent


class GovernedBlueprintContent(GeneratedBlueprintContent):
    """Contract 2 for new governed runs; historical drafts retain their shape."""

    npc_archetypes: GovernedNPCSection
    quest_hooks: GovernedQuestSection


class GeneratedGovernedQuest(GovernedQuest):
    objectives: SkipJsonSchema[list[str]] = Field(default_factory=list, min_length=1)

    @model_validator(mode="after")
    def match_state_objectives(self) -> "GeneratedGovernedQuest":
        # Only omitted display text is derived; explicit conflicts must still fail.
        if "objectives" not in self.model_fields_set:
            self.objectives = [item.objective for item in self.state_contract.objectives]
        return super().match_state_objectives()


class GeneratedGovernedQuestContent(GovernedQuestContent):
    quests: list[GeneratedGovernedQuest] = Field(max_length=2)


class GeneratedGovernedQuestSection(GovernedQuestSection):
    content: GeneratedGovernedQuestContent


class FreshGovernedNPC(GovernedNPC):
    dialogue_triggers: list[GovernedDialogueTrigger] = Field(min_length=1, max_length=3)


class FreshGovernedNPCContent(GovernedNPCContent):
    npcs: list[FreshGovernedNPC] = Field(max_length=2)


class FreshGovernedNPCSection(GovernedNPCSection):
    content: FreshGovernedNPCContent


class GeneratedGovernedBlueprintContent(GovernedBlueprintContent):
    """New drafts require speech; freshness policy and saved profiles stay separate."""

    npc_archetypes: FreshGovernedNPCSection
    quest_hooks: GeneratedGovernedQuestSection


class FreshGovernedBlueprintContent(GeneratedGovernedBlueprintContent):
    """Fresh generation cannot silently omit every spoken line for a returned NPC."""

    npc_archetypes: FreshGovernedNPCSection


class BlueprintSectionRevision(BaseModel):
    """Marker for scoped blueprint responses requiring repair preservation."""

    model_config = ConfigDict(extra="forbid")


def _require_content_citations(self):
    content = self.content.model_dump() if isinstance(self.content, BaseModel) else self.content
    empty = all(value is None or value == "" or value == [] or value == {} for value in content.values())
    if not empty and not self.citations:
        raise ValueError("Nonempty generated section content requires section-matched citations.")
    return self


def _cited_section_schema(schema: dict, model: type[BaseModel]) -> None:
    # Native decoding needs self-contained cited/empty alternatives, not a local-only conditional.
    properties = schema["properties"]
    empty_value = {"anyOf": [{"type": "null"}, {"const": ""},
                             {"type": "array", "items": {}, "maxItems": 0},
                             {"type": "object", "properties": {}, "additionalProperties": False}]}
    empty_content = {"type": "object", "additionalProperties": empty_value}
    content_type = model.model_fields["content"].annotation
    if isinstance(content_type, type) and issubclass(content_type, BaseModel):
        empty_content = {"type": "object", "properties": {
            name: {"type": "array", "items": {}, "maxItems": 0} if get_origin(field.annotation) is list else {"type": "null"}
            for name, field in content_type.model_fields.items()},
            "required": list(content_type.model_fields), "additionalProperties": False}
    cited = {"properties": {**properties, "citations": {**properties["citations"], "minItems": 1}},
             "required": schema["required"]}
    uncited = {"properties": {**properties, "content": empty_content,
                              "citations": {**properties["citations"], "maxItems": 0}},
               "required": schema["required"]}
    schema["anyOf"] = ([cited] if properties["citations"].get("maxItems") != 0 else []) + [uncited]


def grounded_response_model(contract: type[BaseModel], evidence: list[dict], *,
                            defer_runtime: bool = False) -> type[BaseModel]:
    """Constrain new hosted output, never normalize citations in saved drafts."""
    if not evidence:
        return contract  # Existing no-evidence checks still block approval.
    fields = {}
    for section, field in contract.model_fields.items():
        section_type = field.annotation
        ids = tuple(dict.fromkeys(str(item["chunk_id"]) for item in evidence
                                  if section in (item.get("matched_sections") or [])))
        citation_type = list[Literal[ids]] if ids else list[str]
        overrides = {"content": (section_type.model_fields["content"].annotation, ...),
                     "citations": (citation_type, Field(..., **({} if ids else {"max_length": 0})))}
        records_key = {"npc_archetypes": "npcs", "quest_hooks": "quests"}.get(section)
        if records_key:
            content_type = section_type.model_fields["content"].annotation
            records_type = content_type.model_fields[records_key].annotation
            if ids:
                record_fields = {"source_chunk_ids": (citation_type, Field(min_length=1))}
                if records_key == "quests" and defer_runtime:
                    record_fields["runtime"] = (Literal[None], None)
                variants = get_args(records_type.__args__[0]) or (records_type.__args__[0],)
                record = Union[tuple(create_model("Grounded" + variant.__name__,
                                                  __base__=variant, **record_fields) for variant in variants)]
                records = (list[record], deepcopy(content_type.model_fields[records_key]))
            else:
                records = (records_type, Field(max_length=0))
            content = create_model("Grounded" + content_type.__name__, __base__=content_type,
                                   **{records_key: records})
            overrides["content"] = (content, ...)
        if section == "unity_runtime_preview" and defer_runtime:
            empty_content = create_model("DeferredRuntimeContent", __config__=ConfigDict(extra="forbid"))
            overrides.update(content=(empty_content, Field(default_factory=empty_content)),
                             citations=(list[str], Field(..., max_length=0)))
        fields[section] = (create_model("Grounded" + section.title().replace("_", ""),
                                       __base__=section_type, __config__=ConfigDict(json_schema_extra=_cited_section_schema),
                                       __validators__={"require_content_citations": model_validator(mode="after")(_require_content_citations)},
                                       **overrides), ...)
    return create_model("Grounded" + contract.__name__, __base__=contract, **fields)


def revision_response_model(targets: list[str], *, generated: bool = False, design_contract_version: int = 1,
                            fresh_dialogue: bool = False) -> type[BaseModel]:
    """A closed partial blueprint contract; models cannot add unrelated sections."""
    if not targets or any(target not in BLUEPRINT_SECTION_KEYS for target in targets):
        raise ValueError("Select at least one valid blueprint section for revision.")
    contract = GeneratedBlueprintContent if generated else BlueprintContent
    if design_contract_version == 2:
        contract = (FreshGovernedBlueprintContent if fresh_dialogue else
                    GeneratedGovernedBlueprintContent if generated else GovernedBlueprintContent)
    return create_model(
        "BlueprintSectionRevision",
        __base__=BlueprintSectionRevision,
        **{target: (contract.model_fields[target].annotation, ...) for target in dict.fromkeys(targets)},
    )


class DefectReference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    artifact_path: str = Field(min_length=2, max_length=1000, pattern=r"^/")
    artifact_value: Any
    evidence_chunk_id: str | None
    evidence_quote: str | None


class CritiqueReference(DefectReference):
    replacement: Any


class CritiqueFinding(BaseModel):
    severity: Literal["high", "medium", "low"]
    section: str
    issue: str
    recommendation: str
    reference: CritiqueReference | DefectReference | None = None

    @model_serializer(mode="wrap")
    def preserve_legacy_shape(self, handler):
        result = handler(self)
        if self.reference is None:
            result.pop("reference", None)
        return result


SourceCoverageStatus = Literal["covered", "missing", "not_specified"]


class CritiqueSourceCoverage(BaseModel):
    """Model assessments of supplied excerpts, not verified coverage scores."""
    model_config = ConfigDict(extra="forbid")
    summary: SourceCoverageStatus
    narrative_direction: SourceCoverageStatus
    art_style_direction: SourceCoverageStatus
    npc_archetypes: SourceCoverageStatus
    npc_memory_design: SourceCoverageStatus
    level_design_suggestions: SourceCoverageStatus
    gameplay_systems: SourceCoverageStatus
    quest_hooks: SourceCoverageStatus
    unity_runtime_preview: Literal["covered", "missing", "not_specified", "deferred"]


class CritiqueOutput(BaseModel):
    review_mode: Literal["defect_detection"] | None = None
    source_coverage: CritiqueSourceCoverage | None = None
    verdict: Literal["ready_for_review", "needs_revision"]
    findings: list[CritiqueFinding] = Field(default_factory=list)
    summary: str

    @model_serializer(mode="wrap")
    def preserve_legacy_shape(self, handler):
        result = handler(self)
        if self.review_mode is None:
            result.pop("review_mode", None)
        if self.source_coverage is None:
            result.pop("source_coverage", None)
        return result


class GovernedCritiqueFinding(CritiqueFinding):
    section: BlueprintSectionKey
    reference: CritiqueReference

    @model_validator(mode="after")
    def reference_section(self):
        root = f"/{self.section}/content"
        if self.reference.artifact_path != root and not self.reference.artifact_path.startswith(root + "/"):
            raise ValueError("Critic reference must identify content in its declared section.")
        return self


class GovernedCritiqueOutput(CritiqueOutput):
    source_coverage: CritiqueSourceCoverage
    findings: list[GovernedCritiqueFinding]

    @model_validator(mode="after")
    def require_omission_findings(self):
        for section, status in self.source_coverage.model_dump().items():
            if status == "missing":
                if self.verdict != "needs_revision" or not any(
                    finding.section == section and finding.reference.evidence_chunk_id
                    and finding.reference.evidence_quote for finding in self.findings
                ):
                    raise ValueError("Missing source-backed content requires needs_revision and a source-anchored finding.")
        return self


def artifact_content_paths(artifact: dict[str, Any], *, include_records: bool = False) -> list[str]:
    """Existing content paths; whole records opt in for server-bound review."""
    paths = []

    def visit(value, path, record=False):
        # Whole populated records invite abbreviated copies; collections still support missing-item findings.
        if include_records or not (record and isinstance(value, dict) and value):
            paths.append(path)
        if isinstance(value, dict):
            for key, child in value.items():
                visit(child, path + "/" + key.replace("~", "~0").replace("/", "~1"))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{path}/{index}", record=True)

    for section in artifact:
        visit(artifact[section]["content"], f"/{section}/content", record=True)
    return paths


def critique_response_model(artifact: dict[str, Any], *, defer_runtime: bool = False) -> type[GovernedCritiqueOutput]:
    """Bind fresh reviews to fields and collections without repairing model claims."""
    paths = artifact_content_paths(artifact)
    reference = create_model("ArtifactCritiqueReference", __base__=DefectReference,
                             artifact_path=(Literal[tuple(paths)], ...))
    finding = create_model("ArtifactCritiqueFinding", __base__=GovernedCritiqueFinding,
                           reference=(reference, ...))
    # Runtime scope is human-owned; this label never certifies runtime content or dismisses findings.
    coverage = create_model("ArtifactCritiqueSourceCoverage", __base__=CritiqueSourceCoverage,
                            unity_runtime_preview=(Literal["deferred"] if defer_runtime is True
                                                   else Literal["covered", "missing", "not_specified"], ...))
    return create_model("ArtifactCritiqueOutput", __base__=GovernedCritiqueOutput,
                        review_mode=(Literal["defect_detection"], ...),
                        source_coverage=(coverage, ...),
                        findings=(list[finding], ...))


class SectionCritiqueOutput(BaseModel):
    """Fresh wire contract; stored reviews keep their existing canonical shape."""
    model_config = ConfigDict(extra="forbid")
    review_mode: Literal["defect_detection"]
    source_coverage: BaseModel
    findings: list[BaseModel]
    summary: str

    @model_validator(mode="after")
    def source_anchored_omissions(self):
        for section, coverage in self.source_coverage.model_dump().items():
            findings = [finding.model_dump() for finding in self.findings
                        if finding.reference.artifact_path.split("/")[1] == section]
            if coverage == "missing" and (not findings or any(
                finding["reference"]["evidence_index"] is None for finding in findings)):
                raise ValueError("Missing source-backed content requires source-anchored findings.")
        return self

    def as_critique(self, artifact: dict[str, Any], evidence: list[dict[str, Any]]) -> dict[str, Any]:
        from app.design_agent.finding_reviews import _artifact_value

        findings = [finding.model_dump() for finding in self.findings]
        for finding in findings:
            reference = finding["reference"]
            index = reference.pop("evidence_index")
            source = evidence[index] if index is not None else None
            finding["section"] = reference["artifact_path"].split("/")[1]
            reference["artifact_value"] = _artifact_value(artifact, reference["artifact_path"])
            reference["evidence_chunk_id"] = source["chunk_id"] if source else None
            reference["evidence_quote"] = source["content"] if source else None
        return CritiqueOutput.model_validate({
            "review_mode": self.review_mode, "summary": self.summary,
            "source_coverage": self.source_coverage.model_dump(),
            "findings": findings, "verdict": "needs_revision" if findings else "ready_for_review",
        }).model_dump()


def section_critique_response_model(artifact: dict[str, Any], evidence: list[dict[str, Any]], *, defer_runtime: bool = False) -> type[SectionCritiqueOutput]:
    from app.design_agent.grounding import _has_design_content

    if any(not isinstance(item.get(key), str) or not item[key].strip()
           for item in evidence for key in ("chunk_id", "content")):
        raise ValueError("Critic references require non-empty frozen IDs and excerpts.")
    # Server-bound values cannot be abbreviated by the critic, including whole records.
    paths = artifact_content_paths(artifact, include_records=True)
    reference = create_model("FrozenCritiqueReference", __config__=ConfigDict(extra="forbid"),
        artifact_path=(Literal[tuple(paths)], ...),
        evidence_index=(int | None if evidence else type(None),
                        Field(strict=True, ge=0, le=len(evidence) - 1) if evidence else ...))
    finding = create_model("SelectedFieldFinding", __config__=ConfigDict(extra="forbid"),
        severity=(Literal["high", "medium", "low"], ...), issue=(str, ...), recommendation=(str, ...),
        reference=(reference, ...))
    fields = {}
    for section in BLUEPRINT_SECTION_KEYS:
        deferred = section == "unity_runtime_preview" and defer_runtime is True
        coverage = (Literal["covered", "missing", "not_specified"] if _has_design_content(artifact[section]["content"])
                    else Literal["missing", "not_specified"])
        fields[section] = (Literal["deferred"] if deferred else coverage, ...)
    coverage = create_model("SectionCoverage", __config__=ConfigDict(extra="forbid"), **fields)
    return create_model("ArtifactSectionCritique", __base__=SectionCritiqueOutput,
                        source_coverage=(coverage, ...), findings=(list[finding], ...))


class ProposalConfirmation(BaseModel):
    """A designer's acceptance of one labelled proposal, never a GDD citation."""

    model_config = ConfigDict(extra="forbid")
    section: Literal["npc_archetypes", "quest_hooks"]
    record_id: str = Field(min_length=1, max_length=500)
    assumption: str = Field(min_length=1, max_length=4000)


class ResumeDecision(BaseModel):
    decision: Literal["approve", "reject"]
    reason: str | None = None
    reviewer_user_id: str | None = None
    reviewer_label: str = "local_developer"
    target_sections: list[BlueprintSectionKey] | None = Field(default=None, min_length=1, max_length=9)
    artifact_id: UUID | None = None
    confirmed_proposals: list[ProposalConfirmation] = Field(default_factory=list, max_length=64)

    @model_validator(mode="after")
    def require_confirmation_scope(self):
        if self.confirmed_proposals and (self.decision != "approve" or self.artifact_id is None):
            raise ValueError("Proposal confirmation requires approval and the exact artifact_id.")
        return self

    def require_current_artifact(self, artifact_id: UUID | str) -> None:
        if self.artifact_id is not None and str(self.artifact_id) != str(artifact_id):
            raise ValueError("Review the current draft; this confirmation targets an older artifact.")


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
    fresh_dialogue: bool
    dialogue_policy: str | None
    defer_runtime: bool
    allow_unspecified_memory: bool
    design_contract_version: int
    current_artifact_id: str
    current_artifact_version: int
    current_artifact: dict[str, Any]
    critique_id: str
    critique: dict[str, Any]
    review_decision: str
    rejection_reason: str
    revision_targets: list[str]
    revision_failed: bool
    finalization_failed: bool
    confirmed_proposals: list[dict[str, Any]]
    final_artifact_id: str
    blueprint_id: str
