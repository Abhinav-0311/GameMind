from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas import DocumentResponse, DocumentDetailResponse
from app.models.document import Document, DocumentChunk
from app.services.gemini_service import GeminiService
from app.services.rag_service import RAGService
from app.dependencies import get_game_project_id
import uuid
from typing import List

router = APIRouter(prefix="/documents", tags=["documents"])

def get_rag_service():
    gemini = GeminiService()
    return RAGService(gemini)

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB

@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    rag_service: RAGService = Depends(get_rag_service),
    game_project_id: str = Depends(get_game_project_id)
):
    """Upload a document (.txt, .md, .pdf) to extract text, chunk, embed, and store in PG and ChromaDB."""
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
        doc = rag_service.process_document(
            db=db,
            file_name=file.filename,
            file_bytes=content_bytes,
            content_type=file.content_type or "text/plain",
            game_project_id=game_project_id
        )
        return doc
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=str(ve)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"An error occurred during document processing: {e}"
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
        "created_at": doc.created_at,
        "updated_at": doc.updated_at,
        "chunks_count": len(chunks),
        "chunks": chunks
    }

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
