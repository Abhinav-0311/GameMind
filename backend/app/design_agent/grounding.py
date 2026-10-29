import copy
import re
import unicodedata
from typing import Any
from types import SimpleNamespace

from app.design_agent.contracts import BLUEPRINT_SECTION_KEYS, BlueprintContent, GovernedBlueprintContent, CritiqueOutput, CritiqueReference, DefectReference, DialogueTriggerMapping, ProposalConfirmation


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
    "excerpt_start",
    "excerpt_end",
}
_TRAILING_FRAGMENT_WORDS = {"a", "an", "and", "as", "at", "for", "in", "of", "or", "the", "to", "with", "you"}
_OBJECTIVE_NOTE_PATTERN = re.compile(
    r"\s*(?:proposal\s*[-:\u2010-\u2015]\s*)?Objective:\s*(.*?)\s*;\s*"
    r"Event:\s*(.*?)\s*;\s*State:\s*(.*?)\s*;\s*Check:\s*(.*?)\s*",
    re.IGNORECASE | re.DOTALL,
)
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
    # ASCII-only matching erased non-Latin lines, skipping both proposal
    # labelling and source-reuse checks. Retain letters, combining marks and
    # numbers; punctuation/spacing are typography, not source evidence.
    text = unicodedata.normalize("NFKC", value).casefold().replace("\u2019", "'")
    words = "".join(
        character if unicodedata.category(character)[0] in {"L", "M", "N"} or character == "'" else " "
        for character in text
    )
    return " ".join(words.split())


def _mark_generated_dialogue_for_review(
    validated: dict[str, Any],
    evidence_by_id: dict[str, dict[str, Any]],
) -> None:
    """Keep creative dialogue useful, but never present it as a GDD fact.

    A character citation can ground *who* speaks and the scenario, while the
    line itself may be a useful model proposal. Exact source lines stay factual;
    everything else is explicitly a narrative-review draft before runtime use.
    """
    section = validated["npc_archetypes"]
    section["warnings"] = [warning for warning in section["warnings"]
                           if not warning.startswith("Reused source dialogue:")]
    for npc in section["content"]["npcs"]:
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
        reused = sum(
            bool(normalised := _normalise_for_quote_match(hook)) and normalised in source_text
            for hook in npc["dialogue_hooks"]
        )
        if reused:
            section["warnings"].append(
                f"Reused source dialogue: NPC '{npc['name']}' has {reused} source-text hook(s); "
                "these are existing lines, not fresh generated variations."
            )


def _validate_npc_identities(
    validated: dict[str, Any], evidence_by_id: dict[str, dict[str, Any]],
) -> None:
    """Require a whole name in the NPC's own section-matched frozen sources.

    This is a narrow identity check, not proof of personality or claim entailment.
    Never silently rename a character or use an unrelated chunk to justify it.
    """
    for npc in validated["npc_archetypes"]["content"]["npcs"]:
        name = npc["name"].strip()
        source = _cited_evidence_text(npc, evidence_by_id)
        if not name or not re.search(rf"(?<!\w){re.escape(name.casefold())}(?!\w)", source):
            raise ValueError(
                f"NPC identity '{npc['name']}' is not named in its cited NPC evidence. "
                "Use the source character name or supply a source-grounded design decision."
            )


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
            "event actions": list(((quest.get("state_contract") or {}).get("event_actions") or {}).values()),
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
        # Preserve useful drafts, but make each invented failure rule visible.
        # A citation to a level plan does not establish an attempt limit or timer.
        for rule in quest["failure_states"]:
            normalised = _normalise_for_quote_match(rule)
            if normalised and normalised not in source_text:
                proposal = (
                    f"Failure rule proposal (not verified in cited GDD): {rule} "
                    "Requires explicit design confirmation before runtime use."
                )
                quest["assumptions"] = list(dict.fromkeys([*quest["assumptions"], proposal]))


