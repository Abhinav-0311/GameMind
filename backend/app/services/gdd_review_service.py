"""Deterministic, source-grounded design review for uploaded GDDs."""

import re
from typing import Dict, Iterable, List
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.document import Document, DocumentChunk


class GddReviewService:
    """Find missing production decisions without inventing design recommendations."""

    REQUIRED_DECISIONS = (
        ("Core gameplay loop", r"\b(?:core loop|gameplay loop|mechanics?|player loop)\b", "Describe what the player repeatedly does, why it is rewarding, and how a session advances."),
        ("Progression", r"\b(?:progression|level(?:ling|ing)?|experience|\bxp\b|upgrade|unlock|skill tree)\b", "Define how the player gains capability, access, or mastery over time."),
        ("Platform and controls", r"\b(?:platforms?|controls?|input|keyboard|controller|gamepad|touchscreen|mouse)\b", "Name the target platform and the primary input assumptions."),
        ("Technical constraints", r"\b(?:technical constraints?|performance|frame ?rate|\bfps\b|memory budget|hardware|target device|engine|network(?:ing)?|offline|save system|resolution)\b", "Record engine, performance, save, networking, or hardware constraints that affect scope."),
        ("Accessibility", r"\b(?:accessibility|subtitles?|captions?|color ?blind|remapp(?:ing|able)|assist mode|difficulty assist|motion sensitiv(?:ity|e))\b", "Add concrete accessibility requirements such as subtitles, remapping, readable UI, or assist options."),
        ("NPC design", r"\b(?:npc|character|companion|villain|merchant|quest giver)\b", "Identify the first characters, their game role, and why the player interacts with them."),
        ("Level design", r"\b(?:level design|level|zone|area|map|environment|gate|encounter)\b", "Describe the first playable space, objectives, gates, and interactive elements."),
        ("Quest or objective design", r"\b(?:quest|objective|mission|goal|reward)\b", "Specify at least one objective, its completion condition, and its player reward."),
    )

    def _chunks(self, db: Session, document_id: UUID) -> List[DocumentChunk]:
        return db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).order_by(DocumentChunk.chunk_index).all()

    @staticmethod
    def _matches(chunks: Iterable[DocumentChunk], pattern: str) -> List[str]:
        return [str(chunk.id) for chunk in chunks if re.search(pattern, chunk.content, re.IGNORECASE)]

    def review(self, db: Session, document_id: UUID, game_project_id: str) -> Dict[str, object]:
        document = db.query(Document).filter(
            Document.id == document_id,
            Document.game_project_id == game_project_id,
        ).first()
        if not document:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source document not found or not owned by this project.")

        chunks = self._chunks(db, document_id)
        if not chunks:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Source document has no indexed text to review.")

        findings = []
        for title, pattern, guidance in self.REQUIRED_DECISIONS:
            citations = self._matches(chunks, pattern)
            if citations:
                findings.append({
                    "title": title,
                    "severity": "covered",
                    "message": "The source includes an explicit decision for this area.",
                    "guidance": None,
                    "citations": citations,
                })
            else:
                findings.append({
                    "title": title,
                    "severity": "needs_decision",
                    "message": "No explicit decision was found in the source.",
                    "guidance": guidance,
                    "citations": [],
                })

        source_text = "\n".join(chunk.content for chunk in chunks)
        has_single_player = bool(re.search(r"\b(?:single[ -]?player|solo)\b", source_text, re.IGNORECASE))
        has_multiplayer = bool(re.search(r"\b(?:multiplayer|co[ -]?op|online play|pvp)\b", source_text, re.IGNORECASE))
        if has_single_player and has_multiplayer:
            findings.append({
                "title": "Player-mode conflict",
                "severity": "conflict",
                "message": "The source mentions both single-player and multiplayer play.",
                "guidance": "Clarify whether these are separate modes, a staged roadmap, or a contradiction in scope.",
                "citations": self._matches(chunks, r"\b(?:single[ -]?player|solo|multiplayer|co[ -]?op|online play|pvp)\b"),
            })

        needs_decision = sum(finding["severity"] == "needs_decision" for finding in findings)
        conflicts = sum(finding["severity"] == "conflict" for finding in findings)
        return {
            "document_id": document.id,
            "title": document.title,
            "revision_number": document.revision_number,
            "summary": {
                "covered": sum(finding["severity"] == "covered" for finding in findings),
                "needs_decision": needs_decision,
                "conflicts": conflicts,
            },
            "findings": findings,
        }
