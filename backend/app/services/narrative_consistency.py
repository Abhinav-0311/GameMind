import logging
from typing import Dict, Tuple, Optional
from sqlalchemy.orm import Session
from app.services.contradiction_engine import contradiction_engine
from app.services.telemetry_service import TelemetryService

logger = logging.getLogger("gamemind.narrative_consistency")

class NarrativeConsistencyService:
    @staticmethod
    def check_consistency(db: Session, claim: Dict[str, str], game_project_id: str = "default_project") -> Tuple[bool, Optional[str]]:
        """
        Evaluates a structured claim against active world relationships in the graph database.
        Schema: {"subject": "<entity_slug>", "predicate": "<relationship_type>", "object": "<entity_slug>"}
        Returns:
            (True, None) if consistent.
            (False, contradiction_details) if a contradiction is detected.
        """
        subject = claim.get("subject")
        predicate = claim.get("predicate")
        obj = claim.get("object")
        
        if not subject or not predicate or not obj:
            return False, "Invalid claim structure. Must include 'subject', 'predicate', and 'object'."

        # Record consistency check in telemetry
        TelemetryService.record_narrative_metric(
            db,
            action_type="narrative_consistency_checks_total",
            npc_slug=subject,
            model_used=predicate,
            error_str=None
        )

        is_conflict, reason = contradiction_engine.check_contradiction(db, subject, obj, predicate, game_project_id=game_project_id)
        if is_conflict:
            # Record failure in telemetry
            TelemetryService.record_narrative_metric(
                db,
                action_type="narrative_consistency_failures_total",
                npc_slug=subject,
                model_used=predicate,
                error_str=reason
            )
            return False, reason
            
        return True, None
