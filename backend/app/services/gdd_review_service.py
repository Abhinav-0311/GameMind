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
        ("Core gameplay loop", r"\b(?:core loop|gameplay loop|mechanics?|player loop)\b", "Describe what the player repeatedly does, why it is rewarding, and how a session advances.", "high", "gdd"),
        ("Progression", r"\b(?:progression|level(?:ling|ing)?|experience|\bxp\b|upgrade|unlock|skill tree)\b", "Define how the player gains capability, access, or mastery over time.", "high", "level_brief"),
        ("Platform and controls", r"\b(?:platforms?|controls?|input|keyboard|controller|gamepad|touchscreen|mouse)\b", "Name the target platform and the primary input assumptions.", "high", "technical_brief"),
        ("Technical constraints", r"\b(?:technical constraints?|performance|frame ?rate|\bfps\b|memory budget|hardware|target device|engine|network(?:ing)?|offline|save system|resolution)\b", "Record engine, performance, save, networking, or hardware constraints that affect scope.", "high", "technical_brief"),
        ("Accessibility", r"\b(?:accessibility|subtitles?|captions?|color ?blind|remapp(?:ing|able)|assist mode|difficulty assist|motion sensitiv(?:ity|e))\b", "Add concrete accessibility requirements such as subtitles, remapping, readable UI, or assist options.", "medium", "technical_brief"),
        ("NPC design", r"\b(?:npc|character|companion|villain|merchant|quest giver)\b", "Identify the first characters, their game role, and why the player interacts with them.", "medium", "npc_sheet"),
        ("Level design", r"\b(?:level design|level|zone|area|map|environment|gate|encounter)\b", "Describe the first playable space, objectives, gates, and interactive elements.", "high", "level_brief"),
        ("Quest or objective design", r"\b(?:quest|objective|mission|goal|reward)\b", "Specify at least one objective, its completion condition, and its player reward.", "medium", "quest_brief"),
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
        for title, pattern, guidance, priority, recommended_source_kind in self.REQUIRED_DECISIONS:
            citations = self._matches(chunks, pattern)
            if citations:
                findings.append({
                    "title": title,
                    "severity": "covered",
                    "message": "The source includes an explicit decision for this area.",
                    "guidance": None,
                    "priority": "low",
                    "recommended_source_kind": None,
                    "citations": citations,
                })
            else:
                findings.append({
                    "title": title,
                    "severity": "needs_decision",
                    "message": "No explicit decision was found in the source.",
                    "guidance": guidance,
                    "priority": priority,
                    "recommended_source_kind": recommended_source_kind,
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
                "priority": "critical",
                "recommended_source_kind": "gdd",
                "citations": self._matches(chunks, r"\b(?:single[ -]?player|solo|multiplayer|co[ -]?op|online play|pvp)\b"),
            })

        delivery_patterns = (
            r"\b(?:pc|windows|mac|linux|console)\b",
            r"\b(?:android|ios|mobile)\b",
            r"\b(?:augmented reality|\bar\b)\b",
            r"\b(?:virtual reality|\bvr\b)\b",
        )
        delivery_matches = [pattern for pattern in delivery_patterns if re.search(pattern, source_text, re.IGNORECASE)]
        if len(delivery_matches) >= 2:
            findings.append({
                "title": "Multi-platform delivery scope",
                "severity": "needs_decision",
                "message": "The source targets multiple delivery modes or device classes.",
                "guidance": "Choose one MVP build target and name which platforms or modes are staged after the first playable release.",
                "priority": "high",
                "recommended_source_kind": "technical_brief",
                "citations": self._matches(chunks, r"\b(?:pc|windows|mac|linux|console|android|ios|mobile|augmented reality|\bar\b|virtual reality|\bvr\b)\b"),
            })

        has_online_feature = bool(re.search(r"\b(?:leaderboard|online|multiplayer|co[ -]?op|pvp)\b", source_text, re.IGNORECASE))
        # A narrative can mention a server without defining how an online feature is
        # delivered. Require an implementation boundary before treating leaderboard
        # or multiplayer scope as covered.
        has_online_boundary = bool(re.search(
            r"\b(?:backend\s+(?:service|api|endpoint|architecture)|"
            r"server[-\s]?(?:authoritative|hosted|endpoint|api)|"
            r"network(?:ing)?\s+(?:architecture|service|layer|stack)|"
            r"online\s+(?:service|backend|api)|"
            r"(?:offline|local)\s+fallback|"
            r"leaderboard\s+(?:service|backend|api))\b",
            source_text,
            re.IGNORECASE,
        ))
        if has_online_feature and not has_online_boundary:
            findings.append({
                "title": "Online feature boundary",
                "severity": "needs_decision",
                "message": "The source includes an online or leaderboard feature without an implementation boundary.",
                "guidance": "Decide whether this feature belongs in the MVP, what it depends on, and what local fallback exists when it is unavailable.",
                "priority": "high",
                "recommended_source_kind": "technical_brief",
                "citations": self._matches(chunks, r"\b(?:leaderboard|online|multiplayer|co[ -]?op|pvp)\b"),
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
