import json
from typing import Any, Dict, Iterable
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.blueprint import GameBlueprint
from app.models.document import Document, DocumentChunk
from app.services.blueprint_readiness import BlueprintReadinessService
from app.services.design_decision_service import DesignDecisionService
from app.design_agent.grounding import memory_is_unspecified


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
                        summary_key = next((key for key in ("title", "name", "objective") if item.get(key)), None)
                        summary = item[summary_key] if summary_key else json.dumps(item, ensure_ascii=True)
                        yield f"  - {summary}"
                        if summary_key:
                            contract_fields = {"state_contract", "implementation_notes", "assumptions"} if item.get("state_contract") else set()
                            details = {key: value for key, value in item.items() if key != summary_key and key not in contract_fields}
                            for line in BlueprintBriefService._value_lines(details):
                                yield f"    {line}"
                        if item.get("state_contract"):
                            yield "    - **Quest state contract (design proposal, not runtime bindings):**"
                            yield ""
                            yield "      ```json"
                            for line in json.dumps(item["state_contract"], ensure_ascii=True, indent=2).splitlines():
                                yield f"      {line}"
                            yield "      ```"
                            yield ""
                            for note in item.get("implementation_notes", []):
                                yield f"    - Integration note: {note}"
                            for assumption in item.get("assumptions", []):
                                yield f"    - Review/proposal note: {assumption}"
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
            Document.id.in_([UUID(str(source_id)) for source_id in source_ids]),
            Document.game_project_id == game_project_id,
        ).all()
        by_id = {str(document.id): document for document in documents}
        return [
            f"- {by_id[source_id].title} (revision {by_id[source_id].revision_number}, {by_id[source_id].source_kind})"
            for source_id in source_ids
            if source_id in by_id
        ] or ["- Source records are unavailable."]

    def build(self, db: Session, blueprint: GameBlueprint, game_project_id: str,
              *, frozen_context: dict[str, Any] | None = None) -> str:
        citation_ids = set()
        sections = []
        for label, field in self.SECTIONS:
            section = (frozen_context["content"][field] if frozen_context is not None else getattr(blueprint, field)) or {}
            content = section.get("content", {}) if isinstance(section, dict) else {}
            citations = section.get("citations", []) if isinstance(section, dict) else []
            citation_ids.update(str(citation) for citation in citations)
            sections.append((label, content, [str(citation) for citation in citations], section.get("warnings", []) if isinstance(section, dict) else []))

        if frozen_context is not None:
            citations = {str(item["chunk_id"]): f"{item['title']} (frozen excerpt {item['chunk_id']})"
                         for item in frozen_context["evidence"]}
            source_lines = list(dict.fromkeys(
                f"- {item['title']} (frozen source {item.get('document_id', 'not recorded')})"
                for item in frozen_context["evidence"])) or ["- No source excerpts were frozen for this run."]
            decision_coverage = {"items": [{"title": item["title"], "decision": item["decision"],
                                           "evidence_status": "frozen_resolved"}
                                          for item in frozen_context["decisions"]]}
        else:
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
            source_lines = self._source_lines(blueprint, db, game_project_id)
            decision_coverage = (
                DesignDecisionService().coverage(db, blueprint.document_id, game_project_id)
                if blueprint.document_id else {"items": []}
            )
        readiness = BlueprintReadinessService().assess(blueprint)
        memory = frozen_context["content"]["npc_memory_design"] if frozen_context is not None else blueprint.npc_memory_design

        lines = [
            f"# {blueprint.title}",
            "",
            "## Blueprint status",
            f"- Status: {blueprint.status}",
            f"- Current runtime readiness: {readiness['status']}" if frozen_context is not None else f"- Runtime readiness: {readiness['status']}",
            f"- GameMind project: {game_project_id}",
            *([f"- Run: {frozen_context['run_id']}",
               f"- Approved artifact: {frozen_context['artifact_id']} (version {frozen_context['artifact_version']})",
               f"- Frozen evidence snapshot: {frozen_context['snapshot_id']}"] if frozen_context is not None else []),
            "",
            "## Sources",
            *source_lines,
            "",
            "## Design decisions",
        ]

        if decision_coverage["items"]:
            for item in decision_coverage["items"]:
                lines.append(f"- **{item['title']}**: {item['evidence_status'].replace('_', ' ')}")
                if item["decision"]:
                    lines.append(f"  - Decision: {item['decision']}")
        else:
            lines.append("- No resolved design decisions are recorded for this run." if frozen_context is not None
                         else "- No tracked design decisions for this source lineage.")

        for label, content, section_citations, warnings in sections:
            lines.extend(["", f"## {label}"])
            if (label == "Memory design" and (memory or {}).get("memory_unspecified") is True
                    and memory_is_unspecified({"npc_memory_design": memory}, {"allow_unspecified_memory": True})):
                lines.append("- **Unspecified—not assessed.** This design does not define NPC memory; this is not proof of source absence.")
            value_lines = list(self._value_lines(content))
            lines.extend(value_lines or ["- No explicit source detail was extracted."])
            if warnings:
                lines.append("- **Review notes:** " + "; ".join(warnings))
            if section_citations:
                lines.append("- **Evidence:** " + "; ".join(citations[citation] for citation in section_citations if citation in citations))

        if frozen_context is not None:
            lines.extend(["", "## Frozen evidence"])
            for item in frozen_context["evidence"]:
                lines.extend(["", f"### {citations[str(item['chunk_id'])]}", ""])
                lines.extend("> " + line for line in item["content"].splitlines())
        return "\n".join(lines).strip() + "\n"
