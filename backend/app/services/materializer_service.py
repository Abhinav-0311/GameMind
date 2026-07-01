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

logger = logging.getLogger(__name__)

class BlueprintMaterializerService:
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
            name = npc.get("name", "Unnamed NPC")
            archetype = npc.get("archetype", "Default Archetype")
            dialogue_style = npc.get("dialogue_style", "Normal speech.")
            
            # Generate stable slug
            slug = re.sub(r"[^a-z0-9_-]", "", name.lower().replace(" ", "-"))
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

        for q in quest_data:
            title = q.get("title", "Unnamed Quest")
            objective = q.get("objective", "Complete objective.")
            
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
        layout_text = blueprint.level_design_suggestions.get("content", {}).get("level_layout", "")

        for element in flag_data:
            # Key cleanup
            flag_key = re.sub(r"[^a-z0-9_-]", "", element.lower().replace(" ", "-"))
            if not flag_key:
                continue

            existing_flag = db.query(WorldStateFlag).filter(
                WorldStateFlag.flag_key == flag_key,
                WorldStateFlag.game_project_id == game_project_id
            ).first()

            flag_val = "locked"
            if "unlock" in layout_text.lower():
                flag_val = "unlocked"

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
            "api_version": "1.0",
            "blueprint_id": blueprint.id,
            "game_project_id": game_project_id,
            "npcs": npcs,
            "quests": quests,
            "memories": memories,
            "world_flags": world_flags
        }
