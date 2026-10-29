"""Model-authored content assembled into the unchanged reviewable contract."""
import copy
import re
from typing import Annotated, Any, Literal, Union, get_args, get_origin

from pydantic import BaseModel, ConfigDict, Field, create_model, model_validator
from pydantic.json_schema import SkipJsonSchema

from app.design_agent.contracts import (
    BlueprintSection, BlueprintSectionRevision, GeneratedNPCDesignCandidate, GovernedBlueprintContent,
    GeneratedGovernedBlueprintContent, QuestDesignCandidate, QuestEventAction, QuestRuntimeBinding,
    artifact_content_paths, grounded_response_model,
)


class DraftObjective(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    objective: str = Field(min_length=1, max_length=1000)
    completion_action: QuestEventAction


def _dialogue_schema(schema: dict) -> None:
    # Native guided decoding needs self-contained branches, not required-only fields.
    schema["anyOf"] = [
        {"properties": {**schema["properties"], "stage": {"enum": stages}, "quest_index": index},
         "required": schema["required"], "additionalProperties": False}
        for stages, index in (
            (["greeting", "other"], {"type": "null"}),
            (["greeting", "progress", "completion", "failed", "other"], {"type": "integer", "enum": [0, 1]}),
        )
    ]


class DraftDialogue(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, json_schema_extra=_dialogue_schema)
    stage: Literal["greeting", "progress", "completion", "failed", "other"]
    quest_index: int | None = Field(ge=0, le=1, strict=True)
    situation: str = Field(min_length=1, max_length=500)
    text: str = Field(min_length=1, max_length=1000)
    repeat_policy: str = Field(min_length=1, max_length=500)


class DraftNPC(GeneratedNPCDesignCandidate):
    dialogue_triggers: list[DraftDialogue] = Field(min_length=1, max_length=3)


class DraftNPCContent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    npcs: list[DraftNPC] = Field(max_length=2)


class DraftNPCSection(BlueprintSection):
    content: DraftNPCContent


class DraftQuest(QuestDesignCandidate):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    id: SkipJsonSchema[None] = None
    state_contract: SkipJsonSchema[None] = None
    runtime: QuestRuntimeBinding | None = None
    reward: str | None = Field(..., min_length=1, max_length=1000)
    objectives: list[DraftObjective] = Field(min_length=1, max_length=4)
    failure_states: list[QuestEventAction] = Field(default_factory=list)
    restart_action: QuestEventAction | None = None


class DraftQuestContent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    quests: list[DraftQuest] = Field(max_length=2)


class DraftQuestSection(BlueprintSection):
    content: DraftQuestContent


class DraftLevel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=1)
    focus: str = Field(min_length=1)


class DraftSystem(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)


def _design_section(name: str, **fields):
    # Closed, required content fields let native decoding produce useful design data, not arbitrary empty objects.
    content = create_model(name + "Content", __config__=ConfigDict(extra="forbid", str_strip_whitespace=True), **fields)
    return create_model(name + "Section", __base__=BlueprintSection, content=(content, ...))


SummaryDraftSection = _design_section("DraftSummary", description=(str | None, Field(..., min_length=1)))
NarrativeDraftSection = _design_section("DraftNarrative", lore_background=(str | None, Field(..., min_length=1)), themes=(list[str], ...))
ArtDraftSection = _design_section("DraftArt", visual_theme=(str | None, Field(..., min_length=1)), visual_notes=(list[str], ...))
MemoryDraftSection = _design_section("DraftMemory", rules=(list[str], ...))
LevelsDraftSection = _design_section("DraftLevels", levels=(list[DraftLevel], ...))
SystemsDraftSection = _design_section("DraftSystems", systems=(list[DraftSystem], ...))


