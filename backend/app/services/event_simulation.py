import logging
from typing import List, Dict, Any, Set, Tuple
from sqlalchemy.orm import Session
from app.models.graph import WorldEntity, WorldRelationship
from app.services.telemetry_service import TelemetryService

logger = logging.getLogger("gamemind.event_simulation")

class EventChainSimulator:
    MAX_SIMULATION_DEPTH = 5
    MAX_BRANCHES = 50

    @classmethod
    def simulate_narrative_paths(cls, db: Session, starting_triggers: List[str]) -> Dict[str, Any]:
        """
        Runs a simulation of narrative events starting from a list of trigger slugs.
        Enforces MAX_SIMULATION_DEPTH = 5 and MAX_BRANCHES = 50.
        Returns:
            {
              "path": [...],
              "warnings": [...],
              "dead_end": bool
            }
        """
        # Record event simulation in telemetry
        TelemetryService.record_narrative_metric(
            db,
            action_type="event_simulations_total",
            npc_slug="system",
            model_used="event_simulation",
            error_str=None
        )

        warnings: List[str] = []
        if not starting_triggers:
            return {
                "path": [],
                "warnings": ["No starting triggers provided."],
                "dead_end": True
            }

        # Initialize visited nodes list representing the primary simulated path
        simulated_path: List[str] = []
        branch_count = 0
        limit_hit = False

        # Queue of paths to explore: list of slugs
        # Initialize queue with starting triggers as individual paths
        queue: List[List[str]] = [[trigger] for trigger in starting_triggers]
        completed_paths: List[List[str]] = []
        dead_ends_encountered = 0

        while queue:
            # Pop next path
            curr_path = queue.pop(0)
            curr_node = curr_path[-1]
            depth = len(curr_path)

            # Check depth limit
            if depth >= cls.MAX_SIMULATION_DEPTH:
                if not limit_hit and "Max simulation depth reached. Pruned further transitions." not in warnings:
                    warnings.append("Max simulation depth reached. Pruned further transitions.")
                completed_paths.append(curr_path)
                continue

            # Query active outgoing transitions from curr_node in the graph database
            # We look for relationships of type "triggers", "leads_to", "next", etc.
            curr_ent = db.query(WorldEntity).filter(WorldEntity.slug == curr_node).first()
            outgoing_transitions: List[str] = []
            
            if curr_ent:
                rels = db.query(WorldRelationship).filter(
                    WorldRelationship.source_id == curr_ent.id,
                    WorldRelationship.rel_type.in_(["triggers", "leads_to", "next"]),
                    WorldRelationship.valid_to.is_(None)
                ).all()
                for r in rels:
                    tgt = db.query(WorldEntity).filter(WorldEntity.id == r.target_id).first()
                    if tgt:
                        outgoing_transitions.append(tgt.slug)

            # If no outgoing transitions, this is a dead-end
            if not outgoing_transitions:
                completed_paths.append(curr_path)
                dead_ends_encountered += 1
                continue

            # Expand branches
            for next_node in outgoing_transitions:
                # Prevent cycle loop exploration inside simulation path
                if next_node in curr_path:
                    continue

                branch_count += 1
                if branch_count > cls.MAX_BRANCHES:
                    limit_hit = True
                    if "Max simulation branches reached. Pruning remaining paths." not in warnings:
                        warnings.append("Max simulation branches reached. Pruning remaining paths.")
                    break

                queue.append(curr_path + [next_node])

            if limit_hit:
                break

        # Select the longest completed path to represent the primary simulation result
        if completed_paths:
            completed_paths.sort(key=len, reverse=True)
            simulated_path = completed_paths[0]
        else:
            simulated_path = starting_triggers

        # A simulation is a dead end if we encountered any dead-ends in our traversal or hit boundaries
        is_dead_end = (
            dead_ends_encountered > 0 
            or limit_hit 
            or any(len(p) >= cls.MAX_SIMULATION_DEPTH for p in completed_paths)
        )

        if is_dead_end:
            # Record dead end in telemetry
            TelemetryService.record_narrative_metric(
                db,
                action_type="event_simulation_dead_ends_total",
                npc_slug="system",
                model_used="event_simulation",
                error_str="Simulation path hit a dead end"
            )

        return {
            "path": simulated_path,
            "warnings": warnings,
            "dead_end": is_dead_end
        }
