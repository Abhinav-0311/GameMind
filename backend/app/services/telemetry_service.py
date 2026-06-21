import uuid
from typing import Optional, Dict, List, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from app.models.telemetry import LLMTelemetryLog
from app.models.memory import NPCMemory

class TelemetryService:
    @staticmethod
    def record_log(
        db: Session,
        npc_slug: str,
        model_used: str,
        llm_provider: str,
        latency_ms: int,
        action_type: str = "dialogue",
        input_tokens: int = 0,
        output_tokens: int = 0,
        estimated_cost_usd: float = 0.0,
        safety_blocked: bool = False,
        safety_ratings: Optional[List] = None,
        error: Optional[str] = None,
        conversation_id: Optional[uuid.UUID] = None
    ) -> LLMTelemetryLog:
        # Extract short error classification (e.g. first line or exception name)
        short_error = None
        if error:
            # Grab exception name or first phrase
            cleaned = str(error).split("\n")[0].strip()
            if ":" in cleaned:
                cleaned = cleaned.split(":")[0].strip()
            short_error = cleaned[:100]

        log = LLMTelemetryLog(
            conversation_id=conversation_id,
            action_type=action_type,
            npc_slug=npc_slug,
            model_used=model_used,
            llm_provider=llm_provider,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=estimated_cost_usd,
            safety_blocked=safety_blocked,
            safety_ratings=safety_ratings,
            error=short_error
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        return log

    @staticmethod
    def get_overview_metrics(db: Session, game_project_id: str = "default_project") -> Dict:
        """Fetch total cost, average latency, request counts, and token summaries scoped by project."""
        from app.models.npc import NPCProfile
        project_npcs_subquery = db.query(NPCProfile.slug).filter(NPCProfile.game_project_id == game_project_id)

        total_cost = db.query(func.sum(LLMTelemetryLog.estimated_cost_usd)).filter(LLMTelemetryLog.npc_slug.in_(project_npcs_subquery)).scalar() or 0.0
        total_requests = db.query(func.count(LLMTelemetryLog.id)).filter(LLMTelemetryLog.npc_slug.in_(project_npcs_subquery)).scalar() or 0
        avg_latency = db.query(func.avg(LLMTelemetryLog.latency_ms)).filter(LLMTelemetryLog.npc_slug.in_(project_npcs_subquery)).scalar() or 0.0
        total_input_tokens = db.query(func.sum(LLMTelemetryLog.input_tokens)).filter(LLMTelemetryLog.npc_slug.in_(project_npcs_subquery)).scalar() or 0
        total_output_tokens = db.query(func.sum(LLMTelemetryLog.output_tokens)).filter(LLMTelemetryLog.npc_slug.in_(project_npcs_subquery)).scalar() or 0
        safety_blocked_count = db.query(func.count(LLMTelemetryLog.id)).filter(
            LLMTelemetryLog.npc_slug.in_(project_npcs_subquery),
            LLMTelemetryLog.safety_blocked == True
        ).scalar() or 0
        error_count = db.query(func.count(LLMTelemetryLog.id)).filter(
            LLMTelemetryLog.npc_slug.in_(project_npcs_subquery),
            LLMTelemetryLog.error.isnot(None)
        ).scalar() or 0

        # Breakdowns
        by_action = db.query(
            LLMTelemetryLog.action_type, 
            func.count(LLMTelemetryLog.id), 
            func.sum(LLMTelemetryLog.estimated_cost_usd)
        ).filter(LLMTelemetryLog.npc_slug.in_(project_npcs_subquery)).group_by(LLMTelemetryLog.action_type).all()
        
        by_model = db.query(
            LLMTelemetryLog.model_used, 
            func.count(LLMTelemetryLog.id)
        ).filter(LLMTelemetryLog.npc_slug.in_(project_npcs_subquery)).group_by(LLMTelemetryLog.model_used).all()

        return {
            "total_cost_usd": float(total_cost),
            "total_requests": total_requests,
            "avg_latency_ms": float(avg_latency),
            "total_input_tokens": int(total_input_tokens),
            "total_output_tokens": int(total_output_tokens),
            "safety_blocked_count": safety_blocked_count,
            "error_count": error_count,
            "breakdown_by_action": [{"action": r[0], "count": r[1], "cost": float(r[2] or 0.0)} for r in by_action],
            "breakdown_by_model": [{"model": r[0], "count": r[1]} for r in by_model]
        }
        
    @staticmethod
    def get_cost_breakdown(db: Session, game_project_id: str = "default_project") -> List[Dict]:
        """Fetch cost breakdowns by NPC profile scoped by project."""
        from app.models.npc import NPCProfile
        project_npcs_subquery = db.query(NPCProfile.slug).filter(NPCProfile.game_project_id == game_project_id)

        rows = db.query(
            LLMTelemetryLog.npc_slug, 
            func.count(LLMTelemetryLog.id), 
            func.sum(LLMTelemetryLog.estimated_cost_usd)
        ).filter(LLMTelemetryLog.npc_slug.in_(project_npcs_subquery)).group_by(LLMTelemetryLog.npc_slug).all()
        return [{"npc_slug": r[0], "requests_count": r[1], "total_cost_usd": float(r[2] or 0.0)} for r in rows]

    @staticmethod
    def get_memory_metrics(db: Session, game_project_id: str = "default_project") -> Dict:
        """Fetch statistics about active, archived, promoted, and failed memories scoped by project."""
        active_count = db.query(func.count(NPCMemory.id)).filter(
            NPCMemory.archived == False,
            NPCMemory.game_project_id == game_project_id
        ).scalar() or 0
        archived_count = db.query(func.count(NPCMemory.id)).filter(
            NPCMemory.archived == True,
            NPCMemory.game_project_id == game_project_id
        ).scalar() or 0
        promoted_count = db.query(func.count(NPCMemory.id)).filter(
            NPCMemory.conversation_id.isnot(None),
            NPCMemory.game_project_id == game_project_id
        ).scalar() or 0
        avg_importance = db.query(func.avg(NPCMemory.importance_score)).filter(
            NPCMemory.game_project_id == game_project_id
        ).scalar() or 0.0
        failed_indexing = db.query(func.count(NPCMemory.id)).filter(
            NPCMemory.chroma_indexed == False,
            NPCMemory.game_project_id == game_project_id
        ).scalar() or 0
        
        return {
            "active_memories": active_count,
            "archived_memories": archived_count,
            "promoted_memories": promoted_count,
            "average_importance_score": float(avg_importance),
            "failed_chroma_indexing_count": failed_indexing
        }

    @staticmethod
    def record_graph_entity_create(
        db: Session,
        slug: str,
        entity_type: str
    ) -> LLMTelemetryLog:
        log = LLMTelemetryLog(
            conversation_id=None,
            action_type="graph_entity_create",
            npc_slug=slug[:100],
            model_used=entity_type[:100],
            llm_provider="database",
            latency_ms=0,
            input_tokens=1,
            output_tokens=0,
            estimated_cost_usd=0.0,
            safety_blocked=False,
            safety_ratings=None,
            error=None
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        return log

    @staticmethod
    def record_graph_relationship_create(
        db: Session,
        source_slug: str,
        target_slug: str,
        rel_type: str
    ) -> LLMTelemetryLog:
        log = LLMTelemetryLog(
            conversation_id=None,
            action_type="graph_relationship_create",
            npc_slug=f"{source_slug[:48]}->{target_slug[:48]}",
            model_used=rel_type[:100],
            llm_provider="database",
            latency_ms=0,
            input_tokens=1,
            output_tokens=0,
            estimated_cost_usd=0.0,
            safety_blocked=False,
            safety_ratings=None,
            error=None
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        return log

    @staticmethod
    def record_graph_validation_failure(
        db: Session,
        operation: str,
        reason: str
    ) -> LLMTelemetryLog:
        log = LLMTelemetryLog(
            conversation_id=None,
            action_type="graph_validation_failure",
            npc_slug=operation[:100],
            model_used="validator",
            llm_provider="database",
            latency_ms=0,
            input_tokens=1,
            output_tokens=0,
            estimated_cost_usd=0.0,
            safety_blocked=True,
            safety_ratings=None,
            error=reason[:255]
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        return log

    @staticmethod
    def record_graph_override(
        db: Session,
        validation_id: uuid.UUID,
        applied_by: str
    ) -> LLMTelemetryLog:
        log = LLMTelemetryLog(
            conversation_id=None,
            action_type="graph_override",
            npc_slug=applied_by[:100],
            model_used=str(validation_id)[:100],
            llm_provider="database",
            latency_ms=0,
            input_tokens=1,
            output_tokens=0,
            estimated_cost_usd=0.0,
            safety_blocked=False,
            safety_ratings=None,
            error=None
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        return log

    @staticmethod
    def record_narrative_metric(
        db: Session,
        action_type: str,
        npc_slug: str = "system",
        model_used: str = "narrative_engine",
        error_str: Optional[str] = None,
        latency_ms: int = 0,
        input_tokens: int = 1
    ) -> LLMTelemetryLog:
        log = LLMTelemetryLog(
            conversation_id=None,
            action_type=action_type,
            npc_slug=npc_slug[:100],
            model_used=model_used[:100],
            llm_provider="database",
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=0,
            estimated_cost_usd=0.0,
            safety_blocked=False,
            safety_ratings=None,
            error=error_str[:255] if error_str else None
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        return log


    @staticmethod
    def record_graph_pending_ingest_cleanup_run(
        db: Session
    ) -> LLMTelemetryLog:
        log = LLMTelemetryLog(
            conversation_id=None,
            action_type="graph_pending_ingest_cleanup_run",
            npc_slug="cleanup_worker",
            model_used="pruner",
            llm_provider="database",
            latency_ms=0,
            input_tokens=1,
            output_tokens=0,
            estimated_cost_usd=0.0,
            safety_blocked=False,
            safety_ratings=None,
            error=None
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        return log

    @staticmethod
    def record_graph_pending_ingest_cleanup_rows(
        db: Session,
        pruned_count: int
    ) -> LLMTelemetryLog:
        log = LLMTelemetryLog(
            conversation_id=None,
            action_type="graph_pending_ingest_cleanup_rows",
            npc_slug="cleanup_worker",
            model_used="pruner",
            llm_provider="database",
            latency_ms=0,
            input_tokens=pruned_count,
            output_tokens=0,
            estimated_cost_usd=0.0,
            safety_blocked=False,
            safety_ratings=None,
            error=None
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        return log

    @staticmethod
    def get_graph_metrics(db: Session, game_project_id: str = "default_project") -> Dict:
        """Fetch counts and aggregates for all custom graph metrics scoped by project."""
        from app.models.graph import PendingIngest, WorldEntity
        
        project_entities_subquery = db.query(WorldEntity.slug).filter(WorldEntity.game_project_id == game_project_id)
        
        entity_creates = db.query(func.count(LLMTelemetryLog.id)).filter(
            LLMTelemetryLog.action_type == "graph_entity_create",
            LLMTelemetryLog.npc_slug.in_(project_entities_subquery)
        ).scalar() or 0
        
        relationship_creates = db.query(func.count(LLMTelemetryLog.id)).filter(
            LLMTelemetryLog.action_type == "graph_relationship_create"
        ).scalar() or 0
        
        validation_failures = db.query(func.count(LLMTelemetryLog.id)).filter(
            LLMTelemetryLog.action_type == "graph_validation_failure"
        ).scalar() or 0
        
        overrides = db.query(func.count(LLMTelemetryLog.id)).filter(
            LLMTelemetryLog.action_type == "graph_override"
        ).scalar() or 0
        
        pending_count = db.query(func.count(PendingIngest.validation_id)).scalar() or 0
        
        lock_wait_seconds = None  # Deprecated and unavailable
        
        cleanup_runs = db.query(func.count(LLMTelemetryLog.id)).filter(
            LLMTelemetryLog.action_type == "graph_pending_ingest_cleanup_run"
        ).scalar() or 0
        
        cleanup_rows = db.query(func.sum(LLMTelemetryLog.input_tokens)).filter(
            LLMTelemetryLog.action_type == "graph_pending_ingest_cleanup_rows"
        ).scalar() or 0
        
        return {
            "graph_entity_create_total": entity_creates,
            "graph_relationship_create_total": relationship_creates,
            "graph_validation_failure_total": validation_failures,
            "graph_override_total": overrides,
            "graph_pending_ingest_count": pending_count,
            "graph_schema_lock_wait_seconds": lock_wait_seconds,
            "graph_pending_ingest_cleanup_runs_total": cleanup_runs,
            "graph_pending_ingest_cleanup_rows_total": int(cleanup_rows)
        }

    @staticmethod
    def get_conversation_metrics(db: Session) -> Dict:
        """Fetch counts and aggregates for all custom conversation engine metrics (Phase 8)."""
        metrics = [
            "personality_profile_evaluations_total",
            "emotion_state_reads_total",
            "emotional_state_updates_total",
            "conversation_plans_generated_total",
            "conversation_continuity_evaluations_total",
            "dialogue_style_directives_generated_total",
            "dialogue_prompt_sections_generated_total",
            "dialogue_assembly_duration_seconds",
            "dialogue_assembled_tokens_total",
            "dialogue_history_messages_scanned_total"
        ]
        results = {}
        for m in metrics:
            val = db.query(func.count(LLMTelemetryLog.id)).filter(
                LLMTelemetryLog.action_type == m
            ).scalar() or 0
            if m == "dialogue_assembly_duration_seconds":
                sum_ms = db.query(func.sum(LLMTelemetryLog.latency_ms)).filter(
                    LLMTelemetryLog.action_type == m
                ).scalar() or 0
                results[m] = float(sum_ms) / 1000.0
            elif m == "dialogue_assembled_tokens_total":
                sum_tokens = db.query(func.sum(LLMTelemetryLog.input_tokens)).filter(
                    LLMTelemetryLog.action_type == m
                ).scalar() or 0
                results[m] = int(sum_tokens)
            else:
                results[m] = val
        return results

    @staticmethod
    def record_production_metric(
        db: Session,
        name: str,
        value: Any,
        npc_slug: str = "system",
        model_used: str = "production_telemetry",
        latency_ms: int = 0
    ) -> LLMTelemetryLog:
        log = LLMTelemetryLog(
            conversation_id=None,
            action_type=name,
            npc_slug=npc_slug[:100],
            model_used=model_used[:100],
            llm_provider="database",
            latency_ms=latency_ms,
            input_tokens=int(value) if isinstance(value, (int, float)) else 1,
            output_tokens=0,
            estimated_cost_usd=0.0,
            safety_blocked=False,
            safety_ratings=None,
            error=None
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        return log

    @staticmethod
    def get_production_metrics(db: Session) -> Dict[str, Any]:
        metrics = [
            "memory_usage_bytes",
            "active_db_connections",
            "cache_utilization",
            "cache_evictions_total",
            "orchestration_queue_depth",
            "forecast_execution_duration_seconds",
            "dialogue_generation_duration_seconds",
            "quest_generation_duration_seconds"
        ]
        results = {}
        for m in metrics:
            val = db.query(func.count(LLMTelemetryLog.id)).filter(
                LLMTelemetryLog.action_type == m
            ).scalar() or 0
            if "duration_seconds" in m:
                sum_ms = db.query(func.sum(LLMTelemetryLog.latency_ms)).filter(
                    LLMTelemetryLog.action_type == m
                ).scalar() or 0
                results[m] = float(sum_ms) / 1000.0
            elif m in ["memory_usage_bytes", "active_db_connections", "orchestration_queue_depth"]:
                avg_val = db.query(func.avg(LLMTelemetryLog.input_tokens)).filter(
                    LLMTelemetryLog.action_type == m
                ).scalar() or 0.0
                results[m] = float(avg_val)
            else:
                sum_tokens = db.query(func.sum(LLMTelemetryLog.input_tokens)).filter(
                    LLMTelemetryLog.action_type == m
                ).scalar() or 0
                results[m] = int(sum_tokens)
        return results