class ContentBlueprintDraft(GovernedBlueprintContent):
    summary: SummaryDraftSection
    narrative_direction: NarrativeDraftSection
    art_style_direction: ArtDraftSection
    npc_memory_design: MemoryDraftSection
    level_design_suggestions: LevelsDraftSection
    gameplay_systems: SystemsDraftSection
    npc_archetypes: DraftNPCSection
    quest_hooks: DraftQuestSection

    @model_validator(mode="after")
    def dialogue_quest_references(self):
        quests = self.quest_hooks.content.quests
        for npc in self.npc_archetypes.content.npcs:
            for line in npc.dialogue_triggers:
                if line.quest_index is None:
                    if line.stage in {"progress", "completion", "failed"}:
                        raise ValueError("Quest dialogue needs an existing quest_index.")
                elif line.quest_index >= len(quests):
                    raise ValueError("Dialogue quest_index does not identify a returned quest.")
                elif line.stage == "failed" and not quests[line.quest_index].failure_states:
                    raise ValueError("Failed dialogue needs a declared failure condition.")
        return self


class RevisionDialogue(DraftDialogue):
    trigger: str | None = Field(..., min_length=1)


class RevisionNPC(DraftNPC):
    dialogue_triggers: list[RevisionDialogue] = Field(min_length=1, max_length=3)


class RevisionQuest(DraftQuest):
    id: str | None = Field(..., min_length=1)
    failure_states: list[QuestEventAction]
    restart_action: QuestEventAction | None


class ContentBlueprintRevision(BlueprintSectionRevision):
    """Closed content-only response; identities select existing records, never engine bindings."""


class ContentFieldChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    artifact_path: str
    replacement: Any


class ContentFieldRevision(ContentBlueprintRevision):
    changes: list[ContentFieldChange] = Field(min_length=1, max_length=32)


def content_field_revision_model(targets: list[str], artifact: dict) -> type[BaseModel]:
    if not targets or any(target not in ContentBlueprintDraft.model_fields for target in targets):
        raise ValueError("Select valid content revision sections.")
    projected = project_content_revision(artifact, targets)
    paths = [path for path in artifact_content_paths(projected)
             if path.rsplit("/", 1)[-1] not in {"id", "trigger"}]
    paths.extend(f"/{section}/{field}" for section in targets for field in ("citations", "confidence", "warnings"))
    contract = content_revision_model(targets, artifact).model_validate(projected)
    types = {}
    for path in paths:
        value, annotation = contract, type(contract)
        for part in path.split("/")[1:]:
            part = part.replace("~1", "/").replace("~0", "~")
            if isinstance(value, BaseModel):
                annotation = type(value).model_fields[part].rebuild_annotation()
                value = getattr(value, part)
            else:
                while get_origin(annotation) is Annotated:
                    annotation = get_args(annotation)[0]
                args = get_args(annotation)
                annotation = args[0 if isinstance(value, list) else 1] if args else Any
                value = value[int(part)] if isinstance(value, list) else value[part]
        types.setdefault(annotation, []).append(path)
    # Group paths sharing the declared type; null/empty values never define their type.
    variants = [create_model(f"TypedContentFieldChange{index}", __base__=ContentFieldChange,
                             artifact_path=(Literal[tuple(allowed)], ...), replacement=(annotation, ...))
                for index, (annotation, allowed) in enumerate(types.items())]
    change = Union[tuple(variants)]
    return create_model("ScopedContentFieldRevision", __base__=ContentFieldRevision,
                        changes=(list[change], Field(min_length=1, max_length=32)))


def assemble_content_field_revision(artifact: dict, content: dict, targets: list[str], evidence: list[dict],
                                    *, defer_runtime: bool = False) -> dict:
    changes = content_field_revision_model(targets, artifact).model_validate(content).model_dump()["changes"]
    wire, identities = project_content_revision(artifact, targets), copy.deepcopy(artifact)
    seen = []
    for change in changes:
        path = change["artifact_path"]
        if any(path == prior or path.startswith(prior + "/") or prior.startswith(path + "/") for prior in seen):
            raise ValueError("Revision field changes overlap or repeat.")
        seen.append(path)
        parts = [part.replace("~1", "/").replace("~0", "~") for part in path.split("/")[1:]]
        parent = wire
        for part in parts[:-1]:
            parent = parent[int(part)] if isinstance(parent, list) else parent[part]
        parent[int(parts[-1]) if isinstance(parent, list) else parts[-1]] = copy.deepcopy(change["replacement"])
        # A display-text replacement keeps that objective's existing state keys.
        if match := re.fullmatch(r"/quest_hooks/content/quests/(\d+)/objectives/(\d+)/objective", path):
            quest, objective = map(int, match.groups())
            old = identities["quest_hooks"]["content"]["quests"][quest]
            old["objectives"][objective] = change["replacement"]
            old["state_contract"]["objectives"][objective]["objective"] = change["replacement"]
    wire = grounded_response_model(content_revision_model(targets, artifact), evidence,
                                   defer_runtime=defer_runtime).model_validate(wire).model_dump()
    return assemble_content_revision(identities, wire)


