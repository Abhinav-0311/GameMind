import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.document import Document
from app.schemas import QueryRequest, QueryResponse
from app.services.rag_service import RAGService
from app.dependencies import get_game_project_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/query", tags=["query"])

def get_rag_service():
    return RAGService()


def _latest_document_ids(documents: list[Document]) -> set[str]:
    latest_by_source: dict[str, Document] = {}
    for document in documents:
        source_id = str(document.source_document_id or document.id)
        if source_id not in latest_by_source or document.revision_number > latest_by_source[source_id].revision_number:
            latest_by_source[source_id] = document
    return {str(document.id) for document in latest_by_source.values()}

@router.post("/", response_model=QueryResponse)
def query_lore(
    request: QueryRequest,
    rag_service: RAGService = Depends(get_rag_service),
    db: Session = Depends(get_db),
    game_project_id: str = Depends(get_game_project_id)
):
    """Query the local lore index for grounded matches scoped by project."""
    # Chroma unavailable -> return 503 with "Vector index unavailable"
    if not rag_service.chroma_client or not rag_service.collection:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Vector index unavailable"
        )
    
    try:
        documents = db.query(Document).filter(Document.game_project_id == game_project_id).all()
        allowed_document_ids = None if request.include_history else _latest_document_ids(documents)
        results = rag_service.query_lore(
            query_text=request.query,
            limit=request.limit or 5,
            game_project_id=game_project_id,
            document_ids=list(allowed_document_ids) if allowed_document_ids is not None else None,
            overfetch=True,
        )
        documents_by_id = {str(document.id): document for document in documents}
        deduplicated_results = []
        seen = set()
        for result in results:
            document = documents_by_id.get(str(result.get("document_id")))
            if document is None:
                continue
            source_id = str(document.source_document_id or document.id)
            content_key = " ".join(str(result.get("content") or "").split()).casefold()
            key = (source_id, content_key)
            if key in seen:
                continue
            seen.add(key)
            deduplicated_results.append({
                **result,
                "source_document_id": source_id,
                "revision_number": document.revision_number,
            })
            if len(deduplicated_results) == (request.limit or 5):
                break
        results = deduplicated_results
        
        message = None
        if not results:
            message = "No matching lore fragments found. Ensure documents are uploaded."
        else:
            message = "Retrieved matches from source history." if request.include_history else "Retrieved matches from the latest source revisions."

        return {
            "query": request.query,
            "results": results,
            "message": message
        }
    except Exception as e:
        logger.error(f"Error querying lore: {e}")
        # Only return Chroma unavailable errors when query/index access truly cannot work
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Vector index unavailable"
        )
