from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas import DocumentResponse, DocumentDetailResponse, SourceKindUpdate
from app.models.document import Document, DocumentChunk
from app.services.rag_service import DuplicateDocumentError, RAGService
from app.dependencies import get_game_project_id
import uuid
from typing import List

router = APIRouter(prefix="/documents", tags=["documents"])

def get_rag_service():
    return RAGService()

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
SOURCE_KINDS = {"gdd", "lore", "npc_sheet", "quest_brief", "level_brief", "technical_brief", "general"}
DEMO_FROSTPEAK_FILE_NAME = "sample_gdd_frostpeak.md"
DEMO_FROSTPEAK_PATH = Path(__file__).resolve().parents[3] / "docs" / "demo" / DEMO_FROSTPEAK_FILE_NAME

@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
def upload_document(
    file: UploadFile = File(...),
    source_kind: str | None = Form(default=None),
    db: Session = Depends(get_db),
    rag_service: RAGService = Depends(get_rag_service),
    game_project_id: str = Depends(get_game_project_id)
):
    """Upload a document (.txt, .md, .pdf) to extract text, chunk, embed, and store in PG and ChromaDB."""
    if source_kind is not None and source_kind not in SOURCE_KINDS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported source kind.")
    try:
        content_bytes = file.file.read()
        if len(content_bytes) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File size exceeds the maximum limit of 5 MB."
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"Failed to read uploaded file: {e}"
        )

    try:
        return rag_service.process_document(
            db=db,
            file_name=file.filename,
            file_bytes=content_bytes,
            content_type=file.content_type or "text/plain",
            game_project_id=game_project_id,
            reject_duplicate=True,
            source_kind=source_kind,
        )
    except DuplicateDocumentError as duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f'{duplicate} Select the existing source from the library or upload a changed revision.'
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))
    except Exception as error:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Document processing failed: {error}")


@router.post("/{document_id}/revision", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
def upload_document_revision(
    document_id: uuid.UUID,
    file: UploadFile = File(...),
    source_kind: str | None = Form(default=None),
    db: Session = Depends(get_db),
    rag_service: RAGService = Depends(get_rag_service),
    game_project_id: str = Depends(get_game_project_id),
):
    """Add a revised source file while preserving the original citation history."""
    if source_kind is not None and source_kind not in SOURCE_KINDS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported source kind.")
    source_document = db.query(Document).filter(
        Document.id == document_id,
        Document.game_project_id == game_project_id,
    ).first()
    if not source_document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source document not found.")

    content_bytes = file.file.read()
    if len(content_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File size exceeds the maximum limit of 5 MB.")

    try:
        return rag_service.process_document(
            db=db,
            file_name=file.filename,
            file_bytes=content_bytes,
            content_type=file.content_type or "text/plain",
            game_project_id=game_project_id,
            reject_duplicate=True,
            source_document=source_document,
            source_kind=source_kind,
        )
    except DuplicateDocumentError as duplicate:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"{duplicate} Upload a changed source file for a new revision.")
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))
    except Exception as error:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Document revision processing failed: {error}")

@router.post("/demo/frostpeak", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
def load_frostpeak_demo_document(
    db: Session = Depends(get_db),
    rag_service: RAGService = Depends(get_rag_service),
    game_project_id: str = Depends(get_game_project_id)
):
    """Load the bundled Frostpeak sample GDD for the local zero-cost demo path."""
    existing_doc = db.query(Document).filter(
        Document.title == DEMO_FROSTPEAK_FILE_NAME,
        Document.game_project_id == game_project_id
    ).first()
    if existing_doc:
        return existing_doc

    if not DEMO_FROSTPEAK_PATH.exists():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Bundled Frostpeak demo document is missing from the backend."
        )

    try:
        return rag_service.process_document(
            db=db,
            file_name=DEMO_FROSTPEAK_FILE_NAME,
            file_bytes=DEMO_FROSTPEAK_PATH.read_bytes(),
            content_type="text/markdown",
            game_project_id=game_project_id
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while loading the Frostpeak demo: {e}"
        )

@router.get("/", response_model=List[DocumentResponse])
def get_documents(
    db: Session = Depends(get_db),
    game_project_id: str = Depends(get_game_project_id)
):
    """Retrieve all documents metadata."""
    return db.query(Document).filter(Document.game_project_id == game_project_id).order_by(Document.created_at.desc()).all()

@router.get("/{document_id}", response_model=DocumentDetailResponse)
def get_document(
    document_id: uuid.UUID, 
    db: Session = Depends(get_db),
    game_project_id: str = Depends(get_game_project_id)
):
    """Retrieve a single document, including all of its generated chunks."""
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.game_project_id == game_project_id
    ).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Document not found"
        )
    
    # Retrieve chunks ordered by chunk index
    chunks = db.query(DocumentChunk)\
               .filter(DocumentChunk.document_id == document_id)\
               .order_by(DocumentChunk.chunk_index)\
               .all()
    
    return {
        "id": doc.id,
        "title": doc.title,
        "content_type": doc.content_type,
        "source_kind": doc.source_kind,
        "source_document_id": doc.source_document_id,
        "revision_number": doc.revision_number,
        "created_at": doc.created_at,
        "updated_at": doc.updated_at,
        "chunks_count": len(chunks),
        "chunks": chunks
    }


@router.put("/{document_id}/source-kind", response_model=DocumentResponse)
def update_source_kind(
    document_id: uuid.UUID,
    request: SourceKindUpdate,
    db: Session = Depends(get_db),
    game_project_id: str = Depends(get_game_project_id),
):
    """Set the developer-confirmed role of a source without changing its contents."""
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.game_project_id == game_project_id,
    ).first()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source document not found.")
    document.source_kind = request.source_kind
    db.commit()
    db.refresh(document)
    return document

@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    rag_service: RAGService = Depends(get_rag_service),
    game_project_id: str = Depends(get_game_project_id)
):
    """Delete a document, cascade deleting database chunks, and clean up ChromaDB vectors."""
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.game_project_id == game_project_id
    ).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Document not found"
        )
    
    # Delete from ChromaDB vector index
    try:
        if rag_service.collection:
            # Delete vectors associated with this document ID metadata
            rag_service.collection.delete(where={"document_id": str(document_id)})
    except Exception as e:
        # Log error, but proceed with DB delete to avoid mismatch if Chroma is out of sync
        print(f"Error deleting from ChromaDB: {e}")
        
    # Delete from DB (cascade deletes chunks automatically)
    db.delete(doc)
    db.commit()
    return
