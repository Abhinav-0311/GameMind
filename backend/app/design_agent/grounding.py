import copy
import re
from typing import Any

from app.design_agent.contracts import BLUEPRINT_SECTION_KEYS, BlueprintContent


SECTION_KEYWORDS = (
    ("summary", "summary"),
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


def _normalise_for_quote_match(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9']+", value.casefold()))


def _mark_generated_dialogue_for_review(
    validated: dict[str, Any],
    evidence_by_id: dict[str, dict[str, Any]],
) -> None:
    """Keep creative dialogue useful, but never present it as a GDD fact.

    A character citation can ground *who* speaks and the scenario, while the
    line itself may be a useful model proposal. Exact source lines stay factual;
    everything else is explicitly a narrative-review draft before runtime use.
    """
    for npc in validated["npc_archetypes"]["content"]["npcs"]:
        source_text = _normalise_for_quote_match(
            _cited_evidence_text(npc, evidence_by_id)
        )
        has_generated_hook = any(
            (normalised := _normalise_for_quote_match(hook))
            and normalised not in source_text
            for hook in npc["dialogue_hooks"]
        )
        if has_generated_hook:
            npc["assumptions"] = list(dict.fromkeys([
                *npc["assumptions"],
                "Generated dialogue hooks are creative drafts and require narrative approval before runtime use.",
            ]))


def _mark_generated_quest_details_for_review(
    validated: dict[str, Any],
    evidence_by_id: dict[str, dict[str, Any]],
) -> None:
    """Expose generated quest design as a proposal when it is not a GDD fact."""
    for quest in validated["quest_hooks"]["content"]["quests"]:
        source_text = _normalise_for_quote_match(
            _cited_evidence_text(quest, evidence_by_id)
        )
        fields = {
            "objective": [quest["objective"]],
            "reward": [quest["reward"]] if quest.get("reward") else [],
            "objectives": quest["objectives"],
            "failure states": quest["failure_states"],
            "dialogue hooks": quest["dialogue_hooks"],
        }
        generated_fields = [
            label
            for label, values in fields.items()
            if any(
                (normalised := _normalise_for_quote_match(value))
                and normalised not in source_text
                for value in values
            )
        ]
        if generated_fields:
            quest["assumptions"] = list(dict.fromkeys([
                *quest["assumptions"],
                "Generated quest "
                + ", ".join(generated_fields)
                + " are creative proposals and require design approval before runtime use.",
            ]))


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


def _enforce_nested_record_citation_closure(
    validated: dict[str, Any],
    evidence_by_id: dict[str, dict[str, Any]],
) -> None:
    """Retain NPC and quest records only when their evidence matches their section.

    A model-provided ``source_chunk_ids`` list proves only that a chunk was in
    the frozen snapshot. It does not prove that the chunk supports an NPC or
    quest claim. This turns records without section-routed evidence into a
    visible, non-executable review blocker instead of quietly retaining them.
    """
    for section_name, record_key, label_key in (
        ("npc_archetypes", "npcs", "name"),
        ("quest_hooks", "quests", "title"),
    ):
        section = validated[section_name]
        retained = []
        blocked_labels = []
        for record in section["content"][record_key]:
            supported_ids = [
                source_id
                for source_id in record["source_chunk_ids"]
                if section_name in set(
                    evidence_by_id.get(source_id, {}).get("matched_sections") or []
                )
            ]
            if not supported_ids:
                blocked_labels.append(str(record.get(label_key) or "Untitled record"))
                continue
            record["source_chunk_ids"] = list(dict.fromkeys(supported_ids))
            retained.append(record)

        section["content"][record_key] = retained
        if blocked_labels:
            section["warnings"].append(
                "Blocked "
                f"{len(blocked_labels)} {record_key} without section-matched frozen evidence: "
                + ", ".join(blocked_labels)
                + ". Add a source-grounded design decision before generating it."
            )
        # Canonicalize the outer citation list from the records that survived
        # closure so the UI, critique, and approval gate see the same evidence.
        section["citations"] = list(dict.fromkeys(
            source_id
            for record in retained
            for source_id in record["source_chunk_ids"]
        ))


def assess_artifact_quality(content: dict[str, Any]) -> dict[str, Any]:
    """Return transparent, deterministic review signals before human approval.

    This is intentionally a narrow quality check. It confirms structured
    completeness and traceability, but never claims that it can replace a
    designer's judgment of creative quality.
    """
    validated = BlueprintContent.model_validate(content).model_dump()
    unsupported_sections = [
        section_name
        for section_name in BLUEPRINT_SECTION_KEYS
        if not validated[section_name]["citations"]
    ]
    npcs = validated["npc_archetypes"]["content"]["npcs"]
    quests = validated["quest_hooks"]["content"]["quests"]
    records = [*npcs, *quests]
    total_records = len(records)
    cited_records = sum(bool(record["source_chunk_ids"]) for record in records)
    actionable_npcs = sum(bool(npc["dialogue_hooks"]) for npc in npcs)
    actionable_quests = sum(
        bool(quest["objectives"] and quest["failure_states"])
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
    record_grounding = ratio(cited_records, total_records)
    section_grounding = ratio(
        len(BLUEPRINT_SECTION_KEYS) - len(unsupported_sections),
        len(BLUEPRINT_SECTION_KEYS),
    )
    grounding = min(record_grounding, section_grounding)
    integration = ratio(integration_ready, total_records)
    # A draft with unresolved implementation assumptions or unsupported
    # sections is not integration-ready, even if every record happens to have
    # mechanical integration steps. Reflect that in the numeric value as well
    # as the pass/fail flag so the UI never shows a perfect score for a blocked
    # artifact.
    if unresolved or unsupported_sections:
        integration = 0.0
    consistency = 0.0 if duplicate_records else 1.0
    metrics = [
        {"key": "grounding", "label": "Grounding", "value": grounding, "passed": grounding == 1.0, "detail": "Every generated section and every NPC or quest record cites frozen GDD evidence."},
        {"key": "completeness", "label": "Completeness", "value": completeness, "passed": completeness == 1.0, "detail": "NPCs need dialogue hooks; quests need objectives and failure states. Dependencies may be empty when the GDD does not support one."},
        {"key": "consistency", "label": "Contradiction checks", "value": consistency, "passed": consistency == 1.0, "detail": "Checks for duplicate NPC names and quest IDs; human review still assesses narrative conflicts."},
        {"key": "integration_readiness", "label": "Integration readiness", "value": integration, "passed": integration == 1.0, "detail": "Each record has integration steps, no unresolved assumptions remain, and every section has source support."},
    ]
    blockers = [metric["label"] for metric in metrics if not metric["passed"]]
    return {
        "metrics": metrics,
        "overall_score": round(sum(metric["value"] for metric in metrics) / len(metrics), 4),
        "passed": not blockers,
        "blockers": blockers,
        "unresolved_assumptions": unresolved,
        "unsupported_sections": unsupported_sections,
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
        _enforce_nested_record_citation_closure(validated, evidence_by_id)
        _mark_generated_dialogue_for_review(validated, evidence_by_id)
        _mark_generated_quest_details_for_review(validated, evidence_by_id)
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
            if not validated["npc_archetypes"]["content"]["npcs"]:
                raise ValueError("No NPC has section-matched frozen evidence for approval.")
            for npc in validated["npc_archetypes"]["content"]["npcs"]:
                if not npc["dialogue_hooks"]:
                    raise ValueError(
                        f"NPC '{npc['name']}' has no cited dialogue hook; omit it or provide a usable hook."
                    )
        if require_actionable and "quest_hooks" in required:
            if not validated["quest_hooks"]["content"]["quests"]:
                raise ValueError("No quest has section-matched frozen evidence for approval.")
            for quest in validated["quest_hooks"]["content"]["quests"]:
                if not quest["objectives"]:
                    raise ValueError(
                        f"Quest '{quest['title']}' has no ordered objectives; omit it or provide an actionable quest."
                    )
                _reject_unsupported_quest_details(quest, evidence_by_id)
    _add_integration_steps(validated)
    return validated


def review_target(rejection_reason: str) -> str:
    """Return the first matched section for legacy single-target callers."""
    return review_targets(rejection_reason)[0]


def review_targets(rejection_reason: str) -> list[str]:
    """Resolve every section explicitly mentioned by a human review reason."""
    reason = rejection_reason.lower()
    targets = []
    for keyword, section_name in SECTION_KEYWORDS:
        if re.search(rf"\b{keyword}\w*\b", reason):
            if section_name not in targets:
                targets.append(section_name)
    return targets or ["summary"]


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
            section_matches = section_name in matched_sections
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
    """Require a human-targeted change and reject unrelated section drift."""
    targets = set(review_targets(rejection_reason))
    before_validated = BlueprintContent.model_validate(before).model_dump()
    after_validated = BlueprintContent.model_validate(after).model_dump()

    changed_targets = []
    for target in targets:
        before_target = copy.deepcopy(before_validated[target]["content"])
        after_target = copy.deepcopy(after_validated[target]["content"])
        for metadata_key in ("human_revision", "review_directive", "review_adjustments"):
            before_target.pop(metadata_key, None)
            after_target.pop(metadata_key, None)
        if before_target != after_target:
            changed_targets.append(target)
    if not changed_targets:
        raise ValueError(
            "Revision did not materially change any human-targeted section: "
            + ", ".join(sorted(targets))
        )

    changed_unrelated = [
        section_name
        for section_name in BLUEPRINT_SECTION_KEYS
        if section_name not in targets
        and before_validated[section_name] != after_validated[section_name]
    ]
    if changed_unrelated:
        raise ValueError(
            "Revision changed unrelated sections: " + ", ".join(changed_unrelated)
        )
    return ",".join(sorted(changed_targets))
