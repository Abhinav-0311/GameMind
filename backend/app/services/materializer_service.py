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
        """Accept only an explicit runtime state binding, never infer one from prose."""
        if not isinstance(element, dict):
            return None
        key = self._slugify_runtime_id(self._clean_runtime_text(element.get("flag_key")))
        value = self._clean_runtime_text(element.get("flag_value"))
        return (key, value) if key and value else None

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

            archetype = self._clean_runtime_text(npc.get("archetype"))
            if not archetype:
                warn_msg = f"Skipped NPC '{name}' because its approved archetype is missing."
                report["warnings"].append(warn_msg)
                manifest_warnings.append(warn_msg)
                report["npcs"]["skipped"].append(name)
                continue
            dialogue_style = self._clean_runtime_text(npc.get("dialogue_style")) or None
            
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

        # 4. Materialize Quests only when the approved blueprint carries a complete,
        # explicit engine binding. The GDD-facing objective text alone must never be
        # converted into a guessed giver, target type, target id, reward, or difficulty.
        quest_data = blueprint.quest_hooks.get("content", {}).get("quests", [])
        for q in quest_data:
            title = self._clean_runtime_text(q.get("title"))
            runtime = q.get("runtime") if isinstance(q.get("runtime"), dict) else None
            if not title or not runtime:
                warn_msg = f"Quest '{title or 'Unnamed Quest'}' was preserved as approved design only because it has no explicit runtime binding."
                report["warnings"].append(warn_msg)
                manifest_warnings.append(warn_msg)
                report["quests"]["skipped"].append(title or "Unnamed Quest")
                continue
            npc_slug = self._slugify_runtime_id(self._clean_runtime_text(runtime.get("npc_slug")))
            difficulty = self._clean_runtime_text(runtime.get("difficulty"))
            objectives = runtime.get("objectives")
            if (
                not npc_slug
                or not difficulty
                or not isinstance(runtime.get("gold_reward"), int)
                or not isinstance(runtime.get("xp_reward"), int)
                or not isinstance(objectives, list)
                or not objectives
                or any(
                    not isinstance(item, dict)
                    or not self._clean_runtime_text(item.get("description"))
                    or not self._clean_runtime_text(item.get("target_type"))
                    or not self._clean_runtime_text(item.get("target_id"))
                    or not isinstance(item.get("quantity_required"), int)
                    or item["quantity_required"] < 1
                    for item in objectives
                )
            ):
                warn_msg = f"Quest '{title}' was skipped because its runtime binding is incomplete."
                report["warnings"].append(warn_msg)
                manifest_warnings.append(warn_msg)
                report["quests"]["skipped"].append(title)
                continue
            quest_giver = db.query(NPCProfile).filter(
                NPCProfile.slug == npc_slug,
                NPCProfile.game_project_id == game_project_id,
            ).first()
            if not quest_giver or npc_slug not in manifest["npcs"]:
                warn_msg = f"Quest '{title}' was skipped because its explicit quest giver '{npc_slug}' is not owned by this blueprint."
                report["warnings"].append(warn_msg)
                manifest_warnings.append(warn_msg)
                report["quests"]["skipped"].append(title)
                continue
            objective = self._clean_runtime_text(q.get("objective"))
            if not objective:
                warn_msg = f"Quest '{title}' was skipped because its approved objective is missing."
                report["warnings"].append(warn_msg)
                manifest_warnings.append(warn_msg)
                report["quests"]["skipped"].append(title)
                continue
            
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
                    existing_quest.npc_slug = npc_slug
                    existing_quest.difficulty = difficulty
                    existing_quest.gold_reward = runtime["gold_reward"]
                    existing_quest.xp_reward = runtime["xp_reward"]
                    
                    # Delete and rewrite objectives since we own the quest
                    db.query(QuestObjective).filter(QuestObjective.quest_id == existing_quest.id).delete()
                    for index, item in enumerate(objectives):
                        db.add(QuestObjective(
                            id=uuid.uuid4(),
                            quest_id=existing_quest.id,
                            objective_index=index,
                            description=self._clean_runtime_text(item["description"]),
                            target_type=self._clean_runtime_text(item["target_type"]),
                            target_id=self._clean_runtime_text(item["target_id"]),
                            quantity_required=item["quantity_required"],
                        ))
                    report["quests"]["updated"].append(title)
            else:
                # Create Quest
                new_q_id = uuid.uuid4()
                new_quest = Quest(
                    id=new_q_id,
                    title=title,
                    description=objective,
                    npc_slug=npc_slug,
                    difficulty=difficulty,
                    gold_reward=runtime["gold_reward"],
                    xp_reward=runtime["xp_reward"],
                    game_project_id=game_project_id
                )
                db.add(new_quest)
                
                for index, item in enumerate(objectives):
                    db.add(QuestObjective(
                        id=uuid.uuid4(),
                        quest_id=new_q_id,
                        objective_index=index,
                        description=self._clean_runtime_text(item["description"]),
                        target_type=self._clean_runtime_text(item["target_type"]),
                        target_id=self._clean_runtime_text(item["target_id"]),
                        quantity_required=item["quantity_required"],
                    ))
                
                manifest["quest_ids"].append(str(new_q_id))
                report["quests"]["created"].append(title)

        # 5. Materialize NPC Memories
        memory_data = blueprint.npc_memory_design.get("content", {}).get("memory_nodes", [])
        
        for mem in memory_data:
            subject = self._clean_runtime_text(mem.get("subject"))
            npc_slug = self._slugify_runtime_id(self._clean_runtime_text(mem.get("npc_slug")))
            memory_type = self._clean_runtime_text(mem.get("memory_type"))
            importance = mem.get("importance")
            if (
                not subject
                or not npc_slug
                or npc_slug not in manifest["npcs"]
                or not memory_type
                or not isinstance(importance, (int, float))
            ):
                warn_msg = f"Memory '{subject or 'Unknown Memory'}' was skipped because it lacks an explicit runtime binding."
                report["warnings"].append(warn_msg)
                manifest_warnings.append(warn_msg)
                report["memories"]["skipped"].append(subject or "Unknown Memory")
                continue
            target_npc = db.query(NPCProfile).filter(
                NPCProfile.slug == npc_slug,
                NPCProfile.game_project_id == game_project_id,
            ).first()
            if not target_npc:
                warn_msg = f"Memory '{subject}' was skipped because NPC '{npc_slug}' is unavailable."
                report["warnings"].append(warn_msg)
                manifest_warnings.append(warn_msg)
                report["memories"]["skipped"].append(subject)
                continue
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
                # Create memory with an explicit subject/owner; storage defaults are non-design metadata.
                new_mem_id = uuid.uuid4()
                new_mem = NPCMemory(
                    id=new_mem_id,
                    npc_id=target_npc.id,
                    memory_text=subject,
                    memory_type=memory_type,
                    importance_score=importance,
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
        if blueprint.status != "approved":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only an approved blueprint can provide a runtime bundle.",
            )

        manifest = blueprint.materialization_manifest
        if not isinstance(manifest, dict) or not manifest.get("last_materialized_at"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Blueprint must be materialized before it can provide a runtime bundle.",
            )
        if not any(manifest.get(key) for key in ("npcs", "quest_ids", "memory_ids", "flag_keys")):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Materialization completed but did not produce runtime records. "
                    "Review skipped items and add explicit runtime bindings before runtime use."
                ),
            )

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

        return {
            "api_version": "1.1",
            "blueprint_id": blueprint.id,
            "game_project_id": game_project_id,
            "npcs": npcs,
            "quests": quests,
            "memories": memories,
            "world_flags": world_flags,
            "approved_design": self._approved_design_artifacts(blueprint, quests),
        }

    def _approved_design_artifacts(
        self,
        blueprint: GameBlueprint,
        runtime_quests: list[Quest],
    ) -> dict[str, Any]:
        """Expose reviewed GDD artifacts without fabricating engine-specific data."""
        quest_ids_by_title = {quest.title: quest.id for quest in runtime_quests}
        npcs = []
        for npc in blueprint.npc_archetypes.get("content", {}).get("npcs", []):
            name = self._normalize_npc_name(npc.get("name", ""))
            slug = self._slugify_runtime_id(name)
            archetype = self._clean_runtime_text(npc.get("archetype"))
            if not name or not slug or not archetype:
                continue
            npcs.append({
                "slug": slug,
                "name": name,
                "archetype": archetype,
                "dialogue_style": self._clean_runtime_text(npc.get("dialogue_style"), ""),
                "dialogue_hooks": [
                    self._clean_runtime_text(hook, "")
                    for hook in npc.get("dialogue_hooks", [])
                    if self._clean_runtime_text(hook, "")
                ],
            })
        quests = []
        for quest in blueprint.quest_hooks.get("content", {}).get("quests", []):
            title = self._clean_runtime_text(quest.get("title"), "")
            objective = self._clean_runtime_text(quest.get("objective"), "")
            if not title or not objective:
                continue
            quests.append({
                "design_id": self._clean_runtime_text(quest.get("id"), "") or None,
                "runtime_quest_id": quest_ids_by_title.get(title),
                "title": title,
                "objective": objective,
                "objectives": [self._clean_runtime_text(item, "") for item in quest.get("objectives", []) if self._clean_runtime_text(item, "")],
                "failure_states": [self._clean_runtime_text(item, "") for item in quest.get("failure_states", []) if self._clean_runtime_text(item, "")],
                "dependencies": [self._clean_runtime_text(item, "") for item in quest.get("dependencies", []) if self._clean_runtime_text(item, "")],
                "dialogue_hooks": [self._clean_runtime_text(item, "") for item in quest.get("dialogue_hooks", []) if self._clean_runtime_text(item, "")],
            })
        return {"contract_version": "1.0", "npcs": npcs, "quests": quests}
