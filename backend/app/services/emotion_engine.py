import json
import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.relationship import NPCRelationship
from app.models.world_state import WorldStateFlag
from app.services.telemetry_service import TelemetryService

logger = logging.getLogger("gamemind.emotion_engine")

class EmotionEngine:
    @staticmethod
    def get_emotional_state(db: Session, npc_slug: str, player_id: str) -> Dict[str, int]:
        """
        Unified emotional state reader. Resolves trust/fear from relationships
        and anger/curiosity/loyalty from JSON flags in world_state_flags.
        """
        # Record read telemetry
        TelemetryService.record_narrative_metric(
            db,
            action_type="emotion_state_reads_total",
            npc_slug=npc_slug,
            model_used="emotion_engine"
        )

        # 1. Fetch trust & fear from npc_relationships
        rel = db.query(NPCRelationship).filter(
            NPCRelationship.npc_slug == npc_slug,
            NPCRelationship.player_id == player_id
        ).first()

        trust = rel.trust if rel else 50
        fear = rel.fear if rel else 0

        # 2. Fetch anger, curiosity, loyalty from world_state_flags
        flag_key = f"emotion:{npc_slug}:{player_id}"
        flag = db.query(WorldStateFlag).filter(
            WorldStateFlag.flag_key == flag_key
        ).first()

        anger = 0
        curiosity = 0
        loyalty = 0

        if flag and flag.flag_value:
            try:
                data = json.loads(flag.flag_value)
                anger = data.get("anger", 0)
                curiosity = data.get("curiosity", 0)
                loyalty = data.get("loyalty", 0)
            except Exception as e:
                logger.error(f"Failed to parse emotional state JSON for {flag_key}: {e}")

        return {
            "trust": trust,
            "fear": fear,
            "anger": anger,
            "curiosity": curiosity,
            "loyalty": loyalty
        }

    @staticmethod
    def update_emotional_state(
        db: Session,
        npc_slug: str,
        player_id: str,
        updates: Dict[str, int],
        reason: Optional[str] = None
    ) -> Dict[str, int]:
        """
        Unified emotional state updater.
        Validates value ranges (0-100), locks records alphabetically,
        and serializes anger/curiosity/loyalty to JSON.
        """
        # Validate update values: 0 <= value <= 100
        for key, val in updates.items():
            if not isinstance(val, int) or val < 0 or val > 100:
                raise ValueError(f"Value for emotion '{key}' must be an integer between 0 and 100. Got: {val}")

        # Enforce alphabetical lock ordering to prevent deadlocks:
        # We lock NPCRelationship first, then WorldStateFlag since
        # npc_relationships < world_state_flags alphabetically by table name.
        
        # 1. Lock/Fetch NPCRelationship
        rel = db.query(NPCRelationship).filter(
            NPCRelationship.npc_slug == npc_slug,
            NPCRelationship.player_id == player_id
        ).with_for_update().first()

        # 2. Lock/Fetch WorldStateFlag
        flag_key = f"emotion:{npc_slug}:{player_id}"
        flag = db.query(WorldStateFlag).filter(
            WorldStateFlag.flag_key == flag_key
        ).with_for_update().first()

        # Update trust / fear if present
        has_rel_updates = "trust" in updates or "fear" in updates
        if has_rel_updates:
            if not rel:
                rel = NPCRelationship(
                    npc_slug=npc_slug,
                    player_id=player_id,
                    trust=50,
                    fear=0
                )
                db.add(rel)
            if "trust" in updates:
                rel.trust = updates["trust"]
            if "fear" in updates:
                rel.fear = updates["fear"]
            if reason:
                rel.last_reason = reason

        # Update anger, curiosity, loyalty
        has_flag_updates = "anger" in updates or "curiosity" in updates or "loyalty" in updates
        
        current_anger = 0
        current_curiosity = 0
        current_loyalty = 0
        
        if flag and flag.flag_value:
            try:
                data = json.loads(flag.flag_value)
                current_anger = data.get("anger", 0)
                current_curiosity = data.get("curiosity", 0)
                current_loyalty = data.get("loyalty", 0)
            except Exception:
                pass

        new_anger = updates.get("anger", current_anger)
        new_curiosity = updates.get("curiosity", current_curiosity)
        new_loyalty = updates.get("loyalty", current_loyalty)

        if has_flag_updates or not flag:
            new_data = {
                "anger": new_anger,
                "curiosity": new_curiosity,
                "loyalty": new_loyalty
            }
            if not flag:
                flag = WorldStateFlag(
                    flag_key=flag_key,
                    flag_value=json.dumps(new_data),
                    is_active=True,
                    priority=0
                )
                db.add(flag)
            else:
                flag.flag_value = json.dumps(new_data)

        # Commit updates
        db.commit()

        # Record update telemetry
        TelemetryService.record_narrative_metric(
            db,
            action_type="emotional_state_updates_total",
            npc_slug=npc_slug,
            model_used="emotion_engine"
        )

        return {
            "trust": rel.trust if rel else 50,
            "fear": rel.fear if rel else 0,
            "anger": new_anger,
            "curiosity": new_curiosity,
            "loyalty": new_loyalty
        }
