import json
import time
import uuid
import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.quest import Quest, QuestObjective, QuestProgress
from app.models.world_state import WorldStateFlag
from app.services.llm.factory import get_llm_provider
from app.services.telemetry_service import TelemetryService
from app.services.graph_cache import graph_cache

logger = logging.getLogger("gamemind.hint_engine")

MAX_HINT_LEVEL = 3
HINT_COOLDOWN_SECONDS = 300

class HintEngine:
    @staticmethod
    def get_progress_flag_key(player_id: str, quest_id: uuid.UUID) -> str:
        return f"hint:progress:{player_id}:{quest_id}"

    @classmethod
    def get_progression_state(cls, db: Session, player_id: str, quest_id: uuid.UUID) -> tuple[int, datetime | None]:
        """Retrieve hint progression level and last requested timestamp from world state flags."""
        flag_key = cls.get_progress_flag_key(player_id, quest_id)
        flag = db.query(WorldStateFlag).filter(WorldStateFlag.flag_key == flag_key).first()
        if not flag:
            return 0, None
        try:
            data = json.loads(flag.flag_value)
            current_level = int(data.get("current_level", 0))
            last_requested_str = data.get("last_requested_at")
            last_requested = datetime.fromisoformat(last_requested_str) if last_requested_str else None
            return current_level, last_requested
        except Exception as e:
            logger.error(f"Failed to parse hint progress flag: {e}")
            return 0, None

    @classmethod
    def save_progression_state(cls, db: Session, player_id: str, quest_id: uuid.UUID, level: int, requested_at: datetime) -> None:
        """Persist progression level and request timestamp into world state flags."""
        flag_key = cls.get_progress_flag_key(player_id, quest_id)
        flag_value = json.dumps({
            "current_level": level,
            "last_requested_at": requested_at.isoformat()
        })
        flag = db.query(WorldStateFlag).filter(WorldStateFlag.flag_key == flag_key).first()
        if not flag:
            flag = WorldStateFlag(
                flag_key=flag_key,
                flag_value=flag_value,
                is_active=True,
                priority=0
            )
            db.add(flag)
        else:
            flag.flag_value = flag_value
        db.commit()

    @classmethod
    def get_cached_hint(cls, quest_id: uuid.UUID, player_id: str, npc_slug: str) -> tuple[dict | None, bool]:
        """Query hint version-stamp cache."""
        meta_key = f"graph:cache:hints:{quest_id}:{player_id}:meta"
        content_key = f"graph:cache:hints:{quest_id}:{player_id}:content"
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
            logger.error(f"Error querying hint cache: {e}")
            return None, False

    @classmethod
    def set_cached_hint(cls, quest_id: uuid.UUID, player_id: str, npc_slug: str, hint_data: dict, ttl: int = 3600) -> None:
        """Set hint version-stamp cache."""
        meta_key = f"graph:cache:hints:{quest_id}:{player_id}:meta"
        content_key = f"graph:cache:hints:{quest_id}:{player_id}:content"
        try:
            redis_client = graph_cache.redis
            involved_keys = [f"graph:version:entity:{npc_slug}"]
            stored_stamps = graph_cache.get_stamps(involved_keys)

            meta_data = {
                "involved_keys": involved_keys,
                "stored_stamps": stored_stamps
            }

            redis_client.set(content_key, json.dumps(hint_data).encode("utf-8"), ex=ttl)
            redis_client.set(meta_key, json.dumps(meta_data).encode("utf-8"), ex=ttl)
        except Exception as e:
            logger.error(f"Error setting hint cache: {e}")

    @classmethod
    async def generate_hint(cls, db: Session, quest_id: uuid.UUID, player_id: str, hint_level: int) -> dict:
        """
        Orchestrate progressive hint generation.
        Enforces sequence limits, cooldown limits, version stamp cache, and deterministic rules.
        """
        start_time = time.time()
        now = datetime.now(timezone.utc)

        # 1. Input parameters validations
        quest = db.query(Quest).filter(Quest.id == quest_id).first()
        if not quest:
            raise ValueError(f"Quest with ID '{quest_id}' not found.")

        # Validate hint level bounds
        if hint_level < 1 or hint_level > MAX_HINT_LEVEL:
            raise ValueError(f"Invalid hint level {hint_level}. Must be between 1 and {MAX_HINT_LEVEL}.")

        # Retrieve current progression state
        current_level, last_requested = cls.get_progression_state(db, player_id, quest_id)

        is_progression = (hint_level == current_level + 1) or (current_level == MAX_HINT_LEVEL and hint_level == MAX_HINT_LEVEL)
        is_reread = (hint_level <= current_level)

        # 2. Enforce progression rules
        if not is_progression and not is_reread:
            # Record progression block metric
            TelemetryService.record_production_metric(
                db,
                name="progressive_hint_progression_blocks_total",
                value=1,
                npc_slug=quest.npc_slug,
                model_used="hint_engine"
            )
            raise ValueError(f"Progression violation: Cannot skip or regress levels. Current level is {current_level}, requested {hint_level}.")

        # 3. Enforce cooldown rule (only for actual progression steps)
        if is_progression and last_requested:
            # Make sure we compare timezone aware datetimes
            if last_requested.tzinfo is None:
                last_requested = last_requested.replace(tzinfo=timezone.utc)
            elapsed = (now - last_requested).total_seconds()
            if elapsed < HINT_COOLDOWN_SECONDS:
                # Record cooldown block metric
                TelemetryService.record_production_metric(
                    db,
                    name="progressive_hint_cooldown_blocks_total",
                    value=1,
                    npc_slug=quest.npc_slug,
                    model_used="hint_engine"
                )
                cooldown_left = int(HINT_COOLDOWN_SECONDS - elapsed)
                raise ValueError(f"Cooldown active: Please wait {cooldown_left} more seconds before requesting another hint.")

        # 4. Cache validation
        cached_hint, hit = cls.get_cached_hint(quest_id, player_id, quest.npc_slug)
        if hit and cached_hint.get("hint_level") == hint_level:
            # Record cache hit metric
            TelemetryService.record_production_metric(
                db,
                name="progressive_hint_cache_hits_total",
                value=1,
                npc_slug=quest.npc_slug,
                model_used="hint_engine"
            )
            # Only update request time (cooldown reset) if it's a new progression request that hit cache
            if is_progression:
                cls.save_progression_state(db, player_id, quest_id, hint_level, now)
            cached_hint["cache_status"] = "hit"
            return cached_hint

        # Cache Miss
        TelemetryService.record_production_metric(
            db,
            name="progressive_hint_cache_misses_total",
            value=1,
            npc_slug=quest.npc_slug,
            model_used="hint_engine"
        )

        # 5. Fetch objectives context
        objectives = db.query(QuestObjective).filter(QuestObjective.quest_id == quest_id).order_by(QuestObjective.objective_index).all()
        # Find current active objective index based on player quest progress
        active_index = 0
        progress = db.query(QuestProgress).filter(
            QuestProgress.player_id == player_id,
            QuestProgress.quest_id == quest_id
        ).first()
        if progress and progress.objectives_state:
            # Find the first objective index that is not fully completed
            for obj in objectives:
                idx_str = str(obj.objective_index)
                current_qty = progress.objectives_state.get(idx_str, 0)
                if current_qty < obj.quantity_required:
                    active_index = obj.objective_index
                    break

        active_obj = next((o for o in objectives if o.objective_index == active_index), None)
        if not active_obj and objectives:
            active_obj = objectives[0]

        target_type = active_obj.target_type if active_obj else "explore"
        target_id = active_obj.target_id if active_obj else "unknown"
        target_desc = active_obj.description if active_obj else "explore the world"

        # Map spoiler levels
        spoiler_level = "low" if hint_level == 1 else "medium" if hint_level == 2 else "high"

        # Escalation rules
        hint_text = ""
        if hint_level == 1:
            # Deterministic, subtle hint
            if target_type == "kill":
                hint_text = "A threat lurks in the wilderness. Follow the trail and prepare for battle."
            elif target_type == "retrieve":
                hint_text = "An object of interest is hidden in the area. Search thoroughly for anything out of place."
            elif target_type == "speak":
                hint_text = "A key individual holds the information you need. Seek out and converse with them."
            else:
                hint_text = "Focus on your journal and explore the surrounding region."
        elif hint_level == 2:
            # Deterministic contextual hint
            target_name = target_id.replace("_", " ").title()
            # Try to grab location context from quest description if available
            location = "the marked area"
            if quest.description and " at " in quest.description:
                parts = quest.description.split(" at ")
                if len(parts) > 1:
                    location = parts[1].split(".")[0].strip()

            if target_type == "kill":
                hint_text = f"Your target is the {target_name}. Look for signs of conflict near {location}."
            elif target_type == "retrieve":
                hint_text = f"You need to acquire the {target_name}. Search containers or shelves in {location}."
            elif target_type == "speak":
                hint_text = f"Seek out and talk to the {target_name} to progress."
            else:
                hint_text = f"Focus on locating {target_name} in {location}."
        else:
            # Level 3: Invoke the LLM
            llm = get_llm_provider()
            system_prompt = (
                "You are an expert game master helping a player with a quest hint.\n"
                f"Quest Title: {quest.title}\n"
                f"Quest Description: {quest.description}\n"
                f"Active Objective Description: {target_desc}\n"
                f"Objective Target ID: {target_id}\n"
                f"Objective Type: {target_type}\n\n"
                "Give a direct, clear, and extremely helpful instruction (High Spoiler Level) "
                "telling the player exactly where to go, who or what to look for, and what action to perform. "
                "Do not be vague. Speak in a helpful narrative guide tone."
            )
            user_prompt = f"I am stuck on this quest. Tell me exactly what to do for the objective: '{target_desc}'."
            # Run the async LLM call
            response_text, _ = await llm.generate_response(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_output_tokens=200,
                model_name="gemini-1.5-flash"
            )
            # Clean brackets that mock provider might return
            hint_text = response_text
            if hint_text.startswith("["):
                # If mock provider returns bracket headers, clean them up or extract message
                lines = hint_text.split("\n")
                cleaned_lines = [l for l in lines if not l.startswith("[") and not l.startswith("Based on") and not l.startswith("-") and not l.startswith("You asked")]
                hint_text = " ".join(cleaned_lines).strip()
                if not hint_text:
                    hint_text = f"Directly focus on completing: {target_desc} by targeting {target_id}."

        # Compile final hint response payload
        hint_payload = {
            "hint_level": hint_level,
            "hint": hint_text,
            "spoiler_level": spoiler_level,
            "cache_status": "miss"
        }

        # 6. Save progression state to world state flags (only if it was a progression request)
        if is_progression:
            cls.save_progression_state(db, player_id, quest_id, hint_level, now)

        # 7. Write to stamps version cache
        cls.set_cached_hint(quest_id, player_id, quest.npc_slug, hint_payload)

        # 8. Record Telemetry Metrics
        duration_ms = int((time.time() - start_time) * 1000)
        TelemetryService.record_production_metric(
            db,
            name="progressive_hints_generated_total",
            value=1,
            npc_slug=quest.npc_slug,
            model_used="hint_engine"
        )
        TelemetryService.record_production_metric(
            db,
            name=f"progressive_hint_level_{hint_level}_total",
            value=1,
            npc_slug=quest.npc_slug,
            model_used="hint_engine"
        )
        TelemetryService.record_production_metric(
            db,
            name="progressive_hint_generation_duration_seconds",
            value=duration_ms,  # value records raw token/counter, latency_ms records milliseconds duration
            npc_slug=quest.npc_slug,
            model_used="hint_engine",
            latency_ms=duration_ms
        )

        return hint_payload
