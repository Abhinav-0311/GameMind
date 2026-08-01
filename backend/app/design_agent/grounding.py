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
