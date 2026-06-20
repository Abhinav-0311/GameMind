import logging
import uuid
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.models.graph import WorldEntity, WorldEntityVersion, WorldRelationship
from app.services.event_scheduler import WorldEventScheduler
from app.services.telemetry_service import TelemetryService

logger = logging.getLogger("gamemind.narrative_forecasting")

class NarrativeForecaster:
    MAX_FORECAST_DEPTH = 5

    @classmethod
    def forecast_trends(cls, db: Session, steps: int) -> List[Dict[str, Any]]:
        """
        Projects likely future world state updates up to steps (MAX_FORECAST_DEPTH = 5).
        Returns a list of trend dicts containing a confidence score [0.0 - 1.0].
        """
        # Enforce boundary checks
        clamped_steps = max(1, min(cls.MAX_FORECAST_DEPTH, steps))

        # Record generated forecast in telemetry
        TelemetryService.record_narrative_metric(
            db,
            action_type="narrative_forecasts_generated_total",
            npc_slug="system",
            model_used="forecast_trends",
            input_tokens=1
        )
        TelemetryService.record_narrative_metric(
            db,
            action_type="narrative_forecast_depth_reached",
            npc_slug="system",
            model_used="forecast_trends",
            input_tokens=clamped_steps
        )

        trends: List[Dict[str, Any]] = []

        # Simple projection modeling: we look up active event templates and evaluate
        # their conditions to forecast which ones are likely to trigger in subsequent steps.
        # To simulate progression, we estimate standing drifts.
        templates = db.query(WorldEntity).filter(
            WorldEntity.entity_type == "event_template"
        ).all()

        for temp in templates:
            active_ver = db.query(WorldEntityVersion).filter(
                WorldEntityVersion.entity_id == temp.id,
                WorldEntityVersion.valid_to.is_(None)
            ).first()

            if not active_ver or not active_ver.properties:
                continue

            properties = active_ver.properties
            conditions = properties.get("conditions", {})
            effects = properties.get("effects", {})

            # Calculate confidence score based on condition thresholds
            confidence = 1.0
            affected_entities: List[str] = []

            standing_below = conditions.get("standing_below")
            if standing_below:
                source = standing_below.get("source")
                target = standing_below.get("target")
                val = standing_below.get("value")
                
                # Fetch active relationship
                from app.repositories.graph_repository import graph_repo
                rel = graph_repo.get_active_relationship(db, source, target, "standing")
                weight = rel.weight if rel else 50.0
                
                # If weight is close to val, confidence is higher that it will trigger soon
                # Let's map this linearly
                diff = val - weight
                if diff > 0:
                    confidence = min(1.0, max(0.1, 1.0 - (diff / 100.0)))
                else:
                    # Not met but close: standing is above, but if it's within 10 units:
                    if abs(diff) < 10.0:
                        confidence = 0.3
                    else:
                        confidence = 0.05
                
                affected_entities.extend([source, target])

            # Gather affected entities from effects
            standing_shift = effects.get("standing_shift")
            if standing_shift:
                affected_entities.extend([standing_shift.get("source"), standing_shift.get("target")])

            reputation_shift = effects.get("reputation_shift")
            if reputation_shift:
                affected_entities.extend([reputation_shift.get("faction"), reputation_shift.get("entity")])

            # Filter unique non-None slugs
            clean_affected = list(set([slug for slug in affected_entities if slug]))

            # Only report trends with non-zero confidence
            if confidence > 0.0:
                trends.append({
                    "trend_id": str(uuid.uuid4()),
                    "predicted_state_change": f"Event template '{active_ver.name}' triggers, affecting standings.",
                    "confidence_score": round(confidence, 2),
                    "affected_entities": clean_affected
                })

        # Cap predictions returned based on clamped steps (bounded branching)
        # We sort by confidence score and return the top trends
        trends.sort(key=lambda x: x["confidence_score"], reverse=True)
        return trends[:clamped_steps * 2]