def _reject_unsupported_quest_details(
    quest: dict[str, Any],
    evidence_by_id: dict[str, dict[str, Any]],
) -> None:
    """Keep model proposals out of factual quest fields unless sources support them."""
    source_text = _cited_evidence_text(quest, evidence_by_id)
    contract = quest.get("state_contract")
    notes = quest["implementation_notes"]
    if contract:
        symbols = [quest["id"], *(item["flag"] for item in contract["objectives"]),
                   *(contract.get("event_actions") or {})]
        symbols = [re.escape(symbol) for symbol in symbols
                   if re.fullmatch(r"[A-Za-z][A-Za-z0-9]*_[A-Za-z0-9_]+", symbol)]
        if symbols:
            # Declared identifiers in helper notes are bookkeeping; action values and numeric mechanics still need evidence.
            pattern = r"(?<!\w)(?:" + "|".join(symbols) + r")(?!\w)"
            notes = [re.sub(pattern, "", note) for note in notes]
    factual_values = (
        [quest["objective"], quest.get("reward") or ""]
        + quest["objectives"]
        + quest["failure_states"]
        + quest["dependencies"]
        + quest["dialogue_hooks"]
        + notes
    )
    if contract:
        if contract.get("event_actions") is not None:
            # Mapped event keys are bookkeeping, not source-authored quantities.
            factual_values += list(contract["event_actions"].values())
        else:
            factual_values += [item["event"] for item in contract["objectives"]]
            if contract["failure"]:
                factual_values += contract["failure"]["events"]
            if contract["restart"]:
                factual_values.append(contract["restart"]["event"])
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

    normalised_source = _normalise_for_quote_match(source_text)
    for rule in quest["failure_states"]:
        # Word counts and unrelated source numerals must not bypass the gate.
        mechanical_limit = re.search(
            r"\d|\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
            r"hundred|thousand|timer|timeout|countdown|deadline)\b|\btime[- ]limit\b",
            rule, re.IGNORECASE,
        )
        if mechanical_limit and _normalise_for_quote_match(rule) not in normalised_source:
            raise ValueError(
                f"Quest '{quest['title']}' uses an unsupported failure rule: '{rule}'. "
                "Keep it as a review proposal; cite the actual rule before approval."
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


def _validate_dialogue_triggers(validated: dict[str, Any], require_actionable: bool) -> None:
    """Check references, not semantic fit; proposed mappings need designer review."""
    section = validated["npc_archetypes"]
    for npc in section["content"]["npcs"]:
        mappings = npc["dialogue_triggers"]
        if not mappings:
            if any(re.search(r"\btrigger mapping\b", note, re.IGNORECASE)
                   for note in npc["implementation_notes"]):
                message = (
                    f"NPC '{npc['name']}' has unstructured trigger mappings; replace them "
                    "with explicit situation/line pairs and review their semantic fit."
                )
                if require_actionable:
                    raise ValueError(message)
                section["warnings"] = list(dict.fromkeys([*section["warnings"], message]))
                npc["assumptions"] = list(dict.fromkeys([*npc["assumptions"], message]))
            continue  # Legacy first-contact dialogue remains readable.
        hooks = {line.strip() for line in npc["dialogue_hooks"]}
        triggers = [mapping["trigger"].casefold() for mapping in mappings]
        if len(triggers) != len(set(triggers)):
            raise ValueError(f"NPC '{npc['name']}' repeats a dialogue trigger ID.")
        mapped_lines = {mapping["text"] for mapping in mappings}
        if mapped_lines != hooks:
            raise ValueError(
                f"NPC '{npc['name']}' has dialogue trigger lines that do not exactly cover its spoken hooks."
            )
        if any(_normalise_for_quote_match(mapping["text"]) not in
               _normalise_for_quote_match(mapping["manual_test"]) for mapping in mappings):
            raise ValueError(
                f"NPC '{npc['name']}' has a dialogue trigger manual test without its expected spoken line."
            )
        npc["assumptions"] = list(dict.fromkeys([
            *npc["assumptions"],
            "Dialogue trigger mappings are implementation proposals; a designer must check "
            "each situation/line pairing, repeat policy and manual test before runtime use.",
        ]))
        # Structured pairs own dialogue event steps; retain unrelated profile/event guidance.
        npc["implementation_notes"] = [
            note for note in npc["implementation_notes"]
            if not re.search(r"\btrigger mapping\b", note, re.IGNORECASE)
            and not re.search(
                r"^\s*(?:proposal\s*[-:\u2010-\u2015]\s*)?event\s*:.*?\bstate\s*:[^;]*"
                r"\b(?:dialogue|warnings?|spoken|speech|subtitles?|popup)\b",
                note, re.IGNORECASE | re.DOTALL,
            )
            and not note.startswith("Dialogue trigger proposal '")
            and note != "Use dialogue hooks as first-contact lines; keep scene triggers and presentation client-side."
            and note != "Do not implement listed assumptions until a designer confirms them."
        ]


def _mark_scene_integration_proposals(validated: dict[str, Any]) -> None:
    """Give explicitly named scene instructions conservative proposal status.

    This is a field-label safeguard, not an entailment or language detector.
    Even source-constrained placement needs integration review; the label does
    not mean its source facts are unsupported or permit contradicting them.
    Keep the instruction body and unrelated notes intact, without duplicating
    every instruction into assumptions or claiming a verified engine binding.
    """
    scene_note = re.compile(r"^\s*Scene integration(?: proposal)?\s*:\s*", re.I)
    for section, key in (("npc_archetypes", "npcs"), ("quest_hooks", "quests")):
        for record in validated[section]["content"][key]:
            if not any(scene_note.match(note) for note in record["implementation_notes"]):
                continue
            record["implementation_notes"] = [
                scene_note.sub("Scene integration proposal: ", note, count=1)
                for note in record["implementation_notes"]
            ]
            record["assumptions"] = list(dict.fromkeys([
                *record["assumptions"],
                "Scene integration notes are unverified implementation proposals; confirm placement, "
                "activation events and source compatibility before runtime use.",
            ]))


def _add_integration_steps(validated: dict[str, Any], *, design_contract_version: int = 1) -> None:
    """Attach safe, engine-neutral implementation steps to reviewable artifacts."""
    for npc in validated["npc_archetypes"]["content"]["npcs"]:
        generated_steps = [
            f"Create a stable NPC profile for '{npc['name']}' and retain its source_chunk_ids in the review trace.",
        ]
        if npc["dialogue_triggers"]:
            mapping_notes = [
                f"Dialogue trigger proposal '{mapping['trigger']}': {mapping['situation']}. "
                f"Say: {mapping['text']} Repeat policy: {mapping['repeat_policy']} "
                f"Manual check: {mapping['manual_test']}"
                for mapping in npc["dialogue_triggers"]
            ]
            if design_contract_version == 2:
                # Keep proposed manual checks in one field, not copied into every note.
                npc["implementation_notes"] = [note for note in npc["implementation_notes"] if note not in mapping_notes]
                generated_steps.append("Bind each dialogue_triggers entry only while its eligibility holds. "
                    "Run its manual_test and enforce repeat_policy; these are proposed checks, not executed tests.")
            else:
                generated_steps.extend(mapping_notes)
        else:
            generated_steps.append("Use dialogue hooks as first-contact lines; keep scene triggers and presentation client-side.")
        if npc["assumptions"]:
            generated_steps.append("Do not implement listed assumptions until a designer confirms them.")
        npc["implementation_notes"] = list(dict.fromkeys(npc["implementation_notes"] + generated_steps))

    for quest in validated["quest_hooks"]["content"]["quests"]:
        contract = quest.get("state_contract")
        if contract:
            actions = contract.get("event_actions") or {}
            quest["assumptions"] = list(dict.fromkeys([
                *quest["assumptions"],
                "Quest state contract is an unverified implementation proposal, not an engine binding. "
                "Confirm observable events, source ordering and failure/restart rules before integration.",
            ]))
            generated_steps = [
                "Structured state proposal: start an attempt active with all objective flags false. "
                "While active, each declared objective event sets only its own flag true; preserve other flags. "
                "Do not mutate a completed/failed attempt from objective events.",
                "Completion proposal: reevaluate after each objective update; set lifecycle to completed "
                "only when all required_flags are true. Test every partial state and both action orders; "
                "event descriptions are not executable bindings or playtest evidence.",
            ]
            flags = [item["flag"] for item in contract["objectives"]]
            zero = ", ".join(f"{flag}=false" for flag in flags)
            full = ", ".join(f"{flag}=true" for flag in flags)
            generated_steps.append(
                f"Contract check (not executed): Setup: active; {zero}. Action: interact without an objective event. "
                f"Expect: active; {zero}; play dialogue only if its declared situation is satisfied.")
            for item in contract["objectives"]:
                partial = ", ".join(f"{flag}={'true' if flag == item['flag'] else 'false'}" for flag in flags)
                lifecycle = "completed" if len(flags) == 1 else "active"
                check = (f"Contract check (not executed): Setup: active; {zero}. "
                         f"Action: {actions.get(item['event'], item['objective'])} until its proposed event ({item['event']}) occurs. "
                         f"Expect: {lifecycle}; {partial}.")
                remaining = [f"{actions.get(other['event'], other['objective'])} (event: {other['event']})" for other in contract["objectives"]
                             if other["flag"] != item["flag"]]
                if remaining:
                    check += f" Action: perform remaining objectives ({'; '.join(remaining)}). Expect: completed; {full}."
                generated_steps.append(check + " Interact after each step and compare dialogue with its declared situation and repeat policy.")
            generated_steps.append(
                f"Contract check (not executed): Setup: completed; {full}. Action: replay each objective event. "
                f"Expect: completed; {full}; active-only dialogue must remain suppressed.")
            if contract["failure"]:
                generated_steps.append(
                    "Contract check (not executed): Setup: active with each incomplete flag state above. "
                    f"Action: exercise each failure event separately ({'; '.join(actions.get(event, event) for event in contract['failure']['events'])}). "
                    "Expect: failed with exactly the setup flags. Action: ordinary interaction. Expect: failed, "
                    "flags unchanged; active-only dialogue must remain suppressed; no implicit restart.")
            if contract["restart"]:
                setup = "failed with each preserved incomplete flag state above" if contract["failure"] else "the designer-confirmed restart-eligible state"
                generated_steps.append(
                    f"Contract check (not executed): Setup: {setup}. Action: {actions.get(contract['restart']['event'], contract['restart']['event'])}. "
                    f"Expect: active; {zero}, cleared atomically. Interact and recheck dialogue eligibility; "
                    "a reset does not guarantee replay or establish an event binding.")
            # Regenerate server-derived cases so revisions cannot retain stale event or flag names.
            quest["implementation_notes"] = [note for note in quest["implementation_notes"]
                                             if not note.startswith("Contract check (not executed): ")]
            quest["implementation_notes"] = list(dict.fromkeys(quest["implementation_notes"] + generated_steps))
            continue  # Never imply listed-order execution for independent v1 flags.
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


_DESIGN_METADATA_KEYS = {
    "title", "id", "name", "version", "project_id", "generation_mode",
    "citations", "source_chunk_ids", "confidence", "warnings", "assumptions",
    "human_revision", "review_directive", "review_adjustments", "implementation_notes", "manual_test", "fresh_dialogue",
}
BLUEPRINT_RECOVERY_WARNING = (
    "The blueprint response required local structural recovery. "
    "Treat it as a recovered draft; check complete section coverage, source support and design usefulness before approval."
)


def _has_design_content(value: Any) -> bool:
    """Check nonempty design values, not citations, labels, or container shells.

    This measures presence only, never semantic usefulness or source entailment.
    Zero and false are valid explicit settings, unlike null and blank strings.
    """
    if isinstance(value, dict):
        return any(_has_design_content(item) for key, item in value.items()
                   if key not in _DESIGN_METADATA_KEYS)
    if isinstance(value, list):
        return any(_has_design_content(item) for item in value)
    if isinstance(value, str):
        return bool(value.strip())
    return value is not None


def _quest_integration_gaps(quest: dict[str, Any]) -> list[str]:
    """Check per-objective note coverage, not semantic quality or runtime execution."""
    if quest.get("state_contract"):
        # Pydantic has checked exact objective coverage and finite flag semantics.
        return []
    covered = []
    for note in quest["implementation_notes"]:
        match = _OBJECTIVE_NOTE_PATTERN.fullmatch(note)
        if match and all(value.strip() and not re.fullmatch(r"<[^<>]+>", value.strip())
                         for value in match.groups()):
            covered.append(_revision_text(match[1]))
    missing = []
    for objective in quest["objectives"]:
        key = _revision_text(objective)
        if key and key in covered:
            covered.remove(key)
        else:
            missing.append(objective)
    return missing


def _quest_check_conflicts(quest: dict[str, Any]) -> list[dict[str, Any]]:
    """Recognize mirrored completion flags, not arbitrary prose or a game-state engine.

    Only two explicit required-objective notes that set their own flags to true
    and require the other's flag false qualify. No expression is executed.
    """
    bindings = []
    objectives = {_revision_text(value) for value in quest["objectives"]}
    for note in quest["implementation_notes"]:
        match = _OBJECTIVE_NOTE_PATTERN.fullmatch(note)
        if not match or _revision_text(match[1]) not in objectives:
            continue
        state = re.fullmatch(r"quest\s+flag\s+['\"]([A-Za-z_]\w*)['\"]\s+set\s+to\s+true\.?", match[3], re.I)
        check = re.fullmatch(r"([A-Za-z_]\w*)\s*==\s*true\s+AND\s+([A-Za-z_]\w*)\s*==\s*false\.?", match[4], re.I)
        if state and check and state[1] == check[1] and check[1] != check[2]:
            bindings.append((match[1], check[1], check[2], match[4]))
    conflicts = []
    for index, first in enumerate(bindings):
        for second in bindings[index + 1:]:
            if (first[1] == second[2] and first[2] == second[1]
                    and _revision_text(first[0]) != _revision_text(second[0])):
                conflict = {"record_id": quest["id"], "record": quest["title"],
                            "objectives": [first[0], second[0]],
                            "state": {first[1]: True, second[1]: True}, "checks": [first[3], second[3]]}
                if conflict not in conflicts:
                    conflicts.append(conflict)
    return conflicts


def _quest_scoped_completion_trigger(
    mapping: dict[str, Any], quests: list[dict[str, Any]], objective: str,
) -> bool:
    """Recognize a quest-scoped completion label, not the meaning of its line.

    A suffix such as ash_pass_complete may name a quest without the literal
    words 'quest complete'. Require its multiword scope in both a candidate
    quest and the human request; unrelated task labels are not substitutes.
    """
    trigger = _normalise_for_quote_match(mapping["trigger"])
    match = re.fullmatch(r"(.+) (?:complete|completed|completion|success)", trigger)
    if not match or len(match[1].split()) < 2:
        return False
    situation = _normalise_for_quote_match(mapping["situation"])
    if re.search(r"\b(?:not (?:yet )?(?:complete|completed)|incomplete|in progress)\b", situation):
        return False
    scope = " " + match[1] + " "
    return scope in " " + _normalise_for_quote_match(objective) + " " and any(
        scope in " " + _normalise_for_quote_match(quest["id"] + " " + quest["title"]) + " "
        for quest in quests
    )


def _restart_checks_active_state(state: str, check: str) -> bool:
    """Check an explicit quest/quest_state activation and its same-key predicate."""
    active = re.search(
        r"(?:^|\s+AND\s+)(quest(?:_state| state)?)\s+(?:set\s+to|becomes|is)\s+"
        r"['\"]?active['\"]?(?=\s|[.,;]|$)", state, re.I,
    )
    if not active:
        return False
    # Parse conjunctions, not substrings inside a negation or an OR expression.
    if re.search(r"\bOR\b|\|\|", check, re.I):
        return False
    terms = re.split(r"\s+(?:AND|&&)\s+", check.rstrip("."), flags=re.I)
    return any(re.fullmatch(re.escape(active[1]) + r"\s*(?:==|is)\s*['\"]?active['\"]?", term, re.I)
               for term in terms)


def _shared_progress_claim(mapping: dict[str, Any], quests: list[dict[str, Any]]) -> str | None:
    """Recognize a few English state assertions, not arbitrary dialogue meaning.

    Structured eligibility identifies its quest; legacy prose requires one
    typed quest and explicitly shared zero/partial progress. Unknown spoken
    wording, questions and conditional instructions remain for human review.
    Objective-specific vocabulary comes from the draft, never game-name rules.
    """
    condition = mapping.get("eligibility")
    if condition:
        quest = next((quest for quest in quests if quest["id"] == condition["quest_id"]), None)
        if quest is None:
            return None
    elif len(quests) == 1:
        quest = quests[0]
    else:
        return None
    contract = quest.get("state_contract")
    if not contract or len(contract["objectives"]) < 2:
        return None
    situation = _normalise_for_quote_match(mapping["situation"])
    if condition:
        shared_incomplete = condition["lifecycle"] in {"active", "failed"} and condition["progress"] in {"incomplete", "any"}
    else:
        shared_incomplete = (
            re.search(r"\b(?:either or both|one or both|at least one|zero and partial)\b", situation)
            and re.search(r"\b(?:incomplete|unfinished|progress)\b", situation)
        ) or re.search(
            # Legacy prose only; new eligibility never depends on this wording.
            r"\bnot yet\b.+\bor\b.+\bcompleted only one of the (?:two|2) objectives\b", situation,
        )
    if not shared_incomplete:
        return None
    words = [set(re.findall(r"[a-z]+", item["objective"].casefold())) for item in contract["objectives"]]
    shared = set.intersection(*words)
    anchors = set.union(*words) - shared - _DEPENDENCY_STOPWORDS - {
        "at", "in", "of", "with", "clear", "raise", "collect", "inspect", "defeat", "reach", "activate",
    }
    anchors = {word for word in anchors if len(word) > 2}
    state_assertion = (
        r"(?:still\s+(?:breathe|stand)|(?:(?:still\s+)?(?:is|are|remains?|lies?)\s+)?(?:still\s+)?"
        r"(?:closed|locked|down|low|lowered|uncleared|unraised|unfinished|incomplete|pending|gone|cleared|defeated|raised|open))\b"
    )
    objective_assertion = (re.compile(
        r"\b(?:" + "|".join(re.escape(word) for word in sorted(anchors))
        + r")\b(?:\s+[\w'-]+){0,3}\s+" + state_assertion, re.I,
    ) if anchors else None)
    count_assertion = re.compile(
        r"\b(?:(?:only|exactly)\s+)?(?:one|both|all)\s+(?:tasks?|objectives?|actions?)\s+"
        r"(?:remain(?:s)?|(?:is|are)\s+(?:still\s+)?(?:unfinished|incomplete|pending))\b", re.I,
    )
    for match in re.finditer(r"[^.!?;]+[.!?;]?", mapping["text"]):
        clause = match[0].strip()
        if clause.endswith("?") or re.search(r"\b(?:if|unless|whether)\b", clause, re.I):
            continue
        if re.match(r"^(?:return|come back|wait)\s+(?:when|once|until)\b", clause, re.I):
            continue  # Future instructions do not assert that their conditions hold now.
        if count_assertion.search(clause) or (objective_assertion and objective_assertion.search(clause)):
            return clause
    return None


def _first_interaction_repeat_conflict(mapping: dict[str, Any]) -> bool:
    """Recognize an explicit English conflict, not a repeat-policy interpreter.

    Match only a first-event declaration and an unqualified repeat-every-time
    clause. Negations, conditional repetition and unknown prose stay in review.
    Never infer or rewrite a reset event, especially human-supplied direction.
    """
    trigger = _normalise_for_quote_match(mapping["trigger"])
    situation = _normalise_for_quote_match(mapping["situation"])
    first_event = (
        re.fullmatch(r"(?:on )?first (?:interaction|encounter|meeting|greeting)", trigger)
        or re.match(r"first (?:interaction|encounter|meeting|greeting)\b", situation)
    )
    clause = _normalise_for_quote_match(re.split(r"[.;!?\n]", mapping["repeat_policy"], maxsplit=1)[0])
    return bool(first_event and re.fullmatch(
        r"(?:repeatable|repeats?|plays?)(?: on)? (?:each|every) interaction", clause,
    ))


def _quest_source_gaps(quests: list[dict], evidence: list[dict]) -> list[dict[str, str]]:
    from app.services.blueprint_service import BlueprintService

    # shortcut: existing explicit quest-line/table formats and exact normalized identity only; paraphrases need human review.
    parser = BlueprintService()
    by_id = {str(item["chunk_id"]): item for item in evidence if "quest_hooks" in (item.get("matched_sections") or [])}
    gaps = []
    for quest in quests:
        identities = {_normalise_for_quote_match(quest[key]) for key in ("title", "objective")}
        rewards = set()
        quantities = set()
        for source_id in quest["source_chunk_ids"]:
            if source_id not in by_id:
                continue
            item = by_id[source_id]
            chunk = SimpleNamespace(id=source_id, content=str(item.get("content") or ""), chunk_index=item.get("chunk_index") or 0)
            for source in parser._parse_quest_hooks([chunk])["content"]["quests"]:
                if identities & {_normalise_for_quote_match(source[key]) for key in ("title", "objective")}:
                    if source["reward"]:
                        rewards.add(_normalise_for_quote_match(source["reward"]))
                    quantities.update(re.findall(r"\b\d+(?:\.\d+)?\b", source["objective"]))
        contract = quest.get("state_contract") or {}
        actions = contract.get("event_actions") or {}
        objectives = contract.get("objectives") or []
        if quantities and any(quantities - set(re.findall(r"\b\d+(?:\.\d+)?\b", text)) for text in (
                quest["objective"], " ".join(item["objective"] for item in objectives),
                " ".join(actions.get(item["event"], "") for item in objectives))):
            gaps.append({"code": "quest_source_quantity_coverage", "section": "quest_hooks", "record": quest["title"],
                         "issue": f"Quest '{quest['title']}' omits an explicit source objective amount ({', '.join(sorted(quantities))}) from its objective or completion conditions. Preserve the full sourced total; numeral presence alone does not verify threshold semantics."})
        if len(rewards) > 1:
            gaps.append({"code": "quest_reward_conflict", "section": "quest_hooks", "record": quest["title"],
                         "issue": f"Quest '{quest['title']}' has conflicting explicit source rewards in its cited quest records. Resolve the source conflict; do not choose a reward silently."})
        elif rewards and _normalise_for_quote_match(quest.get("reward") or "") not in rewards:
            gaps.append({"code": "quest_reward_coverage", "section": "quest_hooks", "record": quest["title"],
                         "issue": f"Quest '{quest['title']}' omits or changes its explicit source reward. Preserve it in quest.reward, not only notes, assumptions or runtime data."})
    return gaps


def _request_coverage_gaps(
    content: dict[str, Any], review_request: dict[str, Any] | None,
    evidence: list[dict[str, Any]] | None,
) -> list[dict[str, str]]:
    """Bounded English checks for explicit requests, never semantic acceptance.

    Derive human requirements only from the original objective, not source
    instructions or model self-assessments. Check explicit matching source rewards
    separately, plus bounded conflicts in dialogue/restart proposals. Unknown wording remains for review.
    Matching a situation label does not prove its spoken line is useful.
    """
    objective = str((review_request or {}).get("objective") or "")
    # Do not turn explicitly excluded situations into positive requirements.
    affirmative = re.sub(r"\b(?:without|no|do not|don't|omit)\b[^.;!?\n]*", "", objective, flags=re.I)
    # shortcut: these QA wording checks are not semantic validation; expand only for another verified failure.
    active_progress = bool(re.search(r"\bprogress dialogue requires an active attempt\b", affirmative, re.I))
    confirmed_restart = bool(re.search(r"\bconfirmed restart(?: quest)?\b", affirmative, re.I))
    concrete_failure = bool(re.search(r"\bconcrete failure\b", affirmative, re.I))
    # Proposed-cause wording uses typed contracts; legacy prose keeps its transition checks below.
    proposed_failure = bool(re.search(r"\bconcrete proposed failure\b", affirmative, re.I))
    event_identifier = r"[A-Za-z][A-Za-z0-9]*_[A-Za-z0-9_]+"
    npcs = content["npc_archetypes"]["content"]["npcs"]
    quests = content["quest_hooks"]["content"]["quests"]
    gaps = []
    if (review_request or {}).get("design_contract_version") == 2:
        gaps.extend(_quest_source_gaps(quests, evidence or []))

    def add(code: str, section: str, record: str, issue: str) -> None:
        gaps.append({"code": code, "section": section, "record": record, "issue": issue})

    if (review_request or {}).get("defer_runtime") is True:
        preview = content["unity_runtime_preview"]
        if preview["content"] or preview["citations"] or any(quest.get("runtime") is not None for quest in quests):
            add("runtime_deferral_scope", "unity_runtime_preview", "runtime",
                "This run explicitly defers runtime integration. Keep the runtime preview empty and uncited "
                "and quest runtime bindings null; do not mix runtime claims into design-only approval.")

    for quest in quests:
        contract = quest.get("state_contract") or {}
        failure = contract.get("failure")
        actions = contract.get("event_actions") or {}
        if contract and (review_request or {}).get("design_contract_version") == 2:
            # shortcut: missing explicit numerals only; threshold meaning still needs source/human review.
            numbers = r"\b\d+(?:\.\d+)?\b"
            objectives = contract["objectives"]
            missing = set(re.findall(numbers, quest["objective"])) - set(re.findall(
                numbers, " ".join(item["objective"] for item in objectives)))
            incomplete_actions = [item["objective"] for item in objectives if
                set(re.findall(numbers, item["objective"])) - set(re.findall(numbers, actions.get(item["event"], "")))]
            if missing or incomplete_actions:
                add("quest_quantity_coverage", "quest_hooks", quest["title"],
                    f"Quest '{quest['title']}' drops explicit objective numerals from its state objectives "
                    f"({', '.join(sorted(missing)) or 'none'}) or completion actions "
                    f"({'; '.join(incomplete_actions) or 'none'}). Preserve the required amount in the objective "
                    "and its completion-event condition, not only notes or event IDs. Numeral presence alone does not prove correct threshold semantics.")
            failure_causes = quest["failure_states"] + [actions.get(event, event)
                for event in (contract.get("failure") or {}).get("events", [])]
            # shortcut: bounded English unfinished-state forms; other wording still needs semantic review.
            for cause in dict.fromkeys(failure_causes):
                predicate = _normalise_for_quote_match(cause)
                if (re.fullmatch(
                        r"(?:.+\bremain(?:s)? alive(?: at .+)?|.+\bnot (?:yet )?(?:raised|cleared|completed)|"
                        r"(?:less|fewer) than \d+ .+ (?:mined|collected|extracted)(?: from .+)?)", predicate)
                        and not re.search(r"\b(?:when|after|upon|deadline|timeout|countdown)\b", predicate)):
                    add("quest_failure_predicate", "quest_hooks", quest["title"],
                        f"Quest '{quest['title']}' treats ordinary unfinished progress as failure: '{cause}'. "
                        "An active attempt may normally have unfinished objectives. Define a separate observable failure event "
                        "and when it is checked, or keep failure_states empty and state_contract.failure null. "
                        "Proposal confirmation cannot supply the missing failure event.")
        if (concrete_failure or (proposed_failure and contract)) and (not failure or any(re.fullmatch(event_identifier, actions.get(event, event).strip()) for event in failure["events"])):
            add("failure_event_action", "quest_hooks", quest["title"],
                f"Quest '{quest['title']}' requires a concrete failure event, but its failure binding is "
                "missing or contains only an identifier. Describe the observable action that fails an "
                "active attempt in failure.events; a status label or claimed checklist coverage is not "
                "a cause. This bounded identifier check does not validate arbitrary event meaning.")
        restart = contract.get("restart")
        if not restart:
            continue
        # Exact affirmative alternatives observed in QA, not a general intent
        # parser. Full branches avoid treating negations or an explicit later
        # confirmation as an unconditional reset. Unknown prose stays in review.
        restart_action = actions.get(restart["event"], restart["event"])
        unsafe = [branch.strip() for branch in re.split(r"\s+or\s+", restart_action, flags=re.I)
                  if re.fullmatch(
                      r"\s*(?:player\s+)?(?:selects?\s+['\"]?abandon quest['\"]?"
                      r"(?:\s+from (?:the )?quest menu)?|interacts?\s+with\s+.+?"
                      r"\s+after\s+(?:quest\s+)?failure)\s*[.]?\s*", branch, re.I)]
        if unsafe:
            add("restart_event_intent", "quest_hooks", quest["title"],
                f"Quest '{quest['title']}' restart clears all objective flags and sets lifecycle active "
                f"on abandonment or ordinary post-failure interaction: {'; '.join(unsafe)}. "
                "Declare a separate explicit new-attempt confirmation instead, or revise and review "
                "the intended lifecycle before approval. Confirming a proposal does not resolve this "
                "ambiguous reset. This bounded English check does not validate other event wording.")
        if confirmed_restart and re.fullmatch(event_identifier, restart_action.strip()):
            add("restart_confirmation", "quest_hooks", quest["title"],
                f"Quest '{quest['title']}' requires a confirmed restart, but its event is only "
                f"an identifier ({restart['event']}). Name the player's confirmation action in the "
                "event itself; a checklist assertion does not define that action.")

    for npc in npcs:
        for mapping in npc["dialogue_triggers"]:
            condition = mapping.get("eligibility")
            label = _normalise_for_quote_match(mapping["situation"])
            # Exact model-authored labels only; do not infer purpose from arbitrary dialogue prose.
            if (condition and (review_request or {}).get("design_contract_version") == 2
                    and ((label == "greeting" and condition["stage"] != "greeting")
                         or (label == "quest offer" and condition["stage"] in {"progress", "completion"}))):
                add("dialogue_stage_situation", "npc_archetypes", npc["name"],
                    f"NPC '{npc['name']}' trigger '{mapping['trigger']}' has declared situation "
                    f"'{mapping['situation']}' but stage '{condition['stage']}'. Clarify its interaction purpose "
                    "and intended availability instead of silently treating a greeting or offer as quest progress. "
                    "Greetings may remain quest-scoped; offers need an explicit activation/availability decision. "
                    "Proposal confirmation cannot resolve the mismatched declaration.")
            if (active_progress and not mapping.get("eligibility") and re.search(r"\b(?:progress|incomplete)\b", _normalise_for_quote_match(mapping["trigger"]))
                    and not re.search(r"\bactive\b", _normalise_for_quote_match(mapping["situation"]))):
                add("dialogue_active_attempt", "npc_archetypes", npc["name"],
                    f"NPC '{npc['name']}' progress trigger '{mapping['trigger']}' omits the requested "
                    "active-attempt condition from its situation. Preserved incomplete flags can also "
                    "exist after failure; a memory note or claimed test coverage is not this trigger's "
                    "eligibility guard. This bounded missing-word check does not validate other wording.")
            if _first_interaction_repeat_conflict(mapping):
                add("dialogue_repeat_eligibility", "npc_archetypes", npc["name"],
                    f"NPC '{npc['name']}' trigger '{mapping['trigger']}' declares first-interaction "
                    f"eligibility ({mapping['situation']}) but promises unconditional replay: "
                    f"{mapping['repeat_policy']} Reconcile eligibility, repetition limit and named reset "
                    "before approval; a reset must not bypass eligibility. This bounded English check "
                    "does not validate other policy wording.")
            if claim := _shared_progress_claim(mapping, quests):
                add("dialogue_progress_state", "npc_archetypes", npc["name"],
                    f"NPC '{npc['name']}' trigger '{mapping['trigger']}' declares zero and partial "
                    f"progress eligibility but makes a fixed objective-state assertion: {claim} "
                    "A shared reminder must also fit either completed objective. Use a state-neutral "
                    "reminder or explicitly reviewed state-specific situations. This bounded English "
                    "check does not establish semantic correctness for other wording.")

    if re.search(r"\b(?:dialogue|spoken\s+lines?|lines?\s+for)\b", affirmative, re.I):
        stages = (
            ("greeting", r"\bgreeting\b",
             r"\b(?:greet\w*|approach\w*|first encounters?|first interaction|first meeting)\b"),
            ("progress", r"\b(?:quest[- ]in[- ]progress|quest[- ]progress|(?:quest[- ])?progress reminder|in[- ]progress reminder)\b",
             r"\b(?:in progress|quest active|mission active|progress reminder)\b"),
            ("completion", r"\bcompletion\s+(?:after|when|once|only|lines?|dialogue)\b|\bquest[- ]progress\s+and\s+completion\b",
             r"\b(?:quest|mission)\s+(?:is\s+)?(?:completed?|completion|success)\b"),
        )
        per_npc = re.search(r"\b(?:each|every)\s+(?:source\s+)?(?:npc|character)\b", affirmative, re.I)
        groups = [(npc["name"], [npc]) for npc in npcs] if per_npc and npcs else [("dialogue", npcs)]
        for stage, requested, present in stages:
            if not re.search(requested, affirmative, re.I):
                continue
            for record, group in groups:
                if not any(
                    (mapping["eligibility"]["stage"] == stage if mapping.get("eligibility") else
                     (re.search(present, re.sub(r"[_-]+", " ", mapping["trigger"] + " " + mapping["situation"]), re.I)
                      or (stage == "completion" and _quest_scoped_completion_trigger(mapping, quests, affirmative))))
                    for npc in group for mapping in npc["dialogue_triggers"]
                ):
                    add("dialogue_" + stage, "npc_archetypes", record,
                        f"Human request explicitly asks for {stage} dialogue for {record}, but no proposed trigger/situation identifies it. "
                        "An idle line or return after an unspecified task does not establish the requested quest situation.")

    timer_ban = re.search(r"\b(?:no|without)\b[^.;!?\n]{0,100}\btimers?\b", objective, re.I)
    if timer_ban:
        allow_cited_interval = bool(re.search(r"\bno\s+(?:extra|new|additional|invented)\b", timer_ban[0], re.I))
        evidence_by_id = {str(item["chunk_id"]): item for item in (evidence or [])}
        for npc in npcs:
            source = _cited_evidence_text(npc, evidence_by_id)
            for mapping in npc["dialogue_triggers"]:
                policy = re.sub(r"\b(?:not|never|no|without|do not|don't)\b[^.;!?\n]*", "", mapping["repeat_policy"], flags=re.I)
                intervals = re.findall(r"\b\d+(?:\.\d+)?\s*(?:seconds?|minutes?|hours?|ms)\b", policy, re.I)
                if any(not allow_cited_interval or _normalise_for_quote_match(interval) not in _normalise_for_quote_match(source) for interval in intervals):
                    add("unrequested_timer", "npc_archetypes", npc["name"],
                        f"NPC '{npc['name']}' has a timed repeat policy ({mapping['repeat_policy']}) not permitted by the human timer constraint. "
                        "Only a prohibition on extra/new timers permits a literal interval match in cited evidence; that match is not proof of semantic support.")

    combined_success = bool(re.search(r"\bfinal success\s+must\s+require\s+(?:both|all)\b", affirmative, re.I))
    wants_restart = confirmed_restart or bool(re.search(r"\brestart\b", affirmative, re.I) and re.search(r"\bEvent\s*/\s*State\s*/\s*Check\b", affirmative, re.I))
    if wants_restart or combined_success:
        for quest in quests:
            contract = quest.get("state_contract")
            if contract:
                if wants_restart and not contract["restart"]:
                    add("restart_transition", "quest_hooks", quest["title"],
                        f"Quest '{quest['title']}' lacks the requested structured restart event and reset contract.")
                if wants_restart and re.search(r"\bfailure\b", affirmative, re.I) and not contract["failure"]:
                    add("failure_transition", "quest_hooks", quest["title"],
                        f"Quest '{quest['title']}' lacks the requested structured failure event and lifecycle transition.")
                continue  # Typed assignments/predicates replace prose parsing, not source/creative review.
            transitions = (["failure", "restart"] if wants_restart else []) + (["completion"] if combined_success else [])
            for transition in transitions:
                if transition == "failure" and not re.search(r"\bfailure\b", affirmative, re.I):
                    continue
                pattern = (r"\s*(?:proposal\s*[-:\u2010-\u2015]\s*)?" + transition
                           + r":\s*(.+?)\s*;\s*Event:\s*(.+?)\s*;\s*State:\s*(.+?)\s*;\s*Check:\s*(.+?)\s*")
                notes = [match for note in quest["implementation_notes"]
                         if (match := re.fullmatch(pattern, note, re.I | re.S)) and all(
                             value.strip() and not re.fullmatch(r"<[^<>]+>", value.strip()) for value in match.groups())]
                if not notes:
                    add(transition + "_transition", "quest_hooks", quest["title"],
                        f"Quest '{quest['title']}' lacks the requested {transition.title()}/Event/State/Check note. "
                        "Objective checks and failure resets do not specify restart or final combined success.")
                elif transition == "restart":
                    if not all(_restart_checks_active_state(note[3], note[4]) for note in notes):
                        add("restart_reactivation", "quest_hooks", quest["title"],
                            f"Quest '{quest['title']}' restart must explicitly reactivate its quest state and check the same state is active. "
                            "Clearing objective flags alone does not specify a playable new attempt. "
                            "Use an explicit quest_state (or quest) active assignment and same-key AND predicate; other lifecycle wording needs clarification/review.")
                elif transition == "completion":
                    # Only recognize explicit boolean assignments. Do not execute
                    # expressions or claim to validate arbitrary prose/state machines.
                    flags = set()
                    objective_keys = {_revision_text(value) for value in quest["objectives"]}
                    for note in quest["implementation_notes"]:
                        if (match := _OBJECTIVE_NOTE_PATTERN.fullmatch(note)) and _revision_text(match[1]) in objective_keys:
                            flag = re.fullmatch(r"(?:quest\s+flag\s+)?['\"]?([A-Za-z_]\w*)['\"]?\s+(?:set\s+to|is|becomes)\s+true\.?", match[3], re.I)
                            if flag:
                                flags.add(flag[1])
                    def covers_flags(check: str) -> bool:
                        terms = re.split(r"\s+(?:AND|&&)\s+", check.rstrip("."), flags=re.I)
                        parsed = [re.fullmatch(r"([A-Za-z_]\w*)\s*(?:==|is)\s*true", term, re.I) for term in terms]
                        return all(parsed) and {term[1] for term in parsed} == flags
                    if len(flags) > 1 and not all(covers_flags(note[4]) for note in notes):
                        add("completion_flags", "quest_hooks", quest["title"],
                            f"Quest '{quest['title']}' final success must AND the same recorded objective flags: {', '.join(sorted(flags))}. "
                            "A last-action/OR check or renamed flags is not the combined success contract.")
                    if len(flags) > 1 and not all(re.search(
                        r"\b(?:either|each|any|every|both|all)\s+(?:(?:required|recorded)\s+)*(?:actions?|objectives?)\b",
                        note[2], re.I) and not re.search(r"\b(?:not|never)\b", note[2], re.I) for note in notes):
                        add("completion_event", "quest_hooks", quest["title"],
                            f"Quest '{quest['title']}' combined-success Event does not explicitly cover updates from either required action/objective. "
                            "An AND Check alone does not bind reevaluation after both action orders; a single last-action event can miss the reverse order. "
                            "Specify reevaluation on each required action/objective update and review any deliberately ordered design separately. "
                            "This checks the declared event coverage, not executable event wiring.")
    return gaps


def assess_artifact_quality(
    content: dict[str, Any], confirmed_proposals: list[dict[str, Any]] | None = None,
    *, review_request: dict[str, Any] | None = None, evidence: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return transparent, deterministic review signals before human approval.

    This is intentionally a narrow quality check. It confirms structured
    completeness and traceability, but never claims that it can replace a
    designer's judgment of creative quality.
    """
    contract = GovernedBlueprintContent if (review_request or {}).get("design_contract_version") == 2 else BlueprintContent
    validated = contract.model_validate(content).model_dump()
    request_gaps = _request_coverage_gaps(validated, review_request, evidence)
    deferred_sections = (["unity_runtime_preview"]
                         if (review_request or {}).get("defer_runtime") is True
                         and not any(gap["code"] == "runtime_deferral_scope" for gap in request_gaps) else [])
    unspecified_sections = ["npc_memory_design"] if memory_is_unspecified(validated, review_request) else []
    required_sections = [name for name in BLUEPRINT_SECTION_KEYS if name not in deferred_sections + unspecified_sections]
    unsupported_sections = [
        section_name
        for section_name in required_sections
        if not validated[section_name]["citations"]
    ]
    incomplete_sections = [
        section_name for section_name in required_sections
        if not _has_design_content(validated[section_name]["content"])
    ]
    recovered_sections = [
        section_name for section_name in BLUEPRINT_SECTION_KEYS
        if any(warning.startswith(("The blueprint response required closing-delimiter recovery.",
                                   "The blueprint response required local structural recovery."))
               for warning in validated[section_name]["warnings"])
    ]
    npcs = validated["npc_archetypes"]["content"]["npcs"]
    quests = validated["quest_hooks"]["content"]["quests"]
    if evidence and (review_request or {}).get("design_contract_version") == 2:
        evidence_by_id = {str(item["chunk_id"]): item for item in evidence if item.get("chunk_id")}
        for quest in quests:
            try:
                _reject_unsupported_quest_details(quest, evidence_by_id)
            except ValueError as error:
                request_gaps.append({"section": "quest_hooks", "code": "quest_source_details", "issue": str(error)})
    reused_fresh_dialogue = any(
        npc["fresh_dialogue"] and any(
            warning.startswith(f"Reused source dialogue: NPC '{npc['name']}' ")
            for warning in validated["npc_archetypes"]["warnings"]
        ) for npc in npcs
    )
    records = [*npcs, *quests]
    total_records = len(records)
    cited_records = sum(bool(record["source_chunk_ids"]) for record in records)
    actionable_npcs = sum(_has_design_content(npc["dialogue_hooks"]) for npc in npcs)
    actionable_quests = sum(
        _has_design_content(quest["objectives"]) and (
            _has_design_content(quest["failure_states"])
            or bool(quest.get("state_contract") and quest["state_contract"]["failure"] is None))
        for quest in quests
    )
    quest_gaps = [
        {"record_id": quest["id"], "record": quest["title"], "objectives": gaps}
        for quest in quests if (gaps := _quest_integration_gaps(quest))
    ]
    quest_conflicts = [conflict for quest in quests for conflict in _quest_check_conflicts(quest)]
    integration_ready = sum(bool(npc["implementation_notes"]) for npc in npcs) + sum(
        bool(quest["objectives"]) and not _quest_integration_gaps(quest) for quest in quests
    )
    npc_names = [npc["name"].casefold() for npc in npcs]
    quest_ids = [quest["id"].casefold() for quest in quests]
    duplicate_records = (len(npc_names) != len(set(npc_names))) or (len(quest_ids) != len(set(quest_ids)))
    proposals = [
        {"section": section, "record_id": record[identity],
         "record": record.get("name") or record.get("title") or "Untitled record", "assumption": assumption}
        for section, section_records, identity in (("npc_archetypes", npcs, "name"), ("quest_hooks", quests, "id"))
        for record in section_records for assumption in record["assumptions"]
    ]
    confirmations = [ProposalConfirmation.model_validate(item).model_dump() for item in (confirmed_proposals or [])]
    keys = [(item["section"], item["record_id"], item["assumption"]) for item in confirmations]
    available = {(item["section"], item["record_id"], item["assumption"]) for item in proposals}
    if len(keys) != len(set(keys)) or not set(keys) <= available:
        raise ValueError("Proposal confirmation contains duplicate or unknown draft proposals.")
    accepted = set(keys)
    unresolved = [item for item in proposals if (item["section"], item["record_id"], item["assumption"]) not in accepted]

    def ratio(numerator: int, denominator: int) -> float:
        return round(numerator / denominator, 4) if denominator else 0.0

    completeness_total = len(npcs) + len(quests)
    completeness = min(
        ratio(actionable_npcs + actionable_quests, completeness_total),
        ratio(len(required_sections) - len(incomplete_sections), len(required_sections)),
    )
    record_grounding = ratio(cited_records, total_records)
    section_grounding = ratio(
        len(required_sections) - len(unsupported_sections),
        len(required_sections),
    )
    grounding = min(record_grounding, section_grounding)
    integration = ratio(integration_ready, total_records)
    # A draft with unresolved implementation assumptions or unsupported
    # sections is not integration-ready, even if every record happens to have
    # mechanical integration steps. Reflect that in the numeric value as well
    # as the pass/fail flag so the UI never shows a perfect score for a blocked
    # artifact.
    if unresolved or unsupported_sections or incomplete_sections or recovered_sections or reused_fresh_dialogue or quest_conflicts or request_gaps:
        integration = 0.0
    # No records means this check has no input, not positive consistency proof.
    consistency = 0.0 if duplicate_records or quest_conflicts or not records else 1.0
    metrics = [
        {"key": "grounding", "label": "Grounding", "value": grounding, "passed": grounding == 1.0, "detail": "Every generated section and every NPC or quest record cites frozen GDD evidence."},
        {"key": "completeness", "label": "Completeness", "value": completeness, "passed": completeness == 1.0, "detail": "Checks nonempty design content, not proof of source coverage. Empty uncited sections with warnings need source/scope review; do not invent facts to fill them. NPCs need dialogue hooks; quests need objectives and either declared failure states or an explicit failure-free state contract. Dependencies may be empty when unsupported by the GDD."
         + (" Empty design sections: " + ", ".join(incomplete_sections) + "." if incomplete_sections else "")},
        {"key": "consistency", "label": "Contradiction checks", "value": consistency, "passed": consistency == 1.0, "detail": "Checks duplicate NPC names/quest IDs and explicit mirrored objective flags that cannot both pass after both required actions. No records means no positive score; other semantic and narrative conflicts still require review."},
        {"key": "integration_readiness", "label": "Integration readiness", "value": integration, "passed": integration == 1.0, "detail": "NPCs need integration notes; quests need a validated state contract, or per-objective Objective/Event/State/Check notes for legacy drafts. Legacy prose checks do not prove flag assignment or reset semantics. No unresolved assumptions or unsupported/empty sections remain. Checks establish structure, not semantic quality or playtest proof."
         + (" Missing quest checks: " + "; ".join(item["record"] + ": " + ", ".join(item["objectives"]) for item in quest_gaps) + "." if quest_gaps else "")
         + (" Explicit-request gaps: " + ", ".join(dict.fromkeys(item["code"] for item in request_gaps)) + ". Bounded wording/structure checks are not semantic acceptance." if request_gaps else "")},
    ]
    blockers = [metric["label"] for metric in metrics if not metric["passed"]]
    if recovered_sections:
        blockers.append("Recovered output")
    if reused_fresh_dialogue:
        blockers.append("Fresh dialogue")
    if request_gaps:
        blockers.append("Request coverage")
    if deferred_sections:
        for metric in metrics:
            metric["detail"] += " Design-only scope: runtime preview explicitly deferred, not assessed as complete or grounded. Runtime release remains blocked."
    if unspecified_sections:
        for metric in metrics:
            metric["detail"] += " NPC memory: Unspecified, not assessed. Scores cover assessed sections only; this is not proof of source absence or a complete memory design."
    return {
        **({"deferred_sections": deferred_sections, "runtime_deferred": True}
           if (review_request or {}).get("defer_runtime") is True else {}),
        **({"unspecified_sections": unspecified_sections, "assessed_sections": required_sections}
           if (review_request or {}).get("allow_unspecified_memory") is True else {}),
        "metrics": metrics,
        "overall_score": round(sum(metric["value"] for metric in metrics) / len(metrics), 4),
        "passed": not blockers,
        "blockers": blockers,
        "unresolved_assumptions": unresolved,
        "confirmed_assumptions": confirmations,
        "unsupported_sections": unsupported_sections,
        "incomplete_sections": incomplete_sections,
        "quest_integration_gaps": quest_gaps,
        "quest_check_conflicts": quest_conflicts,
        "recovered_sections": recovered_sections,
        "request_coverage_gaps": request_gaps,
    }


_CRITIC_REFERENCE_FAILURE = "Critic reference validation failed; an independently anchored critique is required."


def memory_is_unspecified(content, review_request):
    """Human-owned scope, not proof that the sources contain no memory rules."""
    section = content.get("npc_memory_design", {})
    return ((review_request or {}).get("allow_unspecified_memory") is True
            and not _has_design_content(section.get("content")) and not section.get("citations")
            and any(isinstance(warning, str) and warning.strip() for warning in section.get("warnings", [])))


def critic_reference_errors(critique, content, evidence):
    """Check identity and legacy correction validity, not natural-language entailment."""
    from fastapi import HTTPException
    from app.design_agent.finding_reviews import _artifact_value

    errors = []
    by_id = {str(item["chunk_id"]): item for item in evidence or []}
    detection_only = critique.get("review_mode") == "defect_detection"
    for index, finding in enumerate(critique.get("findings", [])):
        reference = finding.get("reference")
        try:
            if not reference:
                raise ValueError("missing exact field reference")
            reference = (DefectReference if detection_only else CritiqueReference).model_validate(reference).model_dump()
            path = reference["artifact_path"]
            current = _artifact_value(content, path)
            if path.split("/")[1] != finding["section"]:
                raise ValueError("field is outside the finding section")
            if type(current) is not type(reference["artifact_value"]) or current != reference["artifact_value"]:
                raise ValueError("reference does not match the current field")
            if not detection_only and current == reference["replacement"]:
                raise ValueError("proposed correction is a no-op")
            chunk_id, quote = reference.get("evidence_chunk_id"), reference.get("evidence_quote")
            if chunk_id is not None or quote is not None:
                if not chunk_id or not quote or quote not in by_id.get(chunk_id, {}).get("content", ""):
                    raise ValueError("evidence quote is absent from the frozen excerpt")
        except (HTTPException, KeyError, TypeError, ValueError) as error:
            errors.append(f"Finding {index + 1}: {getattr(error, 'detail', None) or str(error)}")
    return errors


def complete_design_critique(
    critique: dict[str, Any], content: dict[str, Any], *,
    review_request: dict[str, Any] | None = None, evidence: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Add objective completeness blockers without censoring independent findings."""
    reviewed = CritiqueOutput.model_validate(critique).model_dump()
    scorecard = assess_artifact_quality(content, review_request=review_request, evidence=evidence)
    if (review_request or {}).get("design_contract_version") == 2:
        # The workflow merges checks twice; never validate our own synthetic blocker as model output.
        model_findings = [item for item in reviewed["findings"] if item["issue"] != _CRITIC_REFERENCE_FAILURE]
        errors = critic_reference_errors({**reviewed, "findings": model_findings}, content, evidence)
        if errors and not any(item["issue"] == _CRITIC_REFERENCE_FAILURE for item in reviewed["findings"]):
            reviewed["findings"].append({"severity": "high", "section": "review",
                "issue": _CRITIC_REFERENCE_FAILURE, "recommendation": "; ".join(errors)})
    for gap in scorecard["request_coverage_gaps"]:
        if not any(item["section"] == gap["section"] and item["issue"] == gap["issue"] for item in reviewed["findings"]):
            reviewed["findings"].append({
                "severity": "high", "section": gap["section"], "issue": gap["issue"],
                "recommendation": "Revise against the original human request and cited evidence. Proposal confirmation cannot supply missing source facts, dialogue or transition instructions. Review the corrected content separately.",
            })
    for conflict in scorecard["quest_check_conflicts"]:
        issue = (f"Quest '{conflict['record']}' has mirrored completion checks: when both required flags are true "
                 f"({', '.join(conflict['state'])}), both checks are false: {'; '.join(conflict['checks'])}.")
        if not any(item["section"] == "quest_hooks" and item["issue"] == issue for item in reviewed["findings"]):
            reviewed["findings"].append({
                "severity": "high", "section": "quest_hooks", "issue": issue,
                "recommendation": "Keep each required action recorded independently, define final success using all required records, and check both action orders. Do not confirm away the contradiction.",
            })
    for gap in scorecard["quest_integration_gaps"]:
        issue = f"Quest '{gap['record']}' lacks event/state/check coverage for objective(s): {', '.join(gap['objectives'])}."
        if not any(item["section"] == "quest_hooks" and item["issue"] == issue for item in reviewed["findings"]):
            reviewed["findings"].append({
                "severity": "high", "section": "quest_hooks", "issue": issue,
                "recommendation": "Supply a structured quest state contract covering each objective; preserve source-supported mechanics and label event bindings as proposals.",
            })
    for section in scorecard["incomplete_sections"]:
        pending_coverage = ((review_request or {}).get("design_contract_version") == 2
                            and not content[section].get("citations") and bool(content[section].get("warnings")))
        issue = ("Source coverage for this empty section needs review; a draft warning does not establish source absence."
                 if pending_coverage else "Design content is empty; citations and warnings do not fill this section.")
        if not any(item["section"] == section and item["issue"] == issue for item in reviewed["findings"]):
            reviewed["findings"].append({
                "severity": "medium" if pending_coverage else "high", "section": section, "issue": issue,
                "recommendation": ("Review the frozen sources and record the human scope decision. Keep genuinely unspecified content unknown; do not invent facts to fill a score. Approval remains blocked pending source/scope review."
                                   if pending_coverage else "Populate source-supported design content or obtain the missing design input; do not invent facts to fill the gap."),
            })
    if reviewed["verdict"] == "ready_for_review" and any(
        item["severity"] == "high" for item in reviewed["findings"]
    ):
        reviewed["verdict"] = "needs_revision"
        reviewed["summary"] = (
            f"{reviewed['summary'].rstrip()} "
            "High-severity findings require revision before human approval."
        )
    reviewed["quality_scorecard"] = scorecard
    return reviewed


def validate_design_approval(
    content: dict[str, Any], evidence: list[dict[str, Any]], critique: dict[str, Any],
    confirmed_proposals: list[dict[str, Any]] | None = None,
    *, review_request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Shared API/worker gate; acceptance resolves proposals, never factual defects."""
    if critique.get("verdict") != "ready_for_review" or any(
        finding.get("severity") == "high" for finding in critique.get("findings", [])
    ):
        raise ValueError("Independent critique must be resolved.")
    if (review_request or {}).get("design_contract_version") == 2 and critic_reference_errors(critique, content, evidence):
        raise ValueError(_CRITIC_REFERENCE_FAILURE)
    historical = critique.get("quality_scorecard") or {}
    # Only the proposal-related blocker can be satisfied by this new action.
    blockers = [item for item in historical.get("blockers", []) if item != "Integration readiness"]
    if blockers or (historical and not historical.get("passed") and not historical.get("blockers")):
        raise ValueError(", ".join(blockers) or "Historical quality review must be resolved.")
    # Normalization adds helper notes; those must not make an incomplete frozen
    # draft approvable merely because its proposals were accepted.
    current_scorecard = assess_artifact_quality(content, confirmed_proposals, review_request=review_request, evidence=evidence)
    if not current_scorecard["passed"]:
        raise ValueError(", ".join(current_scorecard["blockers"]))
    validated = validate_generated_blueprint(content, evidence, require_actionable=True,
        design_contract_version=(review_request or {}).get("design_contract_version", 1))
    validated = ground_blueprint_citations(validated, evidence)
    scorecard = assess_artifact_quality(validated, confirmed_proposals, review_request=review_request, evidence=evidence)
    if not scorecard["passed"]:
        raise ValueError(", ".join(scorecard["blockers"]))
    return scorecard


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
    *, dialogue_policy: str | None = None, fresh_dialogue: bool | None = None,
    design_contract_version: int = 1,
) -> dict[str, Any]:
    """Reject retrieval metadata presented as a developer-facing design artifact.

    A sparse GDD is valid: its section can be an empty structured list with a
    warning. What is not valid is returning a raw evidence record in place of
    an NPC, quest, gameplay, or level design section.
    """
    contract = GovernedBlueprintContent if design_contract_version == 2 else BlueprintContent
    validated = contract.model_validate(content).model_dump()
    for npc in validated["npc_archetypes"]["content"]["npcs"]:
        if fresh_dialogue is not None:
            npc["fresh_dialogue"] = fresh_dialogue
        if dialogue_policy is not None:
            # Run-level human direction is immutable across model revisions.
            # Do not parse prose or infer which game events reset a warning.
            npc["dialogue_triggers"] = [
                DialogueTriggerMapping.model_validate({**mapping, "repeat_policy": dialogue_policy}).model_dump()
                for mapping in npc["dialogue_triggers"]
            ]
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
        _validate_npc_identities(validated, evidence_by_id)
        _mark_generated_dialogue_for_review(validated, evidence_by_id)
        _mark_generated_quest_details_for_review(validated, evidence_by_id)
        for npc in validated["npc_archetypes"]["content"]["npcs"]:
            hooks = npc["dialogue_hooks"]
            spoken_hooks = [hook for hook in hooks if not re.fullmatch(r"[A-Za-z][A-Za-z0-9]*_[A-Za-z0-9_]+", hook.strip())]
            if len(spoken_hooks) != len(hooks):
                validated["npc_archetypes"]["warnings"].append(
                    "Removed trigger identifiers from dialogue hooks; provide actual spoken lines before approval."
                )
            hooks = spoken_hooks
            npc["dialogue_hooks"] = hooks
            complete_hooks = [hook for hook in hooks if not _looks_truncated_dialogue(hook)]
            if len(complete_hooks) != len(hooks):
                npc["dialogue_hooks"] = complete_hooks
                validated["npc_archetypes"]["warnings"].append(
                    f"Removed {len(hooks) - len(complete_hooks)} truncated dialogue hook(s) before review."
                )
        required = actionable_sections or {"npc_archetypes", "quest_hooks"}
        _validate_dialogue_triggers(
            validated, require_actionable and "npc_archetypes" in required,
        )
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
    _mark_scene_integration_proposals(validated)
    _add_integration_steps(validated, design_contract_version=design_contract_version)
    return validated


def review_targets(rejection_reason: str, target_sections: list[str] | None = None) -> list[str]:
    """Explicit scope wins; conservative prose support is for old checkpoints only."""
    if target_sections is not None:
        if not target_sections or any(name not in BLUEPRINT_SECTION_KEYS for name in target_sections):
            raise ValueError("Select at least one valid blueprint section for revision.")
        return list(dict.fromkeys(target_sections))
    reason = rejection_reason.lower()
    only = re.search(r"\b(?:revise|update|change|correct|fix)\s+only\s+([^.;\n]+)", reason)
    if only:
        reason = only.group(1)
    else:
        # Do not interpret exclusions or preservation clauses as authorization.
        reason = " ".join(
            clause for clause in re.split(r"[.;\n]|\bbut\b", reason)
            if not re.search(r"\b(?:do not|don't|does not|must not|without|preserve|keep|unchanged|leave)\b", clause)
        )
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


_REVISION_METADATA_KEYS = {
    "human_revision", "review_directive", "review_adjustments", "assumptions",
    "source_chunk_ids", "implementation_notes", "manual_test", "fresh_dialogue",
}


def _revision_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).translate(str.maketrans({
        "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-",
        "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
    }))
    return " ".join(text.casefold().split())


def _revision_design_content(value: Any, key: str = "") -> Any:
    """Ignore review bookkeeping and typography, but preserve runtime identifiers."""
    if isinstance(value, dict):
        return {name: _revision_design_content(item, name) for name, item in value.items()
                if name not in _REVISION_METADATA_KEYS}
    if isinstance(value, list):
        return [_revision_design_content(item, key) for item in value]
    if isinstance(value, str) and key not in {"id", "trigger", "target_id", "npc_slug", "target_type", "flag", "required_flags", "clear_flags"}:
        return _revision_text(value)
    return value


def _authored_integration_notes(value: Any) -> set[str]:
    """Collect substantive notes, excluding server boilerplate and typography."""
    if isinstance(value, list):
        return set().union(*(_authored_integration_notes(item) for item in value))
    if not isinstance(value, dict):
        return set()
    notes = set()
    for note in value.get("implementation_notes", []):
        generated = (
            note.startswith(("Create a stable NPC profile for '", "Dialogue trigger proposal '"))
            or (note.startswith("Use '") and note.endswith(
                "' as the stable design key and map objectives in their listed order to game events."))
            or note in {
                "Use dialogue hooks as first-contact lines; keep scene triggers and presentation client-side.",
                "Map failure states to explicit quest-state transitions; do not infer rewards or prerequisites from assumptions.",
                "Do not implement listed assumptions until a designer confirms them.",
            }
        )
        if not generated and (normalised := _revision_text(note)):
            notes.add(normalised)
    for key, item in value.items():
        if key not in _REVISION_METADATA_KEYS:
            notes.update(_authored_integration_notes(item))
    return notes


def _without_implementation_notes(value: Any) -> Any:
    """Exact preservation check for a focused notes-only correction."""
    if isinstance(value, dict):
        return {key: _without_implementation_notes(item) for key, item in value.items()
                if key != "implementation_notes"}
    if isinstance(value, list):
        return [_without_implementation_notes(item) for item in value]
    return value


OFFLINE_REVISION_UNAVAILABLE = "The offline provider cannot make this correction. Use a hosted provider or start a new run."


class NoMaterialRevisionError(ValueError):
    """A revision changed only bookkeeping, not the requested design content."""


def validate_structured_revision(
    before: dict[str, Any],
    after: dict[str, Any],
    rejection_reason: str,
    target_sections: list[str] | None = None,
    *, evidence: list[dict[str, Any]] | None = None,
) -> str:
    """Require a material change in every selected section, with no unrelated drift.

    This rejects partial/no-op revisions; it does not prove that arbitrary prose
    instructions were satisfied. Critique and human review still assess intent.
    """
    targets = set(review_targets(rejection_reason, target_sections))
    before_validated = BlueprintContent.model_validate(before).model_dump()
    after_validated = BlueprintContent.model_validate(after).model_dump()
    # Revision must not silently downgrade a typed contract to ambiguous prose.
    revised_quests = {quest["id"]: quest for quest in after_validated["quest_hooks"]["content"]["quests"]}
    for quest in before_validated["quest_hooks"]["content"]["quests"]:
        revised = revised_quests.get(quest["id"])
        if quest.get("state_contract") and revised and not revised.get("state_contract"):
            raise ValueError(f"Revision removed the state contract for quest '{quest['title']}'.")

    # Removing a rejected instruction can itself be the requested correction.
    # Permit that only for a pure notes edit; do not let deletion elsewhere
    # disguise a partial rewrite (for example, a retained invented quest timer).
    notes_only = all(
        _without_implementation_notes(before_validated[target])
        == _without_implementation_notes(after_validated[target])
        for target in targets
    )
    changed_targets = []
    for target in targets:
        before_target = before_validated[target]["content"]
        after_target = after_validated[target]["content"]
        before_notes = _authored_integration_notes(before_target)
        after_notes = _authored_integration_notes(after_target)
        note_changes = (before_notes ^ after_notes) if notes_only else (after_notes - before_notes)
        allowed_ids = {str(item["chunk_id"]) for item in evidence or [] if target in (item.get("matched_sections") or [])}
        before_ids = set(before_validated[target]["citations"])
        after_ids = set(after_validated[target]["citations"])
        citation_repair = bool(_has_design_content(after_target) and after_ids
                               and after_ids <= allowed_ids and not before_ids & allowed_ids)
        if (_revision_design_content(before_target) != _revision_design_content(after_target)
                or note_changes or citation_repair):
            changed_targets.append(target)
    unchanged_targets = targets - set(changed_targets)
    if unchanged_targets:
        error_type = ValueError if changed_targets else NoMaterialRevisionError
        raise error_type(
            "Revision did not materially change every human-targeted section; unchanged: "
            + ", ".join(sorted(unchanged_targets))
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
