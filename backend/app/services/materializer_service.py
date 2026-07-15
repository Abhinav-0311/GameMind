import logging
import re
import uuid
from uuid import UUID
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.blueprint import GameBlueprint
from app.models.npc import NPCProfile
from app.models.quest import Quest, QuestObjective
from app.models.memory import NPCMemory
from app.models.world_state import WorldStateFlag
from app.models.graph import WorldEntity, WorldEntityVersion
from app.services.graph_cache import graph_cache

logger = logging.getLogger(__name__)

class BlueprintMaterializerService:
    INVALID_NPC_NAME_PREFIXES = (
        "the story",
        "story ",
        "section ",
        "project ",
        "version ",
        "quest ",
        "objective ",
        "players ",
        "visual ",
        "level ",
        "game ",
        "faction ",
        "memory ",
        "narrative ",
        "art style",
        "unity ",
    )

    def _clean_runtime_text(self, value: Any, fallback: str = "") -> str:
        if not isinstance(value, str):
            return fallback
        value = value.strip()
        value = re.sub(r"\*\*(.*?)\*\*", r"\1", value)
        value = re.sub(r"^#+\s*", "", value)
        value = re.sub(r"^\s*[-*]\s*", "", value)
        return re.sub(r"\s+", " ", value).strip()

    def _normalize_npc_name(self, value: Any) -> Optional[str]:
        name = self._clean_runtime_text(value)
        name = re.sub(r"^NPC\s+", "", name, flags=re.IGNORECASE).strip()
        name = re.sub(r"[^A-Za-z0-9\s'-]", "", name)
        name = re.sub(r"\s+", " ", name).strip()

        lowered = name.lower()
        if not name or len(name) < 2 or len(name) > 60:
            return None
        if lowered.startswith(self.INVALID_NPC_NAME_PREFIXES):
            return None
        if len(name.split()) > 4:
            return None
        if not re.search(r"[A-Za-z]", name):
            return None
        return name

    def _slugify_runtime_id(self, value: str) -> str:
        slug = re.sub(r"[^a-z0-9_-]", "", value.lower().replace(" ", "-"))
        slug = re.sub(r"-{2,}", "-", slug).strip("-_")
        return slug[:100]

    def _derive_world_state_flag(self, element: Any) -> Optional[tuple[str, str]]:
        """Convert explicit stateful level elements into runtime flags.

        Level interaction data also contains neutral objects such as checkpoints and
        terminals. Those belong in level presentation, not mutable world state.
        """
        raw_value = self._clean_runtime_text(element)
        if not raw_value:
            return None

        lowered = raw_value.lower()
        state_map = (
            ("unlocked", "unlocked"),
            ("locked", "locked"),
            ("enabled", "enabled"),
            ("disabled", "disabled"),
            ("activated", "activated"),
            ("deactivated", "deactivated"),
            ("opened", "opened"),
            ("closed", "closed"),
            ("completed", "completed"),
        )
        for marker, value in state_map:
            if marker in lowered:
                key = self._slugify_runtime_id(re.sub(rf"(?:^|[-\\s]){marker}(?:$|[-\\s])", " ", raw_value, flags=re.IGNORECASE))
                return (key or self._slugify_runtime_id(raw_value), value)
        return None

    def _ensure_npc_graph_entity(
        self,
        db: Session,
        npc: NPCProfile,
        game_project_id: str,
    ) -> None:
        """Mirror a materialized NPC into the scoped narrative graph for quest validation."""
        entity = db.query(WorldEntity).filter(
            WorldEntity.slug == npc.slug,
            WorldEntity.game_project_id == game_project_id,
        ).first()
        if entity:
            return

        entity = WorldEntity(
            id=uuid.uuid4(),
            slug=npc.slug,
            entity_type="npc",
            game_project_id=game_project_id,
        )
        db.add(entity)
        db.flush()
        db.add(WorldEntityVersion(
            id=uuid.uuid4(),
            entity_id=entity.id,
            version=1,
            name=npc.name,
            description=npc.personality_summary,
            importance_score=5,
            properties={"npc_slug": npc.slug, "source": "blueprint_materialization"},
        ))
        graph_cache.increment_entity_stamp(npc.slug)

    def _resolve_fallback_runtime_records(
        self,
        db: Session,
        blueprint: GameBlueprint,
        game_project_id: str
    ) -> Dict[str, List[Any]]:
        """Resolve project-scoped records that match a materialized blueprint's source content.

        This is intentionally narrower than returning all project records. It exists for demo
        databases where records were created by an earlier blueprint run, causing a later
        materialization to skip duplicates and leave an empty manifest.
        """
        npc_slugs = []
        for npc in blueprint.npc_archetypes.get("content", {}).get("npcs", []):
            name = self._normalize_npc_name(npc.get("name", ""))
            if not name:
                continue
            slug = self._slugify_runtime_id(name)
            if slug:
                npc_slugs.append(slug)

        quest_titles = [
            self._clean_runtime_text(quest.get("title"), "Unnamed Quest")
            for quest in blueprint.quest_hooks.get("content", {}).get("quests", [])
        ]
        quest_titles = [title for title in quest_titles if title]

        memory_subjects = [
            self._clean_runtime_text(memory.get("subject"), "")
            for memory in blueprint.npc_memory_design.get("content", {}).get("memory_nodes", [])
        ]
        memory_subjects = [subject for subject in memory_subjects if subject]

        flag_keys = [
            state_flag[0]
            for element in blueprint.level_design_suggestions.get("content", {}).get("interactive_elements", [])
            if (state_flag := self._derive_world_state_flag(element))
        ]

        npcs = []
        if npc_slugs:
            npcs = db.query(NPCProfile).filter(
                NPCProfile.slug.in_(npc_slugs),
                NPCProfile.game_project_id == game_project_id
            ).all()

        quests = []
        if quest_titles:
            quests = db.query(Quest).filter(
                Quest.title.in_(quest_titles),
                Quest.game_project_id == game_project_id
            ).all()
            if quests:
                objectives = db.query(QuestObjective).filter(
                    QuestObjective.quest_id.in_([quest.id for quest in quests])
                ).order_by(QuestObjective.objective_index).all()
                objectives_by_quest = {}
                for objective in objectives:
                    objectives_by_quest.setdefault(objective.quest_id, []).append(objective)
                for quest in quests:
                    quest.objectives = objectives_by_quest.get(quest.id, [])

        memories = []
        if memory_subjects and npcs:
            memories = db.query(NPCMemory).filter(
                NPCMemory.npc_id.in_([npc.id for npc in npcs]),
                NPCMemory.memory_text.in_(memory_subjects),
                NPCMemory.game_project_id == game_project_id
            ).all()

        world_flags = []
        if flag_keys:
            world_flags = db.query(WorldStateFlag).filter(
                WorldStateFlag.flag_key.in_(flag_keys),
                WorldStateFlag.game_project_id == game_project_id
            ).all()

        return {
            "npcs": npcs,
            "quests": quests,
            "memories": memories,
            "world_flags": world_flags
        }

    def materialize_blueprint(self, db: Session, blueprint_id: UUID, game_project_id: str) -> Dict[str, Any]:
        # 1. Fetch blueprint scoped by project
        blueprint = db.query(GameBlueprint).filter(
            GameBlueprint.id == blueprint_id,
            GameBlueprint.game_project_id == game_project_id
        ).first()
        if not blueprint:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Blueprint not found or not owned by this project."
            )

        # Only approved blueprints can be materialized
        if blueprint.status != "approved":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only approved blueprints can be materialized into runtime records."
            )

        # 2. Initialize backward-compatible manifest
        manifest = blueprint.materialization_manifest
        if not manifest:
            manifest = {
                "npcs": [],
                "quest_ids": [],
                "memory_ids": [],
                "flag_keys": [],
                "last_materialized_at": None,
                "warnings": []
            }
        for key in ["npcs", "quest_ids", "memory_ids", "flag_keys", "warnings"]:
            manifest.setdefault(key, [])

        # Staged lists/report details
        report = {
            "status": "success",
            "npcs": {"created": [], "updated": [], "skipped": []},
            "quests": {"created": [], "updated": [], "skipped": []},
            "memories": {"created": [], "updated": [], "skipped": []},
            "flags": {"created": [], "updated": [], "skipped": []},
            "warnings": []
        }

        # Keep trace of warnings inside manifest too
        manifest_warnings = []

        # 3. Materialize NPCs
        npc_data = blueprint.npc_archetypes.get("content", {}).get("npcs", [])
        materialized_npc_slugs = [] # slugs we successfully write/own

        for npc in npc_data:
            raw_name = npc.get("name", "")
            name = self._normalize_npc_name(raw_name)
            if not name:
                warn_msg = f"Skipped malformed NPC entry '{self._clean_runtime_text(raw_name, 'unknown')[:80]}'."
                report["warnings"].append(warn_msg)
                manifest_warnings.append(warn_msg)
                report["npcs"]["skipped"].append(self._clean_runtime_text(raw_name, "unknown")[:80])
                continue

            archetype = self._clean_runtime_text(npc.get("archetype"), "Character profile")
            dialogue_style = self._clean_runtime_text(npc.get("dialogue_style"), "Normal speech.")
            
            # Generate stable slug
            slug = self._slugify_runtime_id(name)
            if not slug:
                slug = f"npc-{uuid.uuid4().hex[:6]}"

            # Check existence
            existing_npc = db.query(NPCProfile).filter(
                NPCProfile.slug == slug,
                NPCProfile.game_project_id == game_project_id
            ).first()

            if existing_npc:
                # Provenance verification
                if slug not in manifest["npcs"]:
                    warn_msg = f"NPC slug '{slug}' already exists in database and is not owned by this blueprint. Skipping."
                    report["warnings"].append(warn_msg)
                    manifest_warnings.append(warn_msg)
                    report["npcs"]["skipped"].append(slug)
                else:
                    # Safe update
                    existing_npc.name = name
                    existing_npc.personality_summary = archetype
                    existing_npc.dialogue_style = dialogue_style
                    report["npcs"]["updated"].append(slug)
                    materialized_npc_slugs.append(slug)
            else:
                # Create NPC
                new_npc = NPCProfile(
                    id=uuid.uuid4(),
                    slug=slug,
                    name=name,
                    personality_summary=archetype,
                    dialogue_style=dialogue_style,
                    game_project_id=game_project_id
                )
                db.add(new_npc)
                manifest["npcs"].append(slug)
                report["npcs"]["created"].append(slug)
                materialized_npc_slugs.append(slug)

        db.flush()

        # Dynamic quest validation resolves NPCs through the narrative graph, so every
        # NPC this blueprint owns must have a project-scoped graph entity as well.
        for npc_slug in materialized_npc_slugs:
            profile = db.query(NPCProfile).filter(
                NPCProfile.slug == npc_slug,
                NPCProfile.game_project_id == game_project_id,
            ).first()
            if profile:
                self._ensure_npc_graph_entity(db, profile, game_project_id)
        db.flush()

        # 4. Materialize Quests
        quest_data = blueprint.quest_hooks.get("content", {}).get("quests", [])
        # Determine a default quest giver NPC
        default_npc_slug = "narrator"
        if materialized_npc_slugs:
            default_npc_slug = materialized_npc_slugs[0]
        else:
            # check active project npcs
            any_npc = db.query(NPCProfile).filter(NPCProfile.game_project_id == game_project_id).first()
            if any_npc:
                default_npc_slug = any_npc.slug
            else:
                default_npc_slug = ""

        for q in quest_data:
            if not default_npc_slug:
                warn_msg = "Quest materialization skipped because no valid NPC quest giver exists."
                report["warnings"].append(warn_msg)
                manifest_warnings.append(warn_msg)
                for skipped_quest in quest_data:
                    report["quests"]["skipped"].append(self._clean_runtime_text(skipped_quest.get("title"), "Unnamed Quest"))
                break

            title = self._clean_runtime_text(q.get("title"), "Unnamed Quest")
            objective = self._clean_runtime_text(q.get("objective"), "Complete objective.")
            
            # Title match (service-level uniqueness check)
            existing_quest = db.query(Quest).filter(
                Quest.title == title,
                Quest.game_project_id == game_project_id
            ).first()

            if existing_quest:
                q_id_str = str(existing_quest.id)
                # Provenance verification
                if q_id_str not in manifest["quest_ids"]:
                    warn_msg = f"Quest with title '{title}' already exists and is not owned by this blueprint. Skipping."
                    report["warnings"].append(warn_msg)
                    manifest_warnings.append(warn_msg)
                    report["quests"]["skipped"].append(title)
                else:
                    # Update quest details
                    existing_quest.description = objective
                    existing_quest.npc_slug = default_npc_slug
                    
                    # Delete and rewrite objectives since we own the quest
                    db.query(QuestObjective).filter(QuestObjective.quest_id == existing_quest.id).delete()
                    new_obj = QuestObjective(
                        id=uuid.uuid4(),
                        quest_id=existing_quest.id,
                        objective_index=0,
                        description=objective,
                        target_type="speak" if "speak" in objective.lower() else "retrieve",
                        target_id=default_npc_slug,
                        quantity_required=1
                    )
                    db.add(new_obj)
                    report["quests"]["updated"].append(title)
            else:
                # Create Quest
                new_q_id = uuid.uuid4()
                new_quest = Quest(
                    id=new_q_id,
                    title=title,
                    description=objective,
                    npc_slug=default_npc_slug,
                    difficulty="Medium",
                    gold_reward=100,
                    xp_reward=200,
                    game_project_id=game_project_id
                )
                db.add(new_quest)
                
                # Add objective
                new_obj = QuestObjective(
                    id=uuid.uuid4(),
                    quest_id=new_q_id,
                    objective_index=0,
                    description=objective,
                    target_type="retrieve",
                    target_id="sky-iron" if "iron" in objective.lower() else "key",
                    quantity_required=1
                )
                db.add(new_obj)
                
                manifest["quest_ids"].append(str(new_q_id))
                report["quests"]["created"].append(title)

        # 5. Materialize NPC Memories
        memory_data = blueprint.npc_memory_design.get("content", {}).get("memory_nodes", [])
        
        # Link memory to the first NPC profile we created/own
        target_npc = None
        if materialized_npc_slugs:
            target_npc = db.query(NPCProfile).filter(
                NPCProfile.slug == materialized_npc_slugs[0],
                NPCProfile.game_project_id == game_project_id
            ).first()
        else:
            target_npc = db.query(NPCProfile).filter(NPCProfile.game_project_id == game_project_id).first()

        if not target_npc:
            warn_msg = "No active NPC Profile found in database. NPC memory materialization skipped."
            report["warnings"].append(warn_msg)
            manifest_warnings.append(warn_msg)
            for mem in memory_data:
                report["memories"]["skipped"].append(mem.get("subject", "Unknown Memory"))
        else:
            for mem in memory_data:
                subject = mem.get("subject", "Historical Event")
                importance = float(mem.get("importance", 5))

                # Check duplicate memory text for this NPC
                existing_mem = db.query(NPCMemory).filter(
                    NPCMemory.npc_id == target_npc.id,
                    NPCMemory.memory_text == subject,
                    NPCMemory.game_project_id == game_project_id
                ).first()

                if existing_mem:
                    mem_id_str = str(existing_mem.id)
                    # Provenance verification
                    if mem_id_str not in manifest["memory_ids"]:
                        warn_msg = f"Memory text for NPC '{target_npc.name}' already exists and is not owned by this blueprint. Skipping."
                        report["warnings"].append(warn_msg)
                        manifest_warnings.append(warn_msg)
                        report["memories"]["skipped"].append(subject)
                    else:
                        existing_mem.importance_score = importance
                        report["memories"]["updated"].append(subject)
                else:
                    # Create memory
                    new_mem_id = uuid.uuid4()
                    new_mem = NPCMemory(
                        id=new_mem_id,
                        npc_id=target_npc.id,
                        memory_text=subject,
                        memory_type="episodic",
                        importance_score=importance,
                        chroma_indexed=False,
                        archived=False,
                        game_project_id=game_project_id
                    )
                    db.add(new_mem)
                    manifest["memory_ids"].append(str(new_mem_id))
                    report["memories"]["created"].append(subject)

        # 6. Materialize World State Flags
        flag_data = blueprint.level_design_suggestions.get("content", {}).get("interactive_elements", [])
        desired_flags = {
            state_flag[0]: state_flag[1]
            for element in flag_data
            if (state_flag := self._derive_world_state_flag(element))
        }

        # Remove only stale flags that this blueprint previously owned. This keeps
        # re-materialization idempotent when source parsing becomes more precise.
        stale_flag_keys = set(manifest["flag_keys"]) - set(desired_flags)
        if stale_flag_keys:
            db.query(WorldStateFlag).filter(
                WorldStateFlag.flag_key.in_(stale_flag_keys),
                WorldStateFlag.game_project_id == game_project_id,
            ).delete(synchronize_session=False)
            manifest["flag_keys"] = [key for key in manifest["flag_keys"] if key not in stale_flag_keys]
            report["warnings"].append("Removed stale blueprint-owned world-state flags that are not explicit source states.")

        for flag_key, flag_val in desired_flags.items():

            existing_flag = db.query(WorldStateFlag).filter(
                WorldStateFlag.flag_key == flag_key,
                WorldStateFlag.game_project_id == game_project_id
            ).first()

            if existing_flag:
                # Provenance verification
                if flag_key not in manifest["flag_keys"]:
                    warn_msg = f"World state flag '{flag_key}' already exists in database and is not owned by this blueprint. Skipping."
                    report["warnings"].append(warn_msg)
                    manifest_warnings.append(warn_msg)
                    report["flags"]["skipped"].append(flag_key)
                else:
                    existing_flag.flag_value = flag_val
                    report["flags"]["updated"].append(flag_key)
            else:
                # Create flag
                new_flag = WorldStateFlag(
                    game_project_id=game_project_id,
                    flag_key=flag_key,
                    flag_value=flag_val,
                    is_active=True,
                    priority=1
                )
                db.add(new_flag)
                manifest["flag_keys"].append(flag_key)
                report["flags"]["created"].append(flag_key)

        # 7. Update manifest records
        manifest["last_materialized_at"] = datetime.utcnow().isoformat()
        manifest["warnings"] = manifest_warnings
        blueprint.materialization_manifest = manifest

        db.commit()
        db.refresh(blueprint)
        return report

    def get_runtime_bundle(self, db: Session, blueprint_id: UUID, game_project_id: str) -> Dict[str, Any]:
        # Fetch blueprint scoped by project
        blueprint = db.query(GameBlueprint).filter(
            GameBlueprint.id == blueprint_id,
            GameBlueprint.game_project_id == game_project_id
        ).first()
        if not blueprint:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Blueprint not found or not owned by this project."
            )

        manifest = blueprint.materialization_manifest
        if not manifest:
            # Return empty structure if not yet materialized
            return {
                "api_version": "1.0",
                "blueprint_id": blueprint.id,
                "game_project_id": game_project_id,
                "npcs": [],
                "quests": [],
                "memories": [],
                "world_flags": []
            }

        # Query only database records listed inside manifest to enforce strict provenance
        npcs = []
        if manifest.get("npcs"):
            npcs = db.query(NPCProfile).filter(
                NPCProfile.slug.in_(manifest["npcs"]),
                NPCProfile.game_project_id == game_project_id
            ).all()

        quests = []
        if manifest.get("quest_ids"):
            quest_uuids = []
            for q_id in manifest["quest_ids"]:
                try:
                    quest_uuids.append(UUID(q_id))
                except ValueError:
                    continue
            if quest_uuids:
                quests = db.query(Quest).filter(
                    Quest.id.in_(quest_uuids),
                    Quest.game_project_id == game_project_id
                ).all()
                objectives = db.query(QuestObjective).filter(
                    QuestObjective.quest_id.in_([quest.id for quest in quests])
                ).order_by(QuestObjective.objective_index).all()
                objectives_by_quest = {}
                for objective in objectives:
                    objectives_by_quest.setdefault(objective.quest_id, []).append(objective)
                for quest in quests:
                    quest.objectives = objectives_by_quest.get(quest.id, [])

        memories = []
        if manifest.get("memory_ids"):
            memory_uuids = []
            for m_id in manifest["memory_ids"]:
                try:
                    memory_uuids.append(UUID(m_id))
                except ValueError:
                    continue
            if memory_uuids:
                memories = db.query(NPCMemory).filter(
                    NPCMemory.id.in_(memory_uuids),
                    NPCMemory.game_project_id == game_project_id
                ).all()

        world_flags = []
        if manifest.get("flag_keys"):
            world_flags = db.query(WorldStateFlag).filter(
                WorldStateFlag.flag_key.in_(manifest["flag_keys"]),
                WorldStateFlag.game_project_id == game_project_id
            ).all()

        if (
            manifest.get("last_materialized_at")
            and not npcs
            and not quests
            and not memories
            and not world_flags
        ):
            fallback_records = self._resolve_fallback_runtime_records(db, blueprint, game_project_id)
            npcs = fallback_records["npcs"]
            quests = fallback_records["quests"]
            memories = fallback_records["memories"]
            world_flags = fallback_records["world_flags"]

        return {
            "api_version": "1.0",
            "blueprint_id": blueprint.id,
            "game_project_id": game_project_id,
            "npcs": npcs,
            "quests": quests,
            "memories": memories,
            "world_flags": world_flags
        }
