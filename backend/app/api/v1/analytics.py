from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.telemetry_service import TelemetryService
from typing import Optional

router = APIRouter(prefix="/analytics", tags=["analytics"])

@router.get("/overview")
def get_overview(db: Session = Depends(get_db)):
    """Retrieve overall LLM usage metrics (requests count, total costs, avg latency, and token totals)."""
    try:
        return TelemetryService.get_overview_metrics(db)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch overview metrics: {e}"
        )

@router.get("/costs")
def get_costs(db: Session = Depends(get_db)):
    """Retrieve cost allocations aggregated by NPC profile."""
    try:
        return TelemetryService.get_cost_breakdown(db)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch cost breakdowns: {e}"
        )

@router.get("/memory")
def get_memory_stats(db: Session = Depends(get_db)):
    """Retrieve counts of active, archived, promoted memories, average importance score, and indexing failures."""
    try:
        return TelemetryService.get_memory_metrics(db)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch memory metrics: {e}"
        )

@router.get("/logs")
def get_logs(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    npc_slug: Optional[str] = None,
    action_type: Optional[str] = None,
    has_error: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """Retrieve paginated and filterable raw telemetry trace logs."""
    try:
        from app.models.telemetry import LLMTelemetryLog
        from sqlalchemy import desc
        query = db.query(LLMTelemetryLog)
        
        if npc_slug:
            query = query.filter(LLMTelemetryLog.npc_slug == npc_slug)
        if action_type:
            query = query.filter(LLMTelemetryLog.action_type == action_type)
        if has_error is not None:
            if has_error:
                query = query.filter(LLMTelemetryLog.error.isnot(None))
            else:
                query = query.filter(LLMTelemetryLog.error.is_(None))
                
        total = query.count()
        logs = query.order_by(desc(LLMTelemetryLog.created_at)).offset(offset).limit(limit).all()
        
        # Serialize DECIMAL fields to float for clean JSON output
        serialized_logs = []
        for log in logs:
            serialized_logs.append({
                "id": str(log.id),
                "conversation_id": str(log.conversation_id) if log.conversation_id else None,
                "action_type": log.action_type,
                "npc_slug": log.npc_slug,
                "model_used": log.model_used,
                "llm_provider": log.llm_provider,
                "latency_ms": log.latency_ms,
                "input_tokens": log.input_tokens,
                "output_tokens": log.output_tokens,
                "estimated_cost_usd": float(log.estimated_cost_usd),
                "safety_blocked": log.safety_blocked,
                "safety_ratings": log.safety_ratings,
                "error": log.error,
                "created_at": log.created_at.isoformat()
            })
            
        return {
            "total": total,
            "logs": serialized_logs
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch telemetry logs: {e}"
        )

@router.get("/graph")
def get_graph_stats(db: Session = Depends(get_db)):
    """Retrieve graph database metrics (entity creations, overrides, validation failures, schema locks, etc.)."""
    try:
        return TelemetryService.get_graph_metrics(db)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch graph metrics: {e}"
        )
