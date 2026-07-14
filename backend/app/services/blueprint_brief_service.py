import json
from typing import Any, Dict, Iterable
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.blueprint import GameBlueprint
from app.models.document import Document, DocumentChunk
from app.services.blueprint_readiness import BlueprintReadinessService
from app.services.design_decision_service import DesignDecisionService


class BlueprintBriefService:
    """Build a portable, source-grounded Markdown project brief."""

    SECTIONS = (
        ("Game summary", "summary"),
        ("Narrative direction", "narrative_direction"),
        ("Art style direction", "art_style_direction"),
        ("NPC design", "npc_archetypes"),
        ("Memory design", "npc_memory_design"),
        ("Level design", "level_design_suggestions"),
        ("Gameplay systems", "gameplay_systems"),
        ("Quest hooks", "quest_hooks"),
        ("Runtime preview", "unity_runtime_preview"),
    )

    @staticmethod
    def _value_lines(content: Dict[str, Any]) -> Iterable[str]:
        for key, value in content.items():
            label = key.replace("_", " ").capitalize()
            if value in (None, "", [], {}):
                continue
            if isinstance(value, list):
                yield f"- **{label}:**"
                for item in value:
                    if isinstance(item, dict):
                        summary = item.get("title") or item.get("name") or item.get("objective") or json.dumps(item, ensure_ascii=True)
                        yield f"  - {summary}"
                    else:
                        yield f"  - {item}"
            elif isinstance(value, dict):
                yield f"- **{label}:** {json.dumps(value, ensure_ascii=True)}"
            else:
                yield f"- **{label}:** {value}"

    @staticmethod
    def _source_lines(blueprint: GameBlueprint, db: Session, game_project_id: str) -> list[str]:
        source_ids = blueprint.source_document_ids or ([] if not blueprint.document_id else [str(blueprint.document_id)])
        if not source_ids:
            return ["- No source document is attached to this blueprint."]
        documents = db.query(Document).filter(
            Document.id.in_(source_ids),
            Document.game_project_id == game_project_id,
        ).all()
        by_id = {str(document.id): document for document in documents}
        return [
            f"- {by_id[source_id].title} (revision {by_id[source_id].revision_number}, {by_id[source_id].source_kind})"
            for source_id in source_ids
            if source_id in by_id
        ] or ["- Source records are unavailable."]

    def build(self, db: Session, blueprint: GameBlueprint, game_project_id: str) -> str:
        citation_ids = set()
        sections = []
        for label, field in self.SECTIONS:
            section = getattr(blueprint, field) or {}
            content = section.get("content", {}) if isinstance(section, dict) else {}
            citations = section.get("citations", []) if isinstance(section, dict) else []
            citation_ids.update(str(citation) for citation in citations)
            sections.append((label, content, [str(citation) for citation in citations], section.get("warnings", []) if isinstance(section, dict) else []))

        parsed_citation_ids = [UUID(citation) for citation in citation_ids]
        citation_rows = db.query(DocumentChunk, Document).join(
            Document, DocumentChunk.document_id == Document.id
        ).filter(
            DocumentChunk.id.in_(parsed_citation_ids),
            Document.game_project_id == game_project_id,
        ).all() if parsed_citation_ids else []
        citations = {
            str(chunk.id): f"{document.title} (revision {document.revision_number}, chunk {chunk.chunk_index + 1})"
            for chunk, document in citation_rows
        }
        readiness = BlueprintReadinessService().assess(blueprint)
        decision_coverage = (
            DesignDecisionService().coverage(db, blueprint.document_id, game_project_id)
            if blueprint.document_id else {"items": []}
        )

        lines = [
            f"# {blueprint.title}",
            "",
            "## Blueprint status",
            f"- Status: {blueprint.status}",
            f"- Runtime readiness: {readiness['status']}",
            f"- GameMind project: {game_project_id}",
            "",
            "## Sources",
            *self._source_lines(blueprint, db, game_project_id),
            "",
            "## Design decisions",
        ]

        if decision_coverage["items"]:
            for item in decision_coverage["items"]:
                lines.append(f"- **{item['title']}**: {item['evidence_status'].replace('_', ' ')}")
                if item["decision"]:
                    lines.append(f"  - Decision: {item['decision']}")
        else:
            lines.append("- No tracked design decisions for this source lineage.")

        for label, content, section_citations, warnings in sections:
            lines.extend(["", f"## {label}"])
            value_lines = list(self._value_lines(content))
            lines.extend(value_lines or ["- No explicit source detail was extracted."])
            if warnings:
                lines.append("- **Review notes:** " + "; ".join(warnings))
            if section_citations:
                lines.append("- **Evidence:** " + "; ".join(citations[citation] for citation in section_citations if citation in citations))

        return "\n".join(lines).strip() + "\n"
