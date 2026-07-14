from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List
from datetime import datetime

from app.database import get_db
from app.dependencies import get_game_project_id
from app.schemas import (
    BlueprintGenerateRequest, BlueprintResponse, BlueprintExportResponse,
    BlueprintComparisonResponse, BlueprintComparisonSection, BlueprintReadinessResponse,
    BlueprintCitationResponse, BlueprintProvenanceResponse, BlueprintSectionProvenanceResponse,
    MaterializationReportResponse, MaterializeBlueprintRequest,
    BlueprintRuntimeBundleResponse
)
from app.models.blueprint import GameBlueprint
from app.models.document import Document, DocumentChunk
from app.services.blueprint_service import BlueprintService
from app.services.materializer_service import BlueprintMaterializerService
from app.services.blueprint_readiness import BlueprintReadinessService
from app.services.blueprint_brief_service import BlueprintBriefService

router = APIRouter(prefix="/blueprints", tags=["blueprints"])

def get_blueprint_service():
    return BlueprintService()

def get_materializer_service():
    return BlueprintMaterializerService()

def get_readiness_service():
    return BlueprintReadinessService()


BLUEPRINT_SECTION_FIELDS = (
    ("Game summary", "summary"),
    ("Narrative", "narrative_direction"),
    ("Art style", "art_style_direction"),
    ("NPCs", "npc_archetypes"),
    ("Memory", "npc_memory_design"),
    ("Levels", "level_design_suggestions"),
    ("Gameplay systems", "gameplay_systems"),
    ("Quests", "quest_hooks"),
)

BLUEPRINT_PROVENANCE_FIELDS = (
    ("summary", "Game summary"),
    ("narrative_direction", "Narrative"),
    ("art_style_direction", "Art style"),
    ("npc_archetypes", "NPCs"),
    ("npc_memory_design", "Memory"),
    ("level_design_suggestions", "Levels"),
    ("gameplay_systems", "Gameplay systems"),
    ("quest_hooks", "Quests"),
    ("unity_runtime_preview", "Runtime"),
)

@router.post("/generate", response_model=BlueprintResponse, status_code=status.HTTP_201_CREATED)
def generate_blueprint(
    request: BlueprintGenerateRequest,
    db: Session = Depends(get_db),
    game_project_id: str = Depends(get_game_project_id),
    blueprint_service: BlueprintService = Depends(get_blueprint_service)
):
    """Generates a structured game blueprint from an existing GDD document."""
    return blueprint_service.generate_blueprint_from_gdd(
        db,
        request.document_id,
        game_project_id,
        request.supporting_document_ids,
    )

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


@router.get("/{blueprint_id}/brief")
def export_blueprint_brief(
    blueprint_id: UUID,
    db: Session = Depends(get_db),
    game_project_id: str = Depends(get_game_project_id),
):
    """Export a portable Markdown brief containing source evidence and design decisions."""
    blueprint = db.query(GameBlueprint).filter(
        GameBlueprint.id == blueprint_id,
        GameBlueprint.game_project_id == game_project_id,
    ).first()
    if not blueprint:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blueprint not found or not owned by this project.")

    safe_name = "".join(character if character.isalnum() else "-" for character in blueprint.title.lower()).strip("-")[:80]
    return Response(
        content=BlueprintBriefService().build(db, blueprint, game_project_id),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{safe_name or "gamemind-brief"}.md"'},
    )

@router.get("/runtime/latest-bundle", response_model=BlueprintRuntimeBundleResponse)
def get_latest_runtime_bundle(
    db: Session = Depends(get_db),
    game_project_id: str = Depends(get_game_project_id),
    materializer_service: BlueprintMaterializerService = Depends(get_materializer_service)
):
    """Returns the newest materialized blueprint bundle for Unity demo scenes."""
    candidate_blueprints = db.query(GameBlueprint).filter(
        GameBlueprint.game_project_id == game_project_id
    ).order_by(GameBlueprint.updated_at.desc()).all()

    blueprint = next(
        (
            candidate
            for candidate in candidate_blueprints
            if isinstance(candidate.materialization_manifest, dict)
            and candidate.materialization_manifest.get("last_materialized_at")
        ),
        None
    )

    if not blueprint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No materialized blueprint found for this project."
        )

    return materializer_service.get_runtime_bundle(db, blueprint.id, game_project_id)

@router.get("/{blueprint_id}/readiness", response_model=BlueprintReadinessResponse)
def get_blueprint_readiness(
    blueprint_id: UUID,
    db: Session = Depends(get_db),
    game_project_id: str = Depends(get_game_project_id),
    readiness_service: BlueprintReadinessService = Depends(get_readiness_service),
):
    """Report whether source evidence is sufficient for a complete runtime bundle."""
    blueprint = db.query(GameBlueprint).filter(
        GameBlueprint.id == blueprint_id,
        GameBlueprint.game_project_id == game_project_id,
    ).first()
    if not blueprint:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blueprint not found or not owned by this project.")
    return readiness_service.assess(blueprint)


