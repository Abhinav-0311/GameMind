import re
from typing import Iterable

from app.models.design_decision import DesignDecision
from app.models.document import Document


class TechnicalBriefTemplateService:
    """Builds an editable local template without inventing production decisions."""

    @staticmethod
    def _filename(title: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_") or "game"
        return f"{slug}_technical_brief.md"

    def build(self, source: Document, decisions: Iterable[DesignDecision]) -> dict[str, str]:
        technical_decisions = [
            decision
            for decision in decisions
            if decision.status == "open" and decision.recommended_source_kind == "technical_brief"
        ]
        lines = [
            f"# Technical Brief: {source.title}",
            "",
            "## Purpose",
            "Record implementation choices that the primary GDD intentionally leaves open.",
            "Replace every bracketed placeholder with a concrete team decision before uploading this file to GameMind.",
            "",
            "## Source context",
            f"- Primary source: {source.title} (revision {source.revision_number})",
            "",
        ]

        if technical_decisions:
            lines.extend(["## Decisions to resolve", ""])
            for decision in technical_decisions:
                lines.extend([
                    f"### {decision.title}",
                    decision.guidance or "Record the implementation boundary for this decision.",
                    "- Decision: [Choose and explain the MVP boundary]",
                    "- Implementation notes: [Record APIs, local fallback, devices, or constraints]",
                    "- Verification: [State how the team will test this choice]",
                    "",
                ])
        else:
            lines.extend([
                "## Technical decisions",
                "- Decision: [Record the technical choice this brief supports]",
                "- Implementation notes: [Record constraints and fallback behavior]",
                "- Verification: [State how the team will test it]",
                "",
            ])

        lines.extend([
            "## Delivery baseline",
            "- MVP build target: [Choose one target platform and mode]",
            "- Deferred platforms or modes: [List what is intentionally postponed]",
            "- Performance target: [Choose a measurable target for the selected device]",
            "- Offline or failure behavior: [Describe what happens when an online service is unavailable]",
            "- Accessibility commitments: [List the supported options and their test cases]",
            "",
        ])
        return {"filename": self._filename(source.title), "content": "\n".join(lines)}