def content_revision_model(targets: list[str], artifact: dict) -> type[BaseModel]:
    if not targets or any(target not in ContentBlueprintDraft.model_fields for target in targets):
        raise ValueError("Select valid content revision sections.")
    records = {"npc_archetypes": ("npcs", RevisionNPC), "quest_hooks": ("quests", RevisionQuest)}
    fields = {}
    for target in dict.fromkeys(targets):
        section = ContentBlueprintDraft.model_fields[target].annotation
        if target in records:
            key, record = records[target]
            if key == "npcs":
                new_line = create_model("NewRevisionDialogue", __base__=RevisionDialogue, trigger=(type(None), ...))
                variants = [create_model("NewRevisionNPC", __base__=RevisionNPC,
                    dialogue_triggers=(list[new_line], Field(min_length=1, max_length=3)))]
                for index, npc in enumerate(artifact["npc_archetypes"]["content"]["npcs"]):
                    triggers = tuple(line["trigger"] for line in npc["dialogue_triggers"])
                    selector = Literal[triggers] | None if triggers else type(None)
                    line = create_model(f"ExistingRevisionDialogue{index}", __base__=RevisionDialogue, trigger=(selector, ...))
                    variants.append(create_model(f"ExistingRevisionNPC{index}", __base__=RevisionNPC,
                        name=(Literal[npc["name"]], ...), dialogue_triggers=(list[line], Field(min_length=1, max_length=3))))
                record = Union[tuple(variants)]
            else:
                ids = tuple(quest["id"] for quest in artifact["quest_hooks"]["content"]["quests"])
                selector = Literal[ids] | None if ids else type(None)
                record = create_model("RevisionQuest", __base__=RevisionQuest, id=(selector, ...))
            content = create_model("Revision" + key.title(), __config__=ConfigDict(extra="forbid"),
                                   **{key: (list[record], Field(max_length=2))})
            section = create_model("Revision" + target.title().replace("_", ""), __base__=section, content=(content, ...))
        fields[target] = (section, ...)
    return create_model("ScopedContentRevision", __base__=ContentBlueprintRevision, **fields)


def project_content_revision(artifact: dict, targets: list[str], quest_ids: list[str] | None = None) -> dict:
    """Remove exact generated duplicates, never authored notes or source facts."""
    from app.design_agent.grounding import _add_integration_steps

    containers = {"npc_archetypes": "npcs", "quest_hooks": "quests"}
    records = {section: GovernedBlueprintContent.model_fields[section].annotation.model_validate(
        artifact.get(section, {"content": {key: []}})).model_dump() for section, key in containers.items()}
    generated = copy.deepcopy(records)
    for section, key in containers.items():
        for record in generated[section]["content"][key]:
            record["implementation_notes"] = []
    _add_integration_steps(generated, design_contract_version=2)
    ids = quest_ids if quest_ids is not None else [quest["id"] for quest in records["quest_hooks"]["content"]["quests"]]
    projected = {target: copy.deepcopy(records.get(target, artifact[target])) for target in targets}
    for section, key in containers.items():
        for index, record in enumerate(projected.get(section, {}).get("content", {}).get(key, [])):
            duplicates = generated[section]["content"][key][index]["implementation_notes"]
            record["implementation_notes"] = [note for note in record["implementation_notes"] if note not in duplicates]
            if section == "npc_archetypes":
                record.pop("dialogue_hooks", None)
                record.pop("fresh_dialogue", None)
                record["dialogue_triggers"] = [{
                    **{key: line[key] for key in ("trigger", "situation", "text", "repeat_policy")},
                    "stage": "failed" if line["eligibility"]["lifecycle"] == "failed" else line["eligibility"]["stage"],
                    "quest_index": ids.index(line["eligibility"]["quest_id"]) if line["eligibility"]["quest_id"] is not None else None,
                } for line in record["dialogue_triggers"]]
            else:
                contract = record.pop("state_contract")
                actions = contract["event_actions"]
                record["objectives"] = [{"objective": item["objective"], "completion_action": actions[item["event"]]}
                                        for item in contract["objectives"]]
                failures = (contract.get("failure") or {}).get("events", [])
                # Historical short labels may already have a readable, saved action.
                record["failure_states"] = [actions[failures[index]] if len(cause.split()) < 2 and index < len(failures)
                                            else cause for index, cause in enumerate(record["failure_states"])]
                record["restart_action"] = actions[contract["restart"]["event"]] if contract["restart"] else None
    return projected


