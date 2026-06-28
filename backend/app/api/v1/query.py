import logging
from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas import QueryRequest, QueryResponse
from app.services.gemini_service import GeminiService
from app.services.rag_service import RAGService
from app.dependencies import get_game_project_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/query", tags=["query"])

def get_rag_service():
    gemini = GeminiService()
    return RAGService(gemini)

@router.post("/", response_model=QueryResponse)
def query_lore(
    request: QueryRequest,
    rag_service: RAGService = Depends(get_rag_service),
    game_project_id: str = Depends(get_game_project_id)
):
    """Query the vector database (ChromaDB) for semantic matches against uploaded lore scoped by project."""
    # Chroma unavailable -> return 503 with "Vector index unavailable"
    if not rag_service.chroma_client or not rag_service.collection:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Vector index unavailable"
        )
    
    try:
        results = rag_service.query_lore(
            query_text=request.query,
            limit=request.limit or 5,
            game_project_id=game_project_id
        )
        
        message = None
        if not results:
            message = "No matching lore fragments found. Ensure documents are uploaded."
        elif not rag_service.gemini_service.is_available():
            message = "Retrieved matches using Local Demo mode (Chroma local embeddings)."

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
