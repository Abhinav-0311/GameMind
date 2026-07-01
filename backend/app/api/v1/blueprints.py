from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List
from datetime import datetime

from app.database import get_db
from app.dependencies import get_game_project_id
from app.schemas import (
    BlueprintGenerateRequest, BlueprintResponse, BlueprintExportResponse,
    MaterializationReportResponse, BlueprintRuntimeBundleResponse
)
from app.models.blueprint import GameBlueprint
from app.services.blueprint_service import BlueprintService
from app.services.materializer_service import BlueprintMaterializerService

router = APIRouter(prefix="/blueprints", tags=["blueprints"])

def get_blueprint_service():
    return BlueprintService()

def get_materializer_service():
    return BlueprintMaterializerService()

@router.post("/generate", response_model=BlueprintResponse, status_code=status.HTTP_201_CREATED)
def generate_blueprint(
    request: BlueprintGenerateRequest,
    db: Session = Depends(get_db),
    game_project_id: str = Depends(get_game_project_id),
    blueprint_service: BlueprintService = Depends(get_blueprint_service)
):
    """Generates a structured game blueprint from an existing GDD document."""
    return blueprint_service.generate_blueprint_from_gdd(db, request.document_id, game_project_id)

@router.get("/", response_model=List[BlueprintResponse])
def list_blueprints(
    db: Session = Depends(get_db),
    game_project_id: str = Depends(get_game_project_id)
):
    """Lists all game blueprints scoped to the active project."""
    return db.query(GameBlueprint).filter(GameBlueprint.game_project_id == game_project_id).all()

@router.get("/{blueprint_id}", response_model=BlueprintResponse)
def get_blueprint(
    blueprint_id: UUID,
    db: Session = Depends(get_db),
    game_project_id: str = Depends(get_game_project_id)
):
    """Returns details for a specific game blueprint."""
    blueprint = db.query(GameBlueprint).filter(
        GameBlueprint.id == blueprint_id,
        GameBlueprint.game_project_id == game_project_id
    ).first()
    if not blueprint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blueprint not found or not owned by this project."
        )
    return blueprint

@router.put("/{blueprint_id}/approve", response_model=BlueprintResponse)
def approve_blueprint(
    blueprint_id: UUID,
    db: Session = Depends(get_db),
    game_project_id: str = Depends(get_game_project_id)
):
    """Approves a game blueprint, updating its status to 'approved'."""
    blueprint = db.query(GameBlueprint).filter(
        GameBlueprint.id == blueprint_id,
        GameBlueprint.game_project_id == game_project_id
    ).first()
    if not blueprint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blueprint not found or not owned by this project."
        )
    blueprint.status = "approved"
    db.commit()
    db.refresh(blueprint)
    return blueprint

@router.get("/{blueprint_id}/export", response_model=BlueprintExportResponse)
def export_blueprint(
    blueprint_id: UUID,
    db: Session = Depends(get_db),
    game_project_id: str = Depends(get_game_project_id)
):
    """Exports the blueprint's flat configuration payload for Unity runtime consumption."""
    blueprint = db.query(GameBlueprint).filter(
        GameBlueprint.id == blueprint_id,
        GameBlueprint.game_project_id == game_project_id
    ).first()
    if not blueprint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blueprint not found or not owned by this project."
        )
    return {
        "api_version": "1.0",
        "blueprint_id": blueprint.id,
        "game_project_id": game_project_id,
        "exported_at": datetime.utcnow(),
        "runtime_data": blueprint.unity_runtime_preview.get("content", {})
    }

@router.post("/{blueprint_id}/materialize", response_model=MaterializationReportResponse)
def materialize_blueprint(
    blueprint_id: UUID,
    db: Session = Depends(get_db),
    game_project_id: str = Depends(get_game_project_id),
    materializer_service: BlueprintMaterializerService = Depends(get_materializer_service)
):
    """Materializes an approved blueprint into active database records (NPCs, quests, flags)."""
    return materializer_service.materialize_blueprint(db, blueprint_id, game_project_id)

@router.get("/{blueprint_id}/runtime-bundle", response_model=BlueprintRuntimeBundleResponse)
def get_runtime_bundle(
    blueprint_id: UUID,
    db: Session = Depends(get_db),
    game_project_id: str = Depends(get_game_project_id),
    materializer_service: BlueprintMaterializerService = Depends(get_materializer_service)
):
    """Returns the consolidated, manifest-linked game configuration bundle for Unity."""
    return materializer_service.get_runtime_bundle(db, blueprint_id, game_project_id)