@router.get("/{blueprint_id}/provenance", response_model=BlueprintProvenanceResponse)
def get_blueprint_provenance(
    blueprint_id: UUID,
    db: Session = Depends(get_db),
    game_project_id: str = Depends(get_game_project_id),
):
    """Resolve section citation IDs to source document titles, revisions, and chunks."""
    blueprint = db.query(GameBlueprint).filter(
        GameBlueprint.id == blueprint_id,
        GameBlueprint.game_project_id == game_project_id,
    ).first()
    if not blueprint:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blueprint not found or not owned by this project.")

    citation_ids = set()
    section_citations = {}
    for field, _label in BLUEPRINT_PROVENANCE_FIELDS:
        section = getattr(blueprint, field) or {}
        citations = section.get("citations", []) if isinstance(section, dict) else []
        section_citations[field] = [str(citation) for citation in citations]
        citation_ids.update(section_citations[field])

    parsed_citation_ids = [UUID(citation) for citation in citation_ids]
    rows = []
    if parsed_citation_ids:
        rows = db.query(DocumentChunk, Document).join(
            Document, DocumentChunk.document_id == Document.id
        ).filter(
            DocumentChunk.id.in_(parsed_citation_ids),
            Document.game_project_id == game_project_id,
        ).all()
    by_chunk_id = {
        str(chunk.id): BlueprintCitationResponse(
            chunk_id=chunk.id,
            document_id=document.id,
            document_title=document.title,
            revision_number=document.revision_number,
            chunk_index=chunk.chunk_index,
        )
        for chunk, document in rows
    }

    return BlueprintProvenanceResponse(
        blueprint_id=blueprint.id,
        sections=[
            BlueprintSectionProvenanceResponse(
                section=field,
                citations=[
                    by_chunk_id[citation]
                    for citation in section_citations[field]
                    if citation in by_chunk_id
                ],
            )
            for field, _label in BLUEPRINT_PROVENANCE_FIELDS
        ],
    )


@router.get("/{blueprint_id}/compare/{revised_blueprint_id}", response_model=BlueprintComparisonResponse)
def compare_blueprints(
    blueprint_id: UUID,
    revised_blueprint_id: UUID,
    db: Session = Depends(get_db),
    game_project_id: str = Depends(get_game_project_id),
):
    """Compare immutable blueprint snapshots from the same project at a reviewable section level."""
    blueprints = db.query(GameBlueprint).filter(
        GameBlueprint.id.in_([blueprint_id, revised_blueprint_id]),
        GameBlueprint.game_project_id == game_project_id,
    ).all()
    by_id = {blueprint.id: blueprint for blueprint in blueprints}
    base = by_id.get(blueprint_id)
    revised = by_id.get(revised_blueprint_id)
    if not base or not revised:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Both blueprints must belong to the active project.")

    changed_sections = []
    for label, field in BLUEPRINT_SECTION_FIELDS:
        before = getattr(base, field) or {}
        after = getattr(revised, field) or {}
        before_content = before.get("content", {}) if isinstance(before, dict) else {}
        after_content = after.get("content", {}) if isinstance(after, dict) else {}
        if before_content == after_content:
            continue
        before_warnings = len(before.get("warnings", [])) if isinstance(before, dict) else 0
        after_warnings = len(after.get("warnings", [])) if isinstance(after, dict) else 0
        changed_sections.append(BlueprintComparisonSection(
            section=label,
            status="changed",
            before_warnings=before_warnings,
            after_warnings=after_warnings,
        ))

    return BlueprintComparisonResponse(
        base_blueprint_id=base.id,
        revised_blueprint_id=revised.id,
        changed_sections=changed_sections,
    )


@router.post("/{blueprint_id}/materialize", response_model=MaterializationReportResponse)
def materialize_blueprint(
    blueprint_id: UUID,
    request: MaterializeBlueprintRequest = MaterializeBlueprintRequest(),
    db: Session = Depends(get_db),
    game_project_id: str = Depends(get_game_project_id),
    materializer_service: BlueprintMaterializerService = Depends(get_materializer_service),
    readiness_service: BlueprintReadinessService = Depends(get_readiness_service),
):
    """Materializes an approved blueprint into active database records (NPCs, quests, flags)."""
    blueprint = db.query(GameBlueprint).filter(
        GameBlueprint.id == blueprint_id,
        GameBlueprint.game_project_id == game_project_id,
    ).first()
    if not blueprint:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blueprint not found or not owned by this project.")

    readiness = readiness_service.assess(blueprint)
    if not readiness["can_materialize"] and not request.confirm_incomplete:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Runtime materialization needs explicit confirmation because required source evidence is missing.",
                "readiness": readiness,
            },
        )
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
