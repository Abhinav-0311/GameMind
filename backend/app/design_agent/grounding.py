import copy
import re
from typing import Any

from app.design_agent.contracts import BLUEPRINT_SECTION_KEYS, BlueprintContent


SECTION_KEYWORDS = (
    ("level", "level_design_suggestions"),
    ("npc", "npc_archetypes"),
    ("character", "npc_archetypes"),
    ("memory", "npc_memory_design"),
    ("quest", "quest_hooks"),
    ("mission", "quest_hooks"),
    ("gameplay", "gameplay_systems"),
    ("mechanic", "gameplay_systems"),
    ("art", "art_style_direction"),
    ("visual", "art_style_direction"),
    ("narrative", "narrative_direction"),
    ("story", "narrative_direction"),
    ("runtime", "unity_runtime_preview"),
    ("unity", "unity_runtime_preview"),
)

_EVIDENCE_ECHO_KEYS = {
    "chunk_id",
    "document_id",
    "chunk_index",
    "matched_sections",
    "section_similarities",
    "similarity",
    "content_truncated",
}
_TRAILING_FRAGMENT_WORDS = {"a", "an", "and", "as", "at", "for", "in", "of", "or", "the", "to", "with", "you"}
_DEPENDENCY_STOPWORDS = {
    "a", "an", "after", "and", "before", "complete", "completed", "completing",
    "finish", "finished", "finishing", "has", "have", "had", "level", "mission",
    "player", "players", "quest", "require", "required", "requires", "stage", "task",
    "the", "to", "unlock", "unlocked", "unlocks",
}


def _cited_evidence_text(record: dict[str, Any], evidence_by_id: dict[str, dict[str, Any]]) -> str:
    return " ".join(
        str(evidence_by_id[source_id].get("content") or "")
        for source_id in record["source_chunk_ids"]
        if source_id in evidence_by_id
    ).casefold()


def _reject_unsupported_quest_details(
    quest: dict[str, Any],
    evidence_by_id: dict[str, dict[str, Any]],
) -> None:
    """Keep model proposals out of factual quest fields unless sources support them."""
    source_text = _cited_evidence_text(quest, evidence_by_id)
    factual_values = (
        [quest["objective"], quest.get("reward") or ""]
        + quest["objectives"]
        + quest["failure_states"]
        + quest["dependencies"]
        + quest["dialogue_hooks"]
        + quest["implementation_notes"]
    )
    unsupported_numbers = sorted({
        number
        for value in factual_values
        for number in re.findall(r"\d+(?:\.\d+)?%?", value)
        if number.casefold() not in source_text
    })
    if unsupported_numbers:
        raise ValueError(
            f"Quest '{quest['title']}' presents unsupported numeric detail(s) as facts: "
            + ", ".join(unsupported_numbers)
            + ". Move proposals to assumptions or cite supporting evidence."
        )

    for dependency in quest["dependencies"]:
        meaningful_words = {
            word.casefold()
            for word in re.findall(r"[A-Za-z][A-Za-z'-]*", dependency)
            if word.casefold() not in _DEPENDENCY_STOPWORDS
        }
        missing_words = sorted(word for word in meaningful_words if word not in source_text)
        if missing_words:
            raise ValueError(
                f"Quest '{quest['title']}' uses an unsupported dependency: '{dependency}'. "
                "Move it to assumptions or cite supporting evidence."
            )


def _add_integration_steps(validated: dict[str, Any]) -> None:
    """Attach safe, engine-neutral implementation steps to reviewable artifacts."""
    for npc in validated["npc_archetypes"]["content"]["npcs"]:
        generated_steps = [
            f"Create a stable NPC profile for '{npc['name']}' and retain its source_chunk_ids in the review trace.",
            "Use dialogue hooks as first-contact lines; keep scene triggers and presentation client-side.",
        ]
        if npc["assumptions"]:
            generated_steps.append("Do not implement listed assumptions until a designer confirms them.")
        npc["implementation_notes"] = list(dict.fromkeys(npc["implementation_notes"] + generated_steps))

    for quest in validated["quest_hooks"]["content"]["quests"]:
        generated_steps = [
            f"Use '{quest['id']}' as the stable design key and map objectives in their listed order to game events.",
            "Map failure states to explicit quest-state transitions; do not infer rewards or prerequisites from assumptions.",
        ]
        if quest["assumptions"]:
            generated_steps.append("Do not implement listed assumptions until a designer confirms them.")
        quest["implementation_notes"] = list(dict.fromkeys(quest["implementation_notes"] + generated_steps))


