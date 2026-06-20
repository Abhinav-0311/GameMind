import logging
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.graph import WorldEntity, WorldRelationship, WorldEntityVersion
from app.models.quest import QuestProgress
from app.repositories.graph_repository import graph_repo
from app.services.telemetry_service import TelemetryService

logger = logging.getLogger("gamemind.event_scheduler")

class WorldEventScheduler:
    @staticmethod
    def evaluate_triggers(db: Session, current_time: datetime) -> List[Dict[str, Any]]:
        """
        Evaluates active event templates and returns events whose trigger conditions are met.
        Deterministic execution only (no background threads).
        """
        start_time = time.time()
        triggered_events: List[Dict[str, Any]] = []

        # Fetch all active event templates from the graph database
        templates = db.query(WorldEntity).filter(
            WorldEntity.entity_type == "event_template"
        ).all()

        for temp in templates:
            # Increment evaluated telemetry
            TelemetryService.record_narrative_metric(
                db,
                action_type="world_events_evaluated_total",
                npc_slug="system",
                model_used=temp.slug
            )

            active_ver = db.query(WorldEntityVersion).filter(
                WorldEntityVersion.entity_id == temp.id,
                WorldEntityVersion.valid_to.is_(None)
            ).first()

            if not active_ver or not active_ver.properties:
                continue

            properties = active_ver.properties
            conditions = properties.get("conditions", {})
            if not conditions:
                # If no conditions defined, trigger by default
                triggered_events.append({
                    "id": str(temp.id),
                    "slug": temp.slug,
                    "title": active_ver.name,
                    "properties": properties
                })
                continue

            # Evaluate trigger conditions
            met = True

            # 1. Standing checks (e.g. standing_below, standing_above)
            standing_below = conditions.get("standing_below")
            if standing_below:
                source = standing_below.get("source")
                target = standing_below.get("target")
                val = standing_below.get("value")
                rel = graph_repo.get_active_relationship(db, source, target, "standing")
                weight = rel.weight if rel else 50.0
                if weight >= val:
                    met = False

            standing_above = conditions.get("standing_above")
            if standing_above and met:
                source = standing_above.get("source")
                target = standing_above.get("target")
                val = standing_above.get("value")
                rel = graph_repo.get_active_relationship(db, source, target, "standing")
                weight = rel.weight if rel else 50.0
                if weight <= val:
                    met = False

            # 2. Temporal checks (e.g. time_after_hour)
            time_after_hour = conditions.get("time_after_hour")
            if time_after_hour is not None and met:
                if current_time.hour < time_after_hour:
                    met = False

            # 3. Quest completion checks (e.g. quest_completed)
            quest_completed = conditions.get("quest_completed")
            if quest_completed and met:
                progress = db.query(QuestProgress).filter(
                    QuestProgress.quest_id == quest_completed,
                    QuestProgress.status == "completed"
                ).first()
                if not progress:
                    met = False

            if met:
                triggered_events.append({
                    "id": str(temp.id),
                    "slug": temp.slug,
                    "title": active_ver.name,
                    "properties": properties
                })

        duration = time.time() - start_time

        # Telemetry updates
        TelemetryService.record_narrative_metric(
            db,
            action_type="narrative_scheduler_duration_seconds",
            npc_slug="system",
            model_used="evaluate_triggers",
            latency_ms=int(duration * 1000)
        )

        return triggered_events
