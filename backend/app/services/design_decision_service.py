import re
from typing import List
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import case
from sqlalchemy.orm import Session

from app.models.design_decision import DesignDecision
from app.models.document import Document
from app.services.gdd_review_service import GddReviewService


class DesignDecisionService:
    """Synchronizes actionable review gaps into human-owned design decisions."""

    @staticmethod
    def _category(title: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
        return normalized[:100]

    def list_for_document(self, db: Session, document_id: UUID, game_project_id: str) -> List[DesignDecision]:
        priority_order = case(
            (DesignDecision.priority == "critical", 0),
            (DesignDecision.priority == "high", 1),
            (DesignDecision.priority == "medium", 2),
            else_=3,
        )
        return db.query(DesignDecision).filter(
            DesignDecision.document_id == document_id,
            DesignDecision.game_project_id == game_project_id,
        ).order_by(DesignDecision.status.asc(), priority_order.asc(), DesignDecision.created_at.asc()).all()

    def sync_from_review(self, db: Session, document_id: UUID, game_project_id: str) -> List[DesignDecision]:
        review = GddReviewService().review(db, document_id, game_project_id)
        actionable = [finding for finding in review["findings"] if finding["severity"] in {"needs_decision", "conflict"}]
        existing = {
            decision.category: decision
            for decision in self.list_for_document(db, document_id, game_project_id)
        }

        for finding in actionable:
            category = self._category(finding["title"])
            decision = existing.get(category)
            if not decision:
                decision = DesignDecision(
                    game_project_id=game_project_id,
                    document_id=document_id,
                    category=category,
                    title=finding["title"],
                    guidance=finding["guidance"] or finding["message"],
                    severity=finding["severity"],
                    priority=finding["priority"],
                    recommended_source_kind=finding["recommended_source_kind"],
                )
                db.add(decision)
                continue

            decision.title = finding["title"]
            decision.guidance = finding["guidance"] or finding["message"]
            decision.severity = finding["severity"]
            decision.priority = finding["priority"]
            decision.recommended_source_kind = finding["recommended_source_kind"]

        db.commit()
        return self.list_for_document(db, document_id, game_project_id)

    def update(
        self,
        db: Session,
        decision_id: UUID,
        game_project_id: str,
        decision_text: str | None,
        decision_status: str | None,
    ) -> DesignDecision:
        decision = db.query(DesignDecision).filter(
            DesignDecision.id == decision_id,
            DesignDecision.game_project_id == game_project_id,
        ).first()
        if not decision:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Design decision not found or not owned by this project.")

        if decision_text is not None:
            decision.decision = decision_text.strip() or None
        if decision_status is not None:
            decision.status = decision_status

        db.commit()
        db.refresh(decision)
        return decision

    def coverage(self, db: Session, document_id: UUID, game_project_id: str) -> dict:
        """Assess the latest decision per category against one source revision."""
        document = db.query(Document).filter(
            Document.id == document_id,
            Document.game_project_id == game_project_id,
        ).first()
        if not document:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source document not found or not owned by this project.")

        root_id = document.source_document_id or document.id
        lineage_ids = [
            row[0]
            for row in db.query(Document.id).filter(
                Document.game_project_id == game_project_id,
                (Document.id == root_id) | (Document.source_document_id == root_id),
            ).all()
        ]
        candidates = db.query(DesignDecision, Document.revision_number).join(
            Document, DesignDecision.document_id == Document.id
        ).filter(
            DesignDecision.game_project_id == game_project_id,
            DesignDecision.document_id.in_(lineage_ids),
        ).order_by(Document.revision_number.desc(), DesignDecision.updated_at.desc()).all()

        latest_by_category = {}
        for decision, revision_number in candidates:
            latest_by_category.setdefault(decision.category, (decision, revision_number))

        review = GddReviewService().review(db, document.id, game_project_id)
        review_by_category = {
            self._category(finding["title"]): finding
            for finding in review["findings"]
        }
        items = []
        for category, (decision, origin_revision) in latest_by_category.items():
            finding = review_by_category.get(category)
            if decision.status == "open":
                evidence_status = "decision_open"
                citations = []
            elif finding and finding["severity"] == "covered":
                evidence_status = "source_backed"
                citations = finding["citations"]
            else:
                evidence_status = "needs_source_evidence"
                citations = []
            items.append({
                "decision_id": decision.id,
                "title": decision.title,
                "decision": decision.decision,
                "status": decision.status,
                "origin_revision_number": origin_revision,
                "evidence_status": evidence_status,
                "citations": citations,
            })

        summary = {
            "source_backed": sum(item["evidence_status"] == "source_backed" for item in items),
            "needs_source_evidence": sum(item["evidence_status"] == "needs_source_evidence" for item in items),
            "decision_open": sum(item["evidence_status"] == "decision_open" for item in items),
        }
        return {
            "document_id": document.id,
            "revision_number": document.revision_number,
            "summary": summary,
            "items": items,
        }
