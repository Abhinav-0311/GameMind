import logging
from collections import deque
from typing import Set, Dict, Any, List
from sqlalchemy.orm import Session
from app.models.graph import WorldEntity, WorldRelationship
from app.models.world_state import WorldStateFlag
from app.repositories.graph_repository import graph_repo
from app.services.telemetry_service import TelemetryService

logger = logging.getLogger("gamemind.world_state_propagation")

class PropagationLimitExceededError(ValueError):
    """Raised when world state propagation exceeds depth or node limits."""
    pass

class WorldStatePropagationService:
    MAX_PROPAGATION_DEPTH = 2
    MAX_PROPAGATION_NODES = 100

    @classmethod
    def propagate_relationship_change(
        cls,
        db: Session,
        source_slug: str,
        target_slug: str,
        rel_type: str,
        new_weight: float
    ) -> int:
        """
        Propagates relationship changes to adjacent vertices in the graph up to depth 2.
        Caps total modified relationship edges to 100.
        Rolls back the active transaction and raises PropagationLimitExceededError if boundaries are breached.
        """
        # Step 1: Alphabetical lock ordering to prevent concurrent deadlocks
        graph_repo._lock_entities_ordered([source_slug, target_slug], db)

        # Step 2: Fetch the active relationship
        active_rel = graph_repo.get_active_relationship(
            db, source_slug, target_slug, rel_type, for_update=True
        )
        if not active_rel:
            logger.warning(f"No active relationship found between '{source_slug}' and '{target_slug}' of type '{rel_type}' to propagate.")
            return 0

        old_weight = active_rel.weight
        delta_weight = new_weight - old_weight
        if delta_weight == 0.0:
            return 0

        # Record world state propagation check in telemetry
        TelemetryService.record_narrative_metric(
            db,
            action_type="world_state_propagations_total",
            npc_slug=source_slug,
            model_used=rel_type,
            error_str=None
        )

        # Update the root relationship first
        updated_root = graph_repo.update_relationship(
            db=db,
            source_slug=source_slug,
            target_slug=target_slug,
            rel_type=rel_type,
            weight=new_weight
        )
        if not updated_root:
            return 0

        # Step 3: Enforce threshold-based state flag rules
        cls._apply_threshold_rules(db, rel_type, new_weight)

        # Step 4: BFS propagation
        # Queue stores: (entity_id, current_depth, delta_to_propagate)
        queue = deque()
        source_ent = graph_repo.get_entity_by_slug(db, source_slug)
        target_ent = graph_repo.get_entity_by_slug(db, target_slug)
        
        # Enqueue the direct endpoints at depth 1 with half the delta weight
        if source_ent:
            queue.append((source_ent.id, 1, delta_weight * 0.5))
        if target_ent:
            queue.append((target_ent.id, 1, delta_weight * 0.5))

        visited_relationships: Set[Any] = {active_rel.id, updated_root.id}
        modified_count = 1

        while queue:
            curr_id, depth, delta = queue.popleft()

            if depth > cls.MAX_PROPAGATION_DEPTH:
                continue

            # Query active adjacent relationships
            adj_rels = db.query(WorldRelationship).filter(
                WorldRelationship.valid_to.is_(None),
                (WorldRelationship.source_id == curr_id) | (WorldRelationship.target_id == curr_id)
            ).all()

            for rel in adj_rels:
                if rel.id in visited_relationships:
                    continue

                visited_relationships.add(rel.id)
                modified_count += 1

                # If limit exceeded, fail-fast and rollback
                if len(visited_relationships) > cls.MAX_PROPAGATION_NODES:
                    db.rollback()
                    TelemetryService.record_narrative_metric(
                        db,
                        action_type="world_state_propagations_total",
                        npc_slug=source_slug,
                        model_used=rel_type,
                        error_str="Limit Exceeded"
                    )
                    raise PropagationLimitExceededError(
                        f"Propagation limits exceeded: total visited relationship edges > {cls.MAX_PROPAGATION_NODES}."
                    )

                # Get adjacent node details
                src_node = db.query(WorldEntity).filter(WorldEntity.id == rel.source_id).first()
                tgt_node = db.query(WorldEntity).filter(WorldEntity.id == rel.target_id).first()
                if not src_node or not tgt_node:
                    continue

                # Lock alphabetically before modifying
                graph_repo._lock_entities_ordered([src_node.slug, tgt_node.slug], db)

                # Update the adjacent relationship weight
                next_weight = max(0.0, min(100.0, rel.weight + delta))
                new_rel = graph_repo.update_relationship(
                    db=db,
                    source_slug=src_node.slug,
                    target_slug=tgt_node.slug,
                    rel_type=rel.rel_type,
                    weight=next_weight
                )
                if new_rel:
                    visited_relationships.add(new_rel.id)

                # Apply threshold flags to this updated adjacent edge
                cls._apply_threshold_rules(db, rel.rel_type, next_weight)

                # Enqueue the neighbor for next hop propagation
                other_id = rel.target_id if rel.source_id == curr_id else rel.source_id
                queue.append((other_id, depth + 1, delta * 0.5))

        return modified_count

    @staticmethod
    def _apply_threshold_rules(db: Session, rel_type: str, weight: float) -> None:
        """
        Threshold-based propagation rules:
        - If standing or faction relation falls below 20 -> set hostilities_present = "true"
        - If standing or faction relation is >= 20 -> set hostilities_present = "false"
        """
        if rel_type in ("standing", "faction_relation", "allied_with"):
            flag = db.query(WorldStateFlag).filter(WorldStateFlag.flag_key == "hostilities_present").first()
            target_val = "true" if weight < 20.0 else "false"
            
            if flag:
                if flag.flag_value != target_val:
                    flag.flag_value = target_val
            else:
                new_flag = WorldStateFlag(
                    flag_key="hostilities_present",
                    flag_value=target_val,
                    is_active=True,
                    priority=10
                )
                db.add(new_flag)
            db.flush()
