from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas import QueryRequest, QueryResponse
from app.services.gemini_service import GeminiService
from app.services.rag_service import RAGService

router = APIRouter(prefix="/query", tags=["query"])

def get_rag_service():
    gemini = GeminiService()
    return RAGService(gemini)

@router.post("/", response_model=QueryResponse)
def query_lore(
    request: QueryRequest,
    rag_service: RAGService = Depends(get_rag_service)
):
    """Query the vector database (ChromaDB) for semantic matches against uploaded lore."""
    if not rag_service.gemini_service.is_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gemini Service is not configured. Please supply a valid GEMINI_API_KEY."
        )
    
    try:
        results = rag_service.query_lore(
            query_text=request.query,
            limit=request.limit or 5
        )
        return {
            "query": request.query,
            "results": results
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during query: {e}"
        )
