import uuid
import time
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from app.models.npc import NPCProfile
from app.models.quest import GeneratedQuest
from app.services.graph_cache import graph_cache
from app.services.telemetry_service import TelemetryService
from app.services.quest_template_engine import QuestTemplateEngine
from app.services.quest_validation_engine import QuestValidationEngine
from app.services.quest_narrative_composer import QuestNarrativeComposer
from app.services.narrative_forecasting import NarrativeForecaster
from app.models.world_state import WorldStateFlag

logger = logging.getLogger("gamemind.dynamic_quest_generator")

class DynamicQuestGenerator:
    @classmethod
    def get_cached_quest(
        cls,
        npc_slug: str,
        player_id: str
    ) -> Tuple[Optional[Dict[str, Any]], bool]:
        """
        Retrieves a cached generated quest using O(1) version stamp validation.
        Key format: graph:cache:generated_quests:<npc_slug>:<player_id>
        """
        meta_key = f"graph:cache:generated_quests:{npc_slug}:{player_id}:meta"
        content_key = f"graph:cache:generated_quests:{npc_slug}:{player_id}:content"

        try:
            redis_client = graph_cache.redis
            meta_raw = redis_client.get(meta_key)
            if not meta_raw:
                return None, False

            meta = json.loads(meta_raw.decode("utf-8"))
            involved_keys = meta.get("involved_keys", [])
            stored_stamps = meta.get("stored_stamps", [])

            # Fetch current stamps
            current_stamps = graph_cache.get_stamps(involved_keys)
            for stored, current in zip(stored_stamps, current_stamps):
                if stored != current:
                    return None, False

            content_raw = redis_client.get(content_key)
            if not content_raw:
                return None, False

            return json.loads(content_raw.decode("utf-8")), True

        except Exception as e:
            logger.error(f"Error checking generated quest cache: {e}")
            return None, False

    @classmethod
    def set_cached_quest(
        cls,
        npc_slug: str,
        player_id: str,
        quest_data: Dict[str, Any],
        ttl: int = 3600
    ) -> None:
        """Caches the generated quest with version stamps."""
        meta_key = f"graph:cache:generated_quests:{npc_slug}:{player_id}:meta"
        content_key = f"graph:cache:generated_quests:{npc_slug}:{player_id}:content"

        try:
            redis_client = graph_cache.redis
            involved_keys = [
                f"graph:version:entity:{npc_slug}"
            ]
            stored_stamps = graph_cache.get_stamps(involved_keys)

            meta_data = {
                "involved_keys": involved_keys,
                "stored_stamps": stored_stamps
            }

            redis_client.set(content_key, json.dumps(quest_data).encode("utf-8"), ex=ttl)
            redis_client.set(meta_key, json.dumps(meta_data).encode("utf-8"), ex=ttl)
        except Exception as e:
            logger.error(f"Error setting generated quest cache: {e}")

    @classmethod
    def generate_quest(
        cls,
        db: Session,
        npc_slug: str,
        player_id: str = "default_player",
        player_level: int = 1
    ) -> Dict[str, Any]:
        """
        Orchestrates the dynamic quest generation pipeline.
        """
        start_time = time.time()

        # Enforce validation bounds
        if player_level < 1 or player_level > 100:
            raise ValueError(f"Player level must be between 1 and 100. Got {player_level}.")

        # Check NPC exists
        npc = db.query(NPCProfile).filter(NPCProfile.slug == npc_slug, NPCProfile.deleted_at.is_(None)).first()
        if not npc:
            raise ValueError(f"NPC Profile with slug '{npc_slug}' not found.")

        # 1. Check generated quest cache
        cached_quest, hit = cls.get_cached_quest(npc_slug, player_id)
        if hit:
            # Increment Cache Hits
            TelemetryService.record_narrative_metric(
                db,
                action_type="quest_generation_cache_hits_total",
                npc_slug=npc_slug,
                model_used="dynamic_quest_generator"
            )
            return cached_quest

        # Cache Miss
        TelemetryService.record_narrative_metric(
            db,
            action_type="quest_generation_cache_misses_total",
            npc_slug=npc_slug,
            model_used="dynamic_quest_generator"
        )

        # 2. Extract environmental context (world state, standing, forecast trends)
        target_name = "Void Slime"
        location = "Shadow Forest"
        target_id = "void_slime"
        quantity = 3

        # Consume forecast trends
        try:
            trends = NarrativeForecaster.forecast_trends(db, steps=3)
            if trends:
                # Use a target or location from trends if available
                trend = trends[0]
                affected = trend.get("affected_entities", [])
                if len(affected) > 0:
                    target_id = affected[0]
                    target_name = target_id.replace("_", " ").title()
                if len(affected) > 1:
                    location = affected[1].replace("_", " ").title()
        except Exception as e:
            logger.warning(f"Failed to fetch forecasting trends for quest generator: {e}")

        # Consume active world state event flags
        try:
            active_flags = db.query(WorldStateFlag).filter(WorldStateFlag.is_active == True).all()
            for flag in active_flags:
                if "threat" in flag.flag_key.lower():
                    # Elevate target quantity and difficulty based on threat flags
                    quantity = 5
        except Exception as e:
            logger.warning(f"Failed to query active world state flags: {e}")

        # 3. Template Selection
        # Choose a template based on world state target type (default to "kill")
        target_type = "kill"
        template = QuestTemplateEngine.select_template(target_type)

        # 4. Reward scaling
        rewards, is_adjusted = QuestTemplateEngine.scale_rewards(
            player_level=player_level,
            difficulty=template["difficulty"],
            reward_scaling=template["reward_scaling"]
        )

        if is_adjusted:
            TelemetryService.record_narrative_metric(
                db,
                action_type="quest_reward_balance_adjustments_total",
                npc_slug=npc_slug,
                model_used="dynamic_quest_generator"
            )

        # 5. Compose narrative
        narrative = QuestNarrativeComposer.compose_narrative(
            db=db,
            npc_profile=npc,
            template=template,
            player_id=player_id,
            target_name=target_name,
            location=location,
            quantity=quantity
        )

        # 6. Build final quest payload
        # Map template's objectives to concrete placeholders
        objectives = []
        for obj in template["objectives"]:
            desc = obj["description"].format(
                quantity=quantity,
                target_name=target_name,
                location=location
            )
            t_id = obj["target_id"].format(target_id=target_id)
            q_req = quantity if "{quantity}" in obj["quantity_required"] else 1
            objectives.append({
                "objective_index": obj["objective_index"],
                "description": desc,
                "target_type": obj["target_type"],
                "target_id": t_id,
                "quantity_required": q_req
            })

        quest_payload = {
            "npc_slug": npc_slug,
            "title": narrative["title"],
            "description": narrative["description"],
            "difficulty": template["difficulty"],
            "objectives": objectives,
            "rewards": rewards,
            "branches": narrative["branches"],
            "consequences": narrative["consequences"]
        }

        # 7. Validate
        valid, reasons = QuestValidationEngine.validate_quest(db, quest_payload)
        if not valid:
            raise ValueError(f"Quest validation failed: {'; '.join(reasons)}")

        # 8. Persist in Database
        db_quest = GeneratedQuest(
            id=uuid.uuid4(),
            npc_slug=npc_slug,
            title=quest_payload["title"],
            objectives=quest_payload["objectives"],
            rewards=quest_payload["rewards"],
            difficulty=quest_payload["difficulty"]
        )
        db.add(db_quest)
        db.commit()
        db.refresh(db_quest)

        # 9. Invalidate Cache - Increment Entity Stamp to signal change
        graph_cache.increment_entity_stamp(npc_slug)

        # 10. Cache generated quest
        cls.set_cached_quest(npc_slug, player_id, quest_payload)

        # 11. Record latency and metrics
        duration = time.time() - start_time
        TelemetryService.record_narrative_metric(
            db,
            action_type="dynamic_quests_generated_total",
            npc_slug=npc_slug,
            model_used="dynamic_quest_generator"
        )
        TelemetryService.record_narrative_metric(
            db,
            action_type="dynamic_quest_generation_duration_seconds",
            npc_slug=npc_slug,
            model_used="dynamic_quest_generator",
            latency_ms=int(duration * 1000)
        )
        TelemetryService.record_narrative_metric(
            db,
            action_type="quest_templates_selected_total",
            npc_slug=npc_slug,
            model_used=template["template_slug"]
        )

        return quest_payload
