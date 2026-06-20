import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from app.database import get_db
from app.services.narrative_consistency import NarrativeConsistencyService
from app.services.quest_dependency import QuestDependencyAnalyzer
from app.services.event_simulation import EventChainSimulator
from app.services.temporal_audit import TemporalNarrativeAuditor
from app.services.narrative_orchestrator import NarrativeOrchestrator
from app.services.faction_dynamics import FactionDynamicsEngine
from app.services.narrative_forecasting import NarrativeForecaster
from app.schemas import EmotionUpdateRequest, EmotionResponse
from app.services.emotion_engine import EmotionEngine
from app.models.npc import NPCProfile


router = APIRouter(prefix="/narrative", tags=["narrative"])

# ----------------------------------------------------
# Pydantic Schemas
# ----------------------------------------------------
class ClaimModel(BaseModel):
    subject: str = Field(..., min_length=1)
    predicate: str = Field(..., min_length=1)
    object: str = Field(..., min_length=1)

class VerifyRequest(BaseModel):
    claims: List[ClaimModel]

class VerifyResponse(BaseModel):
    consistent: bool
    contradictions: List[str]

class EligibilityResponse(BaseModel):
    eligible: bool
    reason: Optional[str] = None

class SimulateRequest(BaseModel):
    starting_triggers: List[str]

class SimulateResponse(BaseModel):
    path: List[str]
    warnings: List[str]
    dead_end: bool

class AuditDiffResponse(BaseModel):
    entities_added: List[str]
    entities_removed: List[str]
    relationships_added: List[Dict[str, Any]]
    relationships_removed: List[Dict[str, Any]]
    relationships_changed: List[Dict[str, Any]]

class OrchestrateTickResponse(BaseModel):
    executed_events: List[str]
    pruned_events_count: int
    warnings: List[str]
    duration_seconds: float

class FactionStandingRequest(BaseModel):
    faction_a: str = Field(..., min_length=1)
    faction_b: str = Field(..., min_length=1)
    delta: float

class FactionStandingResponse(BaseModel):
    faction_a: str
    faction_b: str
    old_standing: float
    new_standing: float
    modified_relationships: int

class ForecastTrendResponse(BaseModel):
    trend_id: str
    predicted_state_change: str
    confidence_score: float
    affected_entities: List[str]

# ----------------------------------------------------
# Endpoints
# ----------------------------------------------------

@router.post("/verify", response_model=VerifyResponse, status_code=status.HTTP_200_OK)
def verify_claims(payload: VerifyRequest, db: Session = Depends(get_db)):
    """
    Validates a batch of structured claims against active graph relationships.
    Max 50 claims per request.
    """
    if len(payload.claims) > 50:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Payload exceeds maximum limit of 50 claims."
        )

    contradictions = []
    for claim in payload.claims:
        claim_dict = {
            "subject": claim.subject,
            "predicate": claim.predicate,
            "object": claim.object
        }
        consistent, reason = NarrativeConsistencyService.check_consistency(db, claim_dict)
        if not consistent and reason:
            contradictions.append(reason)

    return VerifyResponse(
        consistent=len(contradictions) == 0,
        contradictions=contradictions
    )


@router.get("/quests/{id}/eligibility", response_model=EligibilityResponse, status_code=status.HTTP_200_OK)
def check_quest_eligibility(
    id: uuid.UUID,
    player_id: Optional[str] = "default_player",
    db: Session = Depends(get_db)
):
    """
    Checks if a player is eligible to accept a quest based on graph prerequisites.
    """
    eligible, reason = QuestDependencyAnalyzer.is_eligible(db, player_id, str(id))
    return EligibilityResponse(eligible=eligible, reason=reason)


@router.post("/simulate", response_model=SimulateResponse, status_code=status.HTTP_200_OK)
def simulate_events(payload: SimulateRequest, db: Session = Depends(get_db)):
    """
    Simulates sequence of events starting from triggers.
    Max 10 starting triggers.
    """
    if len(payload.starting_triggers) > 10:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Simulation exceeds maximum limit of 10 starting triggers."
        )

    res = EventChainSimulator.simulate_narrative_paths(db, payload.starting_triggers)
    return SimulateResponse(
        path=res["path"],
        warnings=res["warnings"],
        dead_end=res["dead_end"]
    )