def assess_artifact_quality(content: dict[str, Any]) -> dict[str, Any]:
    """Return transparent, deterministic review signals before human approval.

    This is intentionally a narrow quality check. It confirms structured
    completeness and traceability, but never claims that it can replace a
    designer's judgment of creative quality.
    """
    validated = BlueprintContent.model_validate(content).model_dump()
    npcs = validated["npc_archetypes"]["content"]["npcs"]
    quests = validated["quest_hooks"]["content"]["quests"]
    records = [*npcs, *quests]
    total_records = len(records)
    cited_records = sum(bool(record["source_chunk_ids"]) for record in records)
    actionable_npcs = sum(bool(npc["dialogue_hooks"]) for npc in npcs)
    actionable_quests = sum(
        bool(quest["objectives"] and quest["failure_states"] and quest["dependencies"])
        for quest in quests
    )
    integration_ready = sum(bool(record["implementation_notes"]) for record in records)
    npc_names = [npc["name"].casefold() for npc in npcs]
    quest_ids = [quest["id"].casefold() for quest in quests]
    duplicate_records = (len(npc_names) != len(set(npc_names))) or (len(quest_ids) != len(set(quest_ids)))
    unresolved = [
        {"record": record.get("name") or record.get("title") or "Untitled record", "assumption": assumption}
        for record in records
        for assumption in record["assumptions"]
    ]

    def ratio(numerator: int, denominator: int) -> float:
        return round(numerator / denominator, 4) if denominator else 0.0

    completeness_total = len(npcs) + len(quests)
    completeness = ratio(actionable_npcs + actionable_quests, completeness_total)
    grounding = ratio(cited_records, total_records)
    integration = ratio(integration_ready, total_records)
    consistency = 0.0 if duplicate_records else 1.0
    metrics = [
        {"key": "grounding", "label": "Grounding", "value": grounding, "passed": grounding == 1.0, "detail": "Every NPC and quest cites frozen GDD evidence."},
        {"key": "completeness", "label": "Completeness", "value": completeness, "passed": completeness == 1.0, "detail": "NPCs need dialogue hooks; quests need objectives, failure states, and dependencies."},
        {"key": "consistency", "label": "Contradiction checks", "value": consistency, "passed": consistency == 1.0, "detail": "Checks for duplicate NPC names and quest IDs; human review still assesses narrative conflicts."},
        {"key": "integration_readiness", "label": "Integration readiness", "value": integration, "passed": integration == 1.0 and not unresolved, "detail": "Each record has integration steps and no unresolved assumptions remain."},
    ]
    blockers = [metric["label"] for metric in metrics if not metric["passed"]]
    return {
        "metrics": metrics,
        "overall_score": round(sum(metric["value"] for metric in metrics) / len(metrics), 4),
        "passed": not blockers,
        "blockers": blockers,
        "unresolved_assumptions": unresolved,
    }


def _looks_truncated_dialogue(value: str) -> bool:
    text = value.strip()
    if not text or text[-1] in ".!?\"'":
        return False
    words = re.findall(r"[A-Za-z']+", text.lower())
    return bool(words and words[-1] in _TRAILING_FRAGMENT_WORDS)


