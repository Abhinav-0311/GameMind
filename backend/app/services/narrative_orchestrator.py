import logging
import time
from datetime import datetime
from typing import List, Dict, Any, Set, Tuple
from sqlalchemy.orm import Session
from app.services.event_scheduler import WorldEventScheduler
from app.services.faction_dynamics import FactionDynamicsEngine
from app.services.telemetry_service import TelemetryService

logger = logging.getLogger("gamemind.narrative_orchestrator")

class NarrativeOrchestrator:
    MAX_EVENT_CHAIN_DEPTH = 3
    MAX_EVENTS_PER_TICK = 10

    @classmethod
    def execute_tick(cls, db: Session, current_time: datetime) -> Dict[str, Any]:
        """
        Executes a narrative evolution tick.
        Evaluates triggers, filters/resolves conflicts, runs effects, and propagates updates within limits.
        """
        start_time = time.time()
        
        # 1. Evaluate triggers
        triggered_templates = WorldEventScheduler.evaluate_triggers(db, current_time)
        
        # 2. Resolve conflicts among triggered templates
        resolved_templates = cls.resolve_conflicts(triggered_templates)
        
        executed_events: List[str] = []
        warnings: List[str] = []
        pruned_count = 0
        total_triggered = 0

        # Queue of events to execute: (template_dict, current_depth)
        queue: List[Tuple[Dict[str, Any], int]] = [(t, 1) for t in resolved_templates]

        while queue:
            temp, depth = queue.pop(0)
            
            # Check Max Events per Tick limit
            if total_triggered >= cls.MAX_EVENTS_PER_TICK:
                pruned_count += 1
                TelemetryService.record_narrative_metric(
                    db,
                    action_type="narrative_events_pruned_total",
                    npc_slug="system",
                    model_used=temp["slug"],
                    error_str="Max events per tick limit exceeded"
                )
                if "Tick event threshold exceeded. Pruning remainder." not in warnings:
                    warnings.append("Tick event threshold exceeded. Pruning remainder.")
                continue

            # Check Max nested chain depth limit
            if depth > cls.MAX_EVENT_CHAIN_DEPTH:
                pruned_count += 1
                TelemetryService.record_narrative_metric(
                    db,
                    action_type="narrative_events_pruned_total",
                    npc_slug="system",
                    model_used=temp["slug"],
                    error_str="Max event chain depth exceeded"
                )
                if "Max nested event chain depth reached. Pruning child transitions." not in warnings:
                    warnings.append("Max nested event chain depth reached. Pruning child transitions.")
                continue

            # Execute event effects
            cls._execute_effects(db, temp.get("properties", {}).get("effects", {}))
            executed_events.append(temp["slug"])
            total_triggered += 1

            # Log triggered event in telemetry
            TelemetryService.record_narrative_metric(
                db,
                action_type="narrative_events_triggered_total",
                npc_slug="system",
                model_used=temp["slug"]
            )

            # Evaluate any child events directly chained to this event in properties
            child_slugs = temp.get("properties", {}).get("chained_events", [])
            if child_slugs:
                # Find matching event templates in database to enqueue
                from app.models.graph import WorldEntity, WorldEntityVersion
                child_templates = db.query(WorldEntity).filter(
                    WorldEntity.entity_type == "event_template",
                    WorldEntity.slug.in_(child_slugs)
                ).all()

                for ct in child_templates:
                    active_ver = db.query(WorldEntityVersion).filter(
                        WorldEntityVersion.entity_id == ct.id,
                        WorldEntityVersion.valid_to.is_(None)
                    ).first()
                    if active_ver:
                        queue.append(({
                            "id": str(ct.id),
                            "slug": ct.slug,
                            "title": active_ver.name,
                            "properties": active_ver.properties
                        }, depth + 1))

        duration = time.time() - start_time

        # Log orchestration duration
        TelemetryService.record_narrative_metric(
            db,
            action_type="narrative_orchestration_duration_seconds",
            npc_slug="system",
            model_used="execute_tick",
            latency_ms=int(duration * 1000)
        )

        return {
            "executed_events": executed_events,
            "pruned_events_count": pruned_count,
            "warnings": warnings,
            "duration_seconds": duration
        }

    @classmethod
    def resolve_conflicts(cls, templates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Resolves conflicts between competing templates.
        If multiple templates share a conflict_group, we select the one with the highest priority.
        """
        conflict_groups: Dict[str, List[Dict[str, Any]]] = {}
        non_conflicting: List[Dict[str, Any]] = []

        for t in templates:
            group = t.get("properties", {}).get("conflict_group")
            if group:
                if group not in conflict_groups:
                    conflict_groups[group] = []
                conflict_groups[group].append(t)
            else:
                non_conflicting.append(t)

        resolved: List[Dict[str, Any]] = list(non_conflicting)

        for group, group_temps in conflict_groups.items():
            # Sort by priority (default to 0 if not defined)
            group_temps.sort(
                key=lambda x: x.get("properties", {}).get("priority", 0),
                reverse=True
            )
            # Choose the highest priority one
            resolved.append(group_temps[0])

        return resolved

    @staticmethod
    def _execute_effects(db: Session, effects: Dict[str, Any]) -> None:
        """Helper to run standing_shift or reputation_shift effects."""
        if not effects:
            return

        # 1. Standing shifts
        standing_shift = effects.get("standing_shift")
        if standing_shift:
            source = standing_shift.get("source")
            target = standing_shift.get("target")
            delta = standing_shift.get("delta")
            if source and target and delta is not None:
                FactionDynamicsEngine.shift_standing(db, source, target, delta)

        # 2. Reputation shifts
        reputation_shift = effects.get("reputation_shift")
        if reputation_shift:
            faction = reputation_shift.get("faction")
            entity = reputation_shift.get("entity")
            delta = reputation_shift.get("delta")
            if faction and entity and delta is not None:
                FactionDynamicsEngine.propagate_reputation(db, faction, entity, delta)
