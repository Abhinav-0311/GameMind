import json
import hashlib
import logging
from typing import Dict, Any, List, Tuple, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models.quest import GeneratedQuest
from app.models.graph import WorldEntity, WorldRelationship
from app.repositories.graph_repository import graph_repo
from app.services.narrative_consistency import NarrativeConsistencyService
from app.services.contradiction_engine import contradiction_engine
from app.services.graph_cache import graph_cache
from app.services.telemetry_service import TelemetryService

logger = logging.getLogger("gamemind.quest_validation_engine")

MAX_OBJECTIVES_PER_QUEST = 10
MAX_REWARDS_PER_QUEST = 5
MAX_BRANCHES_PER_QUEST = 5
MAX_CONSEQUENCES_PER_QUEST = 10
MAX_DUPLICATE_SCAN = 100
MAX_DEPENDENCY_DEPTH = 5

class QuestValidationEngine:
    @staticmethod
    def _compute_quest_hash(quest_data: Dict[str, Any]) -> str:
        """Compute MD5 hash of quest objectives and rewards for caching."""
        serialized = json.dumps({
            "title": quest_data.get("title", ""),
            "objectives": quest_data.get("objectives", []),
            "rewards": quest_data.get("rewards", {}),
            "game_project_id": quest_data.get("game_project_id", "default_project")
        }, sort_keys=True)
        return hashlib.md5(serialized.encode("utf-8")).hexdigest()

    @classmethod
    def get_cached_validation(
        cls,
        quest_data: Dict[str, Any],
        involved_entities: List[str]
    ) -> Tuple[Optional[Dict[str, Any]], bool]:
        """
        Check validation cache using O(1) version-stamp lookup.
        Key format: graph:cache:quest_validation:<quest_hash>
        """
        quest_hash = cls._compute_quest_hash(quest_data)
        meta_key = f"graph:cache:quest_validation:{quest_hash}:meta"
        content_key = f"graph:cache:quest_validation:{quest_hash}:content"

        try:
            redis_client = graph_cache.redis
            meta_raw = redis_client.get(meta_key)
            if not meta_raw:
                return None, False

            meta = json.loads(meta_raw.decode("utf-8"))
            stored_stamps = meta.get("stored_stamps", [])
            involved_keys = meta.get("involved_keys", [])

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
            logger.error(f"Error checking validation cache: {e}")
            return None, False

    @classmethod
    def set_cached_validation(
        cls,
        quest_data: Dict[str, Any],
        involved_entities: List[str],
        result: Dict[str, Any],
        ttl: int = 3600
    ) -> None:
        """Cache validation result with O(1) version stamps."""
        quest_hash = cls._compute_quest_hash(quest_data)
        meta_key = f"graph:cache:quest_validation:{quest_hash}:meta"
        content_key = f"graph:cache:quest_validation:{quest_hash}:content"

        try:
            redis_client = graph_cache.redis
            involved_keys = [f"graph:version:entity:{slug}" for slug in involved_entities]
            stored_stamps = graph_cache.get_stamps(involved_keys)

            meta_data = {
                "involved_keys": involved_keys,
                "stored_stamps": stored_stamps
            }

            redis_client.set(content_key, json.dumps(result).encode("utf-8"), ex=ttl)
            redis_client.set(meta_key, json.dumps(meta_data).encode("utf-8"), ex=ttl)
        except Exception as e:
            logger.error(f"Error caching validation result: {e}")

    @classmethod
    def check_dependency_depth_and_cycles(cls, db: Session, quest_title_slug: str) -> Tuple[bool, Optional[str]]:
        """DFS traversal checking that quest prerequisite depth is <= 5 and no cycles exist."""
        visited = set()
        rec_stack = set()

        def dfs(slug: str, depth: int) -> Tuple[bool, Optional[str]]:
            if depth > MAX_DEPENDENCY_DEPTH:
                return False, f"Quest dependency depth exceeds limit of {MAX_DEPENDENCY_DEPTH} starting from '{quest_title_slug}'."
            if slug in rec_stack:
                return False, f"Quest dependency cycle detected involving '{slug}'."
            if slug in visited:
                return True, None

            visited.add(slug)
            rec_stack.add(slug)

            # Find prerequisites of 'slug' in WorldRelationship (Target is slug, Source is parent/prerequisite)
            tgt_ent = graph_repo.get_entity_by_slug(db, slug)
            if tgt_ent:
                rels = db.query(WorldRelationship).filter(
                    WorldRelationship.rel_type == "prerequisite",
                    WorldRelationship.target_id == tgt_ent.id,
                    WorldRelationship.valid_to.is_(None)
                ).all()
                for rel in rels:
                    src_ent = db.query(WorldEntity).filter(WorldEntity.id == rel.source_id).first()
                    if src_ent:
                        valid, reason = dfs(src_ent.slug, depth + 1)
                        if not valid:
                            return False, reason

            rec_stack.remove(slug)
            return True, None

        return dfs(quest_title_slug, 0)

    @classmethod
    def validate_quest(
        cls,
        db: Session,
        quest_data: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """
        Runs comprehensive quest validation logic.
        Returns:
            (valid: bool, reasons: List[str])
        """
        reasons = []

        # Gather involved entities for cache stamp tracking
        npc_slug = quest_data.get("npc_slug")
        involved_entities = []
        if npc_slug:
            involved_entities.append(npc_slug)

        # 1. Structural Limits
        objectives = quest_data.get("objectives", [])
        rewards = quest_data.get("rewards", {})
        branches = quest_data.get("branches", [])
        consequences = quest_data.get("consequences", [])

        if len(objectives) > MAX_OBJECTIVES_PER_QUEST:
            reasons.append(f"Objectives count {len(objectives)} exceeds max limit of {MAX_OBJECTIVES_PER_QUEST}.")
        if len(objectives) == 0:
            reasons.append("Objectives count must be at least 1.")

        # Rewards Count Check
        # Count gold, xp and items
        reward_count = 0
        if rewards.get("gold", 0) > 0:
            reward_count += 1
        if rewards.get("xp", 0) > 0:
            reward_count += 1
        reward_count += len(rewards.get("items", []))

        if reward_count > MAX_REWARDS_PER_QUEST:
            reasons.append(f"Rewards count {reward_count} exceeds max limit of {MAX_REWARDS_PER_QUEST}.")

        if len(branches) > MAX_BRANCHES_PER_QUEST:
            reasons.append(f"Branches count {len(branches)} exceeds max limit of {MAX_BRANCHES_PER_QUEST}.")

        if len(consequences) > MAX_CONSEQUENCES_PER_QUEST:
            reasons.append(f"Consequences count {len(consequences)} exceeds max limit of {MAX_CONSEQUENCES_PER_QUEST}.")

        # 2. Check cache
        # If cache hits, we can return precalculated validations.
        for obj in objectives:
            t_id = obj.get("target_id")
            if t_id and t_id not in involved_entities:
                involved_entities.append(t_id)

        cached_res, hit = cls.get_cached_validation(quest_data, involved_entities)
        if hit:
            # Increment Cache Hits
            TelemetryService.record_narrative_metric(
                db,
                action_type="quest_generation_cache_hits_total",
                npc_slug=npc_slug or "system",
                model_used="quest_validation_engine"
            )
            return cached_res["valid"], cached_res["reasons"]

        # Cache Miss
        TelemetryService.record_narrative_metric(
            db,
            action_type="quest_generation_cache_misses_total",
            npc_slug=npc_slug or "system",
            model_used="quest_validation_engine"
        )

        # 3. Duplicate Quest Check (Scan last 100 generated quests)
        title = quest_data.get("title", "")
        project_id = quest_data.get("game_project_id", "default_project")
        last_quests = db.query(GeneratedQuest).filter(
            GeneratedQuest.game_project_id == project_id
        ).order_by(desc(GeneratedQuest.created_at)).limit(MAX_DUPLICATE_SCAN).all()
        for q in last_quests:
            if q.title.strip().lower() == title.strip().lower():
                reasons.append(f"Duplicate quest found: a quest with title '{title}' was recently generated.")
                TelemetryService.record_narrative_metric(
                    db,
                    action_type="quest_duplicate_rejections_total",
                    npc_slug=npc_slug or "system",
                    model_used="quest_validation_engine",
                    error_str=f"Duplicate quest title: {title}"
                )
                break

        # 4. Quest Dependency & DAG Validation
        title_slug = title.lower().replace(" ", "_")
        dep_valid, dep_reason = cls.check_dependency_depth_and_cycles(db, title_slug)
        if not dep_valid:
            reasons.append(dep_reason)

        # 5. Narrative Consistency Check (via NarrativeConsistencyService)
        if npc_slug:
            for obj in objectives:
                claim = {
                    "subject": npc_slug,
                    "predicate": obj.get("target_type", ""),
                    "object": obj.get("target_id", "")
                }
                consistent, details = NarrativeConsistencyService.check_consistency(db, claim)
                if not consistent:
                    reasons.append(f"Narrative consistency check failed for objective target '{obj.get('target_id')}': {details}")

        # 6. Contradiction Check (via ContradictionEngineService)
        # Verify if proposed standing rewards or consequences conflict
        # E.g. check if target standing shifts conflict with faction alliances/wars.
        # If there are faction Standing changes, validate them.
        for cons in consequences:
            source = cons.get("source")
            target = cons.get("target")
            rel_type = cons.get("type")
            if source and target and rel_type:
                conflict, detail = contradiction_engine.check_contradiction(db, source, target, rel_type)
                if conflict:
                    reasons.append(f"Contradiction detected in consequence: {detail}")

        # 7. Faction and World State Validation
        # Verify that npc and targets are active and faction exists
        if npc_slug:
            npc_entity = graph_repo.get_entity_by_slug(db, npc_slug)
            if not npc_entity:
                reasons.append(f"Faction/World validation error: NPC '{npc_slug}' does not exist in world graph.")

        # Determine validation result
        valid = (len(reasons) == 0)

        # Record validation status and telemetry
        result = {
            "valid": valid,
            "reasons": reasons
        }

        if not valid:
            TelemetryService.record_narrative_metric(
                db,
                action_type="quest_validation_failures_total",
                npc_slug=npc_slug or "system",
                model_used="quest_validation_engine",
                error_str="; ".join(reasons)
            )

        # Store in cache
        cls.set_cached_validation(quest_data, involved_entities, result)

        return valid, reasons