def _unused_key(stem: str, used: set[str]) -> str:
    key, suffix = stem, 2
    while key in used:
        key = f"{stem}_{suffix}"
        suffix += 1
    used.add(key)
    return key


def assemble_content_draft(content: dict) -> dict:
    """Derive mechanical keys only; never fill missing facts, citations or actions."""
    draft = ContentBlueprintDraft.model_validate(content).model_dump()
    _assemble_records(draft)
    return GeneratedGovernedBlueprintContent.model_validate(draft).model_dump()


def assemble_content_revision(artifact: dict, content: dict) -> dict:
    selected = content_revision_model(list(content), artifact).model_validate(content).model_dump()
    _assemble_records(selected, artifact)
    # Validate references against the whole draft, but never normalize an unselected section.
    merged = GovernedBlueprintContent.model_validate({**artifact, **selected}).model_dump()
    return {target: merged[target] for target in selected}


def _assemble_records(draft: dict, previous: dict | None = None) -> None:
    old_quests = (previous or {}).get("quest_hooks", {}).get("content", {}).get("quests", [])
    old_by_id = {quest["id"]: (index, quest) for index, quest in enumerate(old_quests, 1)}
    used_ids, seen_ids = set(old_by_id), set()
    quests = draft.get("quest_hooks", {}).get("content", {}).get("quests", old_quests)
    for position, quest in enumerate(draft.get("quest_hooks", {}).get("content", {}).get("quests", []), 1):
        identity = quest["id"]
        if previous and identity is not None and (identity not in old_by_id or identity in seen_ids):
            raise ValueError("Revision quest identity is foreign or duplicated.")
        if identity is not None:
            seen_ids.add(identity)
        index, old = old_by_id.get(identity, (len(old_quests) + position, {}))
        quest["id"] = identity or _unused_key(f"quest_{index}", used_ids)
        old_contract = old.get("state_contract") or {}
        old_objectives = {item["objective"]: item for item in old_contract.get("objectives", [])}
        used = {item["flag"] for item in old_contract.get("objectives", [])} | set(old_contract.get("event_actions", {}))
        used.update(event.removesuffix("_completed") for event in old_contract.get("event_actions", {}))
        objectives = []
        for number, item in enumerate(quest["objectives"], 1):
            old_item = old_objectives.get(item["objective"])
            if old_item is None:
                # Unchanged behavior can identify a reworded objective; never guess by position.
                matches = [candidate for candidate in old_objectives.values()
                           if old_contract.get("event_actions", {}).get(candidate["event"]) == item["completion_action"]
                           and candidate["objective"] not in {entry["objective"] for entry in quest["objectives"]}]
                if len(matches) == 1 and not any(entry["flag"] == matches[0]["flag"] for entry in objectives):
                    old_item = matches[0]
            flag = old_item["flag"] if old_item else _unused_key(f"q{index}_objective_{number}", used)
            objectives.append({"objective": item["objective"], "flag": flag,
                               "event": old_item["event"] if old_item else f"{flag}_completed"})
        actions = {state["event"]: item["completion_action"]
                   for state, item in zip(objectives, quest["objectives"])}
        flags = [item["flag"] for item in objectives]
        old_failures = dict(zip(old.get("failure_states", []), (old_contract.get("failure") or {}).get("events", [])))
        for event in list(old_failures.values()):
            old_failures.setdefault(old_contract["event_actions"][event], event)
        failures = [old_failures[cause] if cause in old_failures else _unused_key(f"q{index}_failure_{number}", used)
                    for number, cause in enumerate(quest["failure_states"], 1)]
        actions.update({event: old_contract["event_actions"][event] if cause in old_failures else cause
                        for event, cause in zip(failures, quest["failure_states"])})
        restart_action = quest.pop("restart_action")
        restart_event = ((old_contract.get("restart") or {}).get("event")
                         or _unused_key(f"q{index}_confirmed_restart", used))
        if restart_action is not None:
            actions[restart_event] = restart_action
        quest["objectives"] = [item["objective"] for item in objectives]
        quest["state_contract"] = {
            "version": "1", "objectives": objectives,
            "completion": {"required_flags": flags, "mode": "all", "reevaluate_on": "each_objective_update", "lifecycle": "completed"},
            "failure": {"events": failures, "lifecycle": "failed"} if failures else None,
            "restart": {"event": restart_event, "lifecycle": "active", "clear_flags": flags} if restart_action is not None else None,
            "event_actions": actions,
        }
        quest["assumptions"] = list(dict.fromkeys([*quest["assumptions"],
            "Server-derived quest keys and state bookkeeping are unverified implementation proposals, not engine bindings or source facts."]))
    old_npcs = (previous or {}).get("npc_archetypes", {}).get("content", {}).get("npcs", [])
    old_by_name = {npc["name"]: (index, npc) for index, npc in enumerate(old_npcs, 1)}
    used_triggers = {line["trigger"] for npc in old_npcs for line in npc["dialogue_triggers"]}
    for position, npc in enumerate(draft.get("npc_archetypes", {}).get("content", {}).get("npcs", []), 1):
        npc_index, old = old_by_name.get(npc["name"], (len(old_npcs) + position, {}))
        if previous is not None:
            npc["fresh_dialogue"] = old.get("fresh_dialogue", False)
        old_triggers = {line["trigger"] for line in old.get("dialogue_triggers", [])}
        seen_triggers = set()
        mappings = []
        for number, line in enumerate(npc["dialogue_triggers"], 1):
            stage = line["stage"]
            quest_index = line["quest_index"]
            if quest_index is not None and (quest_index >= len(quests) or (stage == "failed" and not quests[quest_index]["state_contract"]["failure"])):
                raise ValueError("Revision dialogue references an absent quest or failure transition.")
            trigger = line.get("trigger")
            if trigger is not None and (trigger not in old_triggers or trigger in seen_triggers):
                raise ValueError("Revision dialogue identity is foreign or duplicated.")
            trigger = trigger or _unused_key(f"npc_{npc_index}_{stage}_{number}", used_triggers)
            seen_triggers.add(trigger)
            lifecycle = (None if quest_index is None else "completed" if stage == "completion"
                         else "failed" if stage == "failed" else "active")
            progress = ("any" if quest_index is None or stage == "other" else
                        "complete" if stage == "completion" else "incomplete")
            mappings.append({"trigger": trigger,
                **{key: line[key] for key in ("situation", "text", "repeat_policy")},
                "eligibility": {"stage": "other" if stage == "failed" else stage,
                    "quest_id": quests[quest_index]["id"] if quest_index is not None else None,
                    "lifecycle": lifecycle, "progress": progress}})
        npc["dialogue_triggers"] = mappings
        npc.pop("dialogue_hooks", None)
        npc["assumptions"] = list(dict.fromkeys([*npc["assumptions"],
            "Server-derived dialogue keys and eligibility are unverified implementation proposals, not engine bindings or source facts."]))
