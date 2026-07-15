import logging
import time
from typing import Dict, Any, List, Set
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.models.graph import WorldEntity, WorldRelationship
from app.repositories.graph_repository import graph_repo
from app.services.world_state_propagation import WorldStatePropagationService
from app.services.telemetry_service import TelemetryService

logger = logging.getLogger("gamemind.faction_dynamics")

class FactionDynamicsEngine:
    @staticmethod
    def _standing_lock_key(faction_a: str, faction_b: str) -> str:
        """Return one deterministic lock key for a faction pair."""
        return "faction-standing:" + ":".join(sorted((faction_a, faction_b)))

    @classmethod
    def _acquire_standing_lock(cls, db: Session, faction_a: str, faction_b: str) -> bool:
        """Serialize one standing change across its multi-commit legacy workflow."""
        if db.bind is None or db.bind.dialect.name != "postgresql":
            return False
        db.execute(text("SELECT pg_advisory_lock(hashtext(:lock_key))"), {
            "lock_key": cls._standing_lock_key(faction_a, faction_b),
        })
        return True

    @classmethod
    def _release_standing_lock(cls, db: Session, faction_a: str, faction_b: str) -> None:
        if db.bind is None or db.bind.dialect.name != "postgresql":
            return
        db.execute(text("SELECT pg_advisory_unlock(hashtext(:lock_key))"), {
            "lock_key": cls._standing_lock_key(faction_a, faction_b),
        })
        db.commit()

    @staticmethod
    def shift_standing(db: Session, faction_a: str, faction_b: str, delta: float) -> Dict[str, Any]:
        """
        Shifts the standing between Faction A and Faction B.
        Locks entities in alphabetical order to prevent concurrent deadlocks.
        """
        start_time = time.time()
        lock_acquired = FactionDynamicsEngine._acquire_standing_lock(db, faction_a, faction_b)
        try:
            # Alphabetical row ordering remains useful for related graph updates.
            graph_repo._lock_entities_ordered([faction_a, faction_b], db)

            active_rel = graph_repo.get_active_relationship(
                db, faction_a, faction_b, "standing", for_update=True
            )
            old_weight = active_rel.weight if active_rel else 50.0

            if not active_rel:
                active_rel = graph_repo.create_relationship(
                    db=db,
                    source_slug=faction_a,
                    target_slug=faction_b,
                    rel_type="standing",
                    weight=50.0
                )

            new_weight = max(0.0, min(100.0, old_weight + delta))
            modified_nodes = WorldStatePropagationService.propagate_relationship_change(
                db=db,
                source_slug=faction_a,
                target_slug=faction_b,
                rel_type="standing",
                new_weight=new_weight
            )

            duration = time.time() - start_time
            TelemetryService.record_narrative_metric(
                db,
                action_type="faction_standing_changes_total",
                npc_slug=faction_a,
                model_used=faction_b,
                input_tokens=1
            )
            TelemetryService.record_narrative_metric(
                db,
                action_type="narrative_orchestration_duration_seconds",
                npc_slug="system",
                model_used="shift_standing",
                latency_ms=int(duration * 1000)
            )

            return {
                "faction_a": faction_a,
                "faction_b": faction_b,
                "old_standing": old_weight,
                "new_standing": new_weight,
                "modified_relationships": modified_nodes
            }
        except Exception:
            db.rollback()
            raise
        finally:
            if lock_acquired:
                FactionDynamicsEngine._release_standing_lock(db, faction_a, faction_b)

    @staticmethod
    def propagate_reputation(db: Session, source_faction: str, entity_slug: str, delta: float) -> int:
        """
        Propagates standing/reputation changes of an entity (e.g. player or NPC) with a faction
        to other connected factions based on alliance/hostility relationships.
        Locks all involved entities in alphabetical order to avoid deadlocks.
        """
        # 1. Discover connected factions first to build lock set
        src_faction_ent = graph_repo.get_entity_by_slug(db, source_faction)
        if not src_faction_ent:
            return 0

        # Find all active standing relationships involving the source faction
        rels = db.query(WorldRelationship).filter(
            WorldRelationship.rel_type == "standing",
            WorldRelationship.valid_to.is_(None),
            (WorldRelationship.source_id == src_faction_ent.id) | (WorldRelationship.target_id == src_faction_ent.id)
        ).all()

        connected_factions: Dict[str, float] = {} # faction_slug -> standing weight
        for rel in rels:
            other_id = rel.target_id if rel.source_id == src_faction_ent.id else rel.source_id
            other_ent = db.query(WorldEntity).filter(WorldEntity.id == other_id).first()
            if other_ent:
                connected_factions[other_ent.slug] = rel.weight

        # Lock list: source_faction, entity_slug, plus all connected faction slugs
        lock_slugs = sorted(list({source_faction, entity_slug} | set(connected_factions.keys())))
        
        # alphabetical lock ordering required
        graph_repo._lock_entities_ordered(lock_slugs, db)

        updates_count = 0

        # 2. Update reputation with the source faction
        src_rep_rel = graph_repo.get_active_relationship(db, source_faction, entity_slug, "reputation")
        old_src_rep = src_rep_rel.weight if src_rep_rel else 50.0
        new_src_rep = max(0.0, min(100.0, old_src_rep + delta))

        if src_rep_rel:
            graph_repo.update_relationship(db, source_faction, entity_slug, "reputation", weight=new_src_rep)
        else:
            graph_repo.create_relationship(db, source_faction, entity_slug, "reputation", weight=new_src_rep)
        
        updates_count += 1
        TelemetryService.record_narrative_metric(
            db,
            action_type="faction_propagation_updates_total",
            npc_slug=source_faction,
            model_used=entity_slug
        )

        # 3. Propagate to connected factions
        for fac_slug, standing in connected_factions.items():
            # Allied factions (standing > 70) share positive/negative shifts by 50%
            # Hostile factions (standing < 30) shift in the opposite direction by 30%
            shift = 0.0
            if standing > 70.0:
                shift = delta * 0.5
            elif standing < 30.0:
                shift = -delta * 0.3

            if shift == 0.0:
                continue

            rep_rel = graph_repo.get_active_relationship(db, fac_slug, entity_slug, "reputation")
            old_rep = rep_rel.weight if rep_rel else 50.0
            new_rep = max(0.0, min(100.0, old_rep + shift))

            if rep_rel:
                graph_repo.update_relationship(db, fac_slug, entity_slug, "reputation", weight=new_rep)
            else:
                graph_repo.create_relationship(db, fac_slug, entity_slug, "reputation", weight=new_rep)
            
            updates_count += 1
            TelemetryService.record_narrative_metric(
                db,
                action_type="faction_propagation_updates_total",
                npc_slug=fac_slug,
                model_used=entity_slug
            )

        return updates_count