def validate_generated_blueprint(
    content: dict[str, Any],
    evidence: list[dict[str, Any]] | None = None,
    require_actionable: bool = False,
    actionable_sections: set[str] | None = None,
) -> dict[str, Any]:
    """Reject retrieval metadata presented as a developer-facing design artifact.

    A sparse GDD is valid: its section can be an empty structured list with a
    warning. What is not valid is returning a raw evidence record in place of
    an NPC, quest, gameplay, or level design section.
    """
    validated = BlueprintContent.model_validate(content).model_dump()
    echoed_sections = []
    for section_name in BLUEPRINT_SECTION_KEYS:
        section_content = validated[section_name]["content"]
        if not isinstance(section_content, dict):
            continue
        keys = set(section_content)
        if "content" in keys and len(keys & _EVIDENCE_ECHO_KEYS) >= 2:
            echoed_sections.append(section_name)

    if echoed_sections:
        raise ValueError(
            "Generated blueprint contains retrieved evidence metadata instead of "
            "structured design content in: " + ", ".join(echoed_sections)
        )
    if evidence is not None:
        allowed_ids = {str(item["chunk_id"]) for item in evidence if item.get("chunk_id")}
        evidence_by_id = {
            str(item["chunk_id"]): item for item in evidence if item.get("chunk_id")
        }
        for section_name, record_key in (("npc_archetypes", "npcs"), ("quest_hooks", "quests")):
            for record in validated[section_name]["content"][record_key]:
                unsupported = set(record["source_chunk_ids"]) - allowed_ids
                if unsupported:
                    raise ValueError(
                        f"{section_name} references source chunks outside the frozen evidence snapshot."
                    )
        for npc in validated["npc_archetypes"]["content"]["npcs"]:
            hooks = npc["dialogue_hooks"]
            complete_hooks = [hook for hook in hooks if not _looks_truncated_dialogue(hook)]
            if len(complete_hooks) != len(hooks):
                npc["dialogue_hooks"] = complete_hooks
                validated["npc_archetypes"]["warnings"].append(
                    f"Removed {len(hooks) - len(complete_hooks)} truncated dialogue hook(s) before review."
                )
        required = actionable_sections or {"npc_archetypes", "quest_hooks"}
        if require_actionable and "npc_archetypes" in required:
            for npc in validated["npc_archetypes"]["content"]["npcs"]:
                if not npc["dialogue_hooks"]:
                    raise ValueError(
                        f"NPC '{npc['name']}' has no cited dialogue hook; omit it or provide a usable hook."
                    )
        if require_actionable and "quest_hooks" in required:
            for quest in validated["quest_hooks"]["content"]["quests"]:
                if not quest["objectives"]:
                    raise ValueError(
                        f"Quest '{quest['title']}' has no ordered objectives; omit it or provide an actionable quest."
                    )
                _reject_unsupported_quest_details(quest, evidence_by_id)
    _add_integration_steps(validated)
    return validated


def review_target(rejection_reason: str) -> str:
    reason = rejection_reason.lower()
    for keyword, section_name in SECTION_KEYWORDS:
        if re.search(rf"\b{keyword}\w*\b", reason):
            return section_name
    return "summary"


def ground_blueprint_citations(
    content: dict[str, Any],
    evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    """Remove citations that are absent or routed to an unrelated section."""
    grounded = copy.deepcopy(content)
    evidence_by_id = {
        str(item["chunk_id"]): item
        for item in evidence
        if item.get("chunk_id")
    }
    for section_name in BLUEPRINT_SECTION_KEYS:
        section = grounded[section_name]
        valid_citations = []
        removed = 0
        for citation in section.get("citations", []):
            citation_id = str(citation)
            item = evidence_by_id.get(citation_id)
            matched_sections = set(item.get("matched_sections") or []) if item else set()
            section_matches = not matched_sections or section_name in matched_sections
            if item and section_matches and citation_id not in valid_citations:
                valid_citations.append(citation_id)
            else:
                removed += 1

        warnings = list(dict.fromkeys(section.get("warnings", [])))
        if removed:
            warnings.append(
                f"Removed {removed} citation(s) that were not retrieved for this section."
            )
        if not valid_citations:
            warnings.append("No section-matched source citation supports this output.")
            section["confidence"] = "Low"
        else:
            similarities = [
                float(
                    evidence_by_id[citation].get("section_similarities", {}).get(
                        section_name,
                        evidence_by_id[citation].get("similarity", 0.0),
                    )
                )
                for citation in valid_citations
            ]
            best_similarity = max(similarities, default=0.0)
            section["confidence"] = (
                "High"
                if best_similarity >= 0.75
                else "Medium"
                if best_similarity >= 0.55
                else "Low"
            )
        section["citations"] = valid_citations
        section["warnings"] = list(dict.fromkeys(warnings))

    return BlueprintContent.model_validate(grounded).model_dump()


def validate_structured_revision(
    before: dict[str, Any],
    after: dict[str, Any],
    rejection_reason: str,
) -> str:
    """Require a targeted content change and reject unrelated section drift."""
    target = review_target(rejection_reason)
    before_validated = BlueprintContent.model_validate(before).model_dump()
    after_validated = BlueprintContent.model_validate(after).model_dump()

    before_target = copy.deepcopy(before_validated[target]["content"])
    after_target = copy.deepcopy(after_validated[target]["content"])
    for metadata_key in ("human_revision", "review_directive", "review_adjustments"):
        before_target.pop(metadata_key, None)
        after_target.pop(metadata_key, None)
    if before_target == after_target:
        raise ValueError(
            f"Revision did not materially change structured section '{target}'."
        )

    changed_unrelated = [
        section_name
        for section_name in BLUEPRINT_SECTION_KEYS
        if section_name != target
        and before_validated[section_name] != after_validated[section_name]
    ]
    if changed_unrelated:
        raise ValueError(
            "Revision changed unrelated sections: " + ", ".join(changed_unrelated)
        )
    return target
