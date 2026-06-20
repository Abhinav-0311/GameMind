import logging
from typing import Set, Dict, Any, List
from sqlalchemy.orm import Session
from app.models.npc import NPCProfile
from app.models.quest import Quest, QuestObjective
from app.models.graph import WorldEntity, WorldRelationship
from app.services.telemetry_service import TelemetryService

logger = logging.getLogger("gamemind.cross_npc_validation")

class CrossNPCValidationService:
    @staticmethod
    def get_npc_known_slugs(db: Session, npc_slug: str) -> Set[str]:
        """
        Gathers all entity slugs known to an NPC up to depth <= 2.
        Knowledge sources:
          - direct active relationships
          - faction membership
          - quest involvement
        """
        known: Set[str] = {npc_slug}
        
        # Step 0: Get the NPC profile to check faction alignment
        npc_profile = db.query(NPCProfile).filter(
            NPCProfile.slug == npc_slug,
            NPCProfile.deleted_at.is_(None)
        ).first()
        
        # Get the WorldEntity for npc_slug if it exists
        npc_entity = db.query(WorldEntity).filter(WorldEntity.slug == npc_slug).first()
        npc_entity_id = npc_entity.id if npc_entity else None

        # ----------------------------------------------------
        # Depth 1: Direct links
        # ----------------------------------------------------
        depth_1_nodes: Set[str] = set()
        depth_1_entity_ids: Set[Any] = set()

        # 1. Faction Alignment (1 hop)
        faction_slug = None
        if npc_profile and npc_profile.faction_alignment:
            faction_slug = npc_profile.faction_alignment
            depth_1_nodes.add(faction_slug)

        # 2. Quests Giver/Involvement (1 hop)
        quests = db.query(Quest).filter(Quest.npc_slug == npc_slug).all()
        quest_ids = [q.id for q in quests]
        for q in quests:
            # We can use the quest title or its string ID as a known slug
            depth_1_nodes.add(str(q.id))
            depth_1_nodes.add(q.title.lower().replace(" ", "_"))

        # 3. Direct active relationships in graph (1 hop)
        if npc_entity_id:
            active_rels_1 = db.query(WorldRelationship).filter(
                WorldRelationship.valid_to.is_(None),
                (WorldRelationship.source_id == npc_entity_id) | (WorldRelationship.target_id == npc_entity_id)
            ).all()
            for rel in active_rels_1:
                # Add the other end to depth 1
                other_id = rel.target_id if rel.source_id == npc_entity_id else rel.source_id
                other_entity = db.query(WorldEntity).filter(WorldEntity.id == other_id).first()
                if other_entity:
                    depth_1_nodes.add(other_entity.slug)
                    depth_1_entity_ids.add(other_id)

        known.update(depth_1_nodes)

        # ----------------------------------------------------
        # Depth 2: Neighbors of Depth 1 nodes
        # ----------------------------------------------------
        depth_2_nodes: Set[str] = set()

        # 1. Faction membership propagation (NPCs and entities in the same faction)
        if faction_slug:
            # Other NPCs in the same faction
            aligned_npcs = db.query(NPCProfile).filter(
                NPCProfile.faction_alignment == faction_slug,
                NPCProfile.deleted_at.is_(None)
            ).all()
            for an in aligned_npcs:
                depth_2_nodes.add(an.slug)
            
            # Entities linked to faction slug in graph
            faction_entity = db.query(WorldEntity).filter(WorldEntity.slug == faction_slug).first()
            if faction_entity:
                faction_rels = db.query(WorldRelationship).filter(
                    WorldRelationship.valid_to.is_(None),
                    (WorldRelationship.source_id == faction_entity.id) | (WorldRelationship.target_id == faction_entity.id)
                ).all()
                for rel in faction_rels:
                    other_id = rel.target_id if rel.source_id == faction_entity.id else rel.source_id
                    other_entity = db.query(WorldEntity).filter(WorldEntity.id == other_id).first()
                    if other_entity:
                        depth_2_nodes.add(other_entity.slug)

        # 2. Quest objectives (Objectives targets of NPC's quests)
        if quest_ids:
            objectives = db.query(QuestObjective).filter(QuestObjective.quest_id.in_(quest_ids)).all()
            for obj in objectives:
                depth_2_nodes.add(obj.target_id)

        # 3. Active relationships from depth 1 entities (2 hops)
        if depth_1_entity_ids:
            active_rels_2 = db.query(WorldRelationship).filter(
                WorldRelationship.valid_to.is_(None),
                (WorldRelationship.source_id.in_(depth_1_entity_ids)) | (WorldRelationship.target_id.in_(depth_1_entity_ids))
            ).all()
            for rel in active_rels_2:
                # Add source/target slugs if they aren't already known
                src_ent = db.query(WorldEntity).filter(WorldEntity.id == rel.source_id).first()
                tgt_ent = db.query(WorldEntity).filter(WorldEntity.id == rel.target_id).first()
                if src_ent:
                    depth_2_nodes.add(src_ent.slug)
                if tgt_ent:
                    depth_2_nodes.add(tgt_ent.slug)

        known.update(depth_2_nodes)
        return known

    @classmethod
    def npc_knows(cls, db: Session, npc_slug: str, entity_slug: str) -> bool:
        """
        Returns True if npc_slug knows entity_slug (depth <= 2).
        """
        known = cls.get_npc_known_slugs(db, npc_slug)
        is_known = entity_slug in known
        if not is_known:
            # Record validation failure in telemetry
            TelemetryService.record_narrative_metric(
                db,
                action_type="cross_npc_validation_failures_total",
                npc_slug=npc_slug,
                model_used="npc_knows",
                error_str=f"NPC '{npc_slug}' does not know entity '{entity_slug}'."
            )
        return is_known

    @classmethod
    def npc_knows_relationship(cls, db: Session, npc_slug: str, source_slug: str, target_slug: str, rel_type: str) -> bool:
        """
        Returns True if npc_slug knows both entities and the relationship is active.
        """
        # 1. Must know both source and target
        if not cls.npc_knows(db, npc_slug, source_slug) or not cls.npc_knows(db, npc_slug, target_slug):
            # Telemetry is already logged by npc_knows
            return False

        # 2. Relationship must exist and be active
        source_ent = db.query(WorldEntity).filter(WorldEntity.slug == source_slug).first()
        target_ent = db.query(WorldEntity).filter(WorldEntity.slug == target_slug).first()
        if not source_ent or not target_ent:
            return False

        active_rel = db.query(WorldRelationship).filter(
            WorldRelationship.source_id == source_ent.id,
            WorldRelationship.target_id == target_ent.id,
            WorldRelationship.rel_type == rel_type,
            WorldRelationship.valid_to.is_(None)
        ).first()

        if not active_rel:
            # Record failure in telemetry
            TelemetryService.record_narrative_metric(
                db,
                action_type="cross_npc_validation_failures_total",
                npc_slug=npc_slug,
                model_used="npc_knows_relationship",
                error_str=f"Relationship '{rel_type}' between '{source_slug}' and '{target_slug}' does not exist or is inactive."
            )
            return False

        return True