@router.get("/audit", response_model=AuditDiffResponse, status_code=status.HTTP_200_OK)
def audit_narrative_drift(
    as_of_start: str = Query(..., description="ISO 8601 Start datetime"),
    as_of_end: str = Query(..., description="ISO 8601 End datetime"),
    db: Session = Depends(get_db)
):
    """
    Returns diff-oriented output of state drift between two timestamps.
    Max audit window = 365 days.
    """
    try:
        def parse_iso(dt_str: str) -> datetime:
            if dt_str.endswith("Z"):
                cleaned = dt_str[:-1]
                if "+" in cleaned or "-" in cleaned[10:]:
                    return datetime.fromisoformat(cleaned)
                return datetime.fromisoformat(cleaned + "+00:00")
            return datetime.fromisoformat(dt_str)

        start_dt = parse_iso(as_of_start)
        end_dt = parse_iso(as_of_end)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid date format: {e}. Dates must be in ISO 8601 format."
        )

    # Check 365 day window limit
    if abs((end_dt - start_dt).days) > 365:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Audit window exceeds maximum range of 365 days."
        )

    diff = TemporalNarrativeAuditor.audit_state_drift(db, start_dt, end_dt)
    return AuditDiffResponse(
        entities_added=diff["entities_added"],
        entities_removed=diff["entities_removed"],
        relationships_added=diff["relationships_added"],
        relationships_removed=diff["relationships_removed"],
        relationships_changed=diff["relationships_changed"]
    )


@router.post("/orchestrate/tick", response_model=OrchestrateTickResponse, status_code=status.HTTP_200_OK)
def orchestrate_narrative_tick(db: Session = Depends(get_db)):
    """
    Triggers evaluation and processes event queue tick.
    """
    res = NarrativeOrchestrator.execute_tick(db, datetime.utcnow())
    return OrchestrateTickResponse(
        executed_events=res["executed_events"],
        pruned_events_count=res["pruned_events_count"],
        warnings=res["warnings"],
        duration_seconds=res["duration_seconds"]
    )


@router.post("/factions/standing", response_model=FactionStandingResponse, status_code=status.HTTP_200_OK)
def update_faction_standing(payload: FactionStandingRequest, db: Session = Depends(get_db)):
    """
    Updates faction standing relation weight and propagates changes.
    """
    res = FactionDynamicsEngine.shift_standing(
        db, payload.faction_a, payload.faction_b, payload.delta
    )
    return FactionStandingResponse(
        faction_a=res["faction_a"],
        faction_b=res["faction_b"],
        old_standing=res["old_standing"],
        new_standing=res["new_standing"],
        modified_relationships=res["modified_relationships"]
    )


@router.get("/forecast", response_model=List[ForecastTrendResponse], status_code=status.HTTP_200_OK)
def get_narrative_forecast(
    steps: int = Query(default=3, description="Forecast simulation steps"),
    db: Session = Depends(get_db)
):
    """
    Retrieves projected state trajectories. Max steps = 5.
    """
    if steps < 1 or steps > 5:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Forecast steps must be between 1 and 5."
        )

    res = NarrativeForecaster.forecast_trends(db, steps)
    return [
        ForecastTrendResponse(
            trend_id=trend["trend_id"],
            predicted_state_change=trend["predicted_state_change"],
            confidence_score=trend["confidence_score"],
            affected_entities=trend["affected_entities"]
        )
        for trend in res
    ]

@router.get("/emotion", response_model=EmotionResponse, status_code=status.HTTP_200_OK)
def get_npc_emotion(
    npc_slug: str = Query(..., min_length=1),
    player_id: str = Query("default_player"),
    db: Session = Depends(get_db)
):
    """
    Retrieves the 5 emotional states of an NPC with respect to a player.
    """
    npc = db.query(NPCProfile).filter(NPCProfile.slug == npc_slug, NPCProfile.deleted_at.is_(None)).first()
    if not npc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"NPC with slug '{npc_slug}' not found.")
    
    emotions = EmotionEngine.get_emotional_state(db, npc_slug, player_id)
    return EmotionResponse(npc_slug=npc_slug, player_id=player_id, emotions=emotions)

@router.post("/emotion", response_model=EmotionResponse, status_code=status.HTTP_200_OK)
def update_npc_emotion(payload: EmotionUpdateRequest, db: Session = Depends(get_db)):
    """
    Updates specified NPC emotional states. Strict range validation (0-100) is enforced.
    """
    npc = db.query(NPCProfile).filter(NPCProfile.slug == payload.npc_slug, NPCProfile.deleted_at.is_(None)).first()
    if not npc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"NPC with slug '{payload.npc_slug}' not found.")

    try:
        updated_emotions = EmotionEngine.update_emotional_state(
            db=db,
            npc_slug=payload.npc_slug,
            player_id=payload.player_id,
            updates=payload.updates,
            reason=payload.reason
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    return EmotionResponse(npc_slug=payload.npc_slug, player_id=payload.player_id, emotions=updated_emotions)


