"""Offline/isolated QA experiment; never imported by the production workflow.

The caller supplies an explicitly reviewed scaffold, not model-authored policy
or arbitrary GDD prose. Schema validity is not source support or approval.
"""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, create_model, model_validator

from app.design_agent.contracts import FocusedDeveloperPack, GovernedNPCSection, GovernedQuestSection
from app.design_agent.grounding import _add_integration_steps


Text = Annotated[str, Field(min_length=1, max_length=1000)]


class ContentOnlyDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    greeting: Text
    progress: Text
    completion: Text
    npc_integration_notes: list[Text] = Field(min_length=1, max_length=3)
    quest_integration_notes: list[Text] = Field(min_length=1, max_length=3)
    event_actions: dict[str, Text]


class ContentOnlyScaffold(FocusedDeveloperPack):
    model_config = ConfigDict(extra="forbid")

    npc_archetypes: GovernedNPCSection
    quest_hooks: GovernedQuestSection

    @model_validator(mode="after")
    def require_explicit_qa_scope(self):
        npcs = self.npc_archetypes.content.npcs
        quests = self.quest_hooks.content.quests
        if len(npcs) != 1 or len(quests) != 1:
            raise ValueError("Content-only QA needs exactly one selected NPC and quest.")
        conditions = [mapping.eligibility for mapping in npcs[0].dialogue_triggers]
        if len(conditions) != 3 or {item.stage for item in conditions} != {"greeting", "progress", "completion"}:
            raise ValueError("Explicitly select greeting, progress and completion slots before generation.")
        if any(item.quest_id not in (None, quests[0].id) for item in conditions):
            raise ValueError("Every quest-scoped slot must reference the selected quest.")
        if any(item.lifecycle == "failed" for item in conditions) and not quests[0].state_contract.failure:
            raise ValueError("Failed-attempt dialogue needs a declared failure transition.")
        if quests[0].runtime is not None:
            raise ValueError("Content-only QA cannot activate runtime bindings.")
        return self


def content_response_model(scaffold: dict) -> type[ContentOnlyDraft]:
    fixed = ContentOnlyScaffold.model_validate(scaffold)
    events = list(fixed.quest_hooks.content.quests[0].state_contract.event_actions)
    description = ContentOnlyDraft.model_json_schema()["properties"]["event_actions"]["additionalProperties"]
    def action_schema(schema):
        schema.pop("propertyNames", None)  # NVIDIA rejects this redundant keyword; Literal still validates locally.
        schema.update(properties={event: description for event in events}, required=events, additionalProperties=False)
    actions = Annotated[dict[Literal[tuple(events)], Text], Field(
        min_length=len(events), max_length=len(events), json_schema_extra=action_schema)]
    return create_model("QAContentOnlyResponse", __base__=ContentOnlyDraft, event_actions=(actions, ...))


def assemble_content_pack(scaffold: dict, response: dict) -> dict:
    """Create a new unapproved draft; never repair or mutate saved model output."""
    fixed = ContentOnlyScaffold.model_validate(scaffold)
    authored = content_response_model(scaffold).model_validate(response).model_dump()
    pack = fixed.model_dump()
    npc = pack["npc_archetypes"]["content"]["npcs"][0]
    quest = pack["quest_hooks"]["content"]["quests"][0]
    for mapping in npc["dialogue_triggers"]:
        mapping["text"] = authored[mapping["eligibility"]["stage"]]
        mapping.pop("manual_test", None)
    npc.pop("dialogue_hooks", None)
    quest["state_contract"]["event_actions"] = authored["event_actions"]
    for record, notes, proposal in (
        (npc, authored["npc_integration_notes"], "Generated dialogue and NPC integration notes are unverified proposals requiring narrative and design review."),
        (quest, authored["quest_integration_notes"], "Generated event descriptions and quest integration notes are unverified proposals requiring design review."),
    ):
        record["implementation_notes"] = list(dict.fromkeys([*record["implementation_notes"], *notes]))
        record["assumptions"] = list(dict.fromkeys([*record["assumptions"], proposal]))
    for section in pack.values():
        section["warnings"] = list(dict.fromkeys([*section["warnings"], "Content-only QA draft; not independently critiqued or runtime-approved."]))
    assembled = ContentOnlyScaffold.model_validate(pack).model_dump()
    _add_integration_steps(assembled, design_contract_version=2)
    return assembled
