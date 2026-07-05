from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.documents import router as documents_router
from app.api.v1.query import router as query_router
from app.api.v1.npcs import router as npcs_router
from app.api.v1.dialogue import router as dialogue_router
from app.api.v1.graph import router as graph_router
from app.api.v1.memories import router as memories_router
from app.api.v1.quests import router as quests_router
from app.api.v1.relationships import router as relationships_router
from app.api.v1.world_state import router as world_state_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.conversations import router as conversations_router
from app.api.v1.narrative import router as narrative_router
from app.api.v1.hints import router as hints_router
from app.api.v1.blueprints import router as blueprints_router
from app.config import settings
import logging

# Setup standard logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gamemind")

from contextlib import asynccontextmanager
import asyncio
from app.workers.cleanup_worker import cleanup_worker_loop

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic: Start cleanup worker loop in the background
    logger.info("Starting background cleanup worker task inside lifespan context...")
    stop_event = asyncio.Event()
    app.state.cleanup_stop_event = stop_event
    task = asyncio.create_task(cleanup_worker_loop(stop_event))
    app.state.cleanup_task = task
    
    # Run backfill/reindex for existing DocumentChunk rows into local collection
    try:
        from app.database import SessionLocal
        from app.services.rag_service import RAGService
        
        logger.info("Running startup local collection backfill...")
        db = SessionLocal()
        rag = RAGService()
        rag.backfill_local_collection(db)
        db.close()
    except Exception as be:
        logger.error(f"Startup vector database backfill failed: {be}")

    yield
    # Shutdown logic: Set stop_event and wait for graceful cleanup
    logger.info("Stopping background cleanup worker task inside lifespan context...")
    stop_event.set()
    try:
        await asyncio.wait_for(task, timeout=5.0)
        logger.info("Cleanup worker stopped successfully.")
    except asyncio.TimeoutError:
        logger.error("Cleanup worker shutdown timed out.")
    except Exception as shutdown_err:
        logger.error(f"Error during cleanup worker shutdown: {shutdown_err}")

app = FastAPI(
    title="GameMind Narrative API",
    description="Backend AI narrative database and RAG engine.",
    version="1.0.0",
    lifespan=lifespan
)


# Enable CORS so the Next.js frontend can query this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for production deployments
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register endpoints under /api/v1
app.include_router(documents_router, prefix="/api/v1")
app.include_router(query_router, prefix="/api/v1")
app.include_router(npcs_router, prefix="/api/v1")
app.include_router(dialogue_router, prefix="/api/v1")
app.include_router(graph_router, prefix="/api/v1")
app.include_router(memories_router, prefix="/api/v1")
app.include_router(quests_router, prefix="/api/v1")
app.include_router(relationships_router, prefix="/api/v1")
app.include_router(world_state_router, prefix="/api/v1")
app.include_router(analytics_router, prefix="/api/v1")
app.include_router(conversations_router, prefix="/api/v1")
app.include_router(narrative_router, prefix="/api/v1")
app.include_router(hints_router, prefix="/api/v1")
app.include_router(blueprints_router, prefix="/api/v1")


@app.get("/health")
def health_check():
    """Verify backend, database connection, ChromaDB connection, and local AI mode."""
    db_status = "unhealthy"
    try:
        from sqlalchemy import text
        from app.database import SessionLocal
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        db_status = "healthy"
    except Exception as e:
        logger.error(f"Database health verification failed: {e}")

    chroma_status = "unhealthy"
    try:
        from app.services.rag_service import RAGService
        rag = RAGService()
        if rag.chroma_client:
            # Try to list or get collections to verify active connection
            if rag.collection is not None:
                chroma_status = "healthy"
    except Exception as e:
        logger.error(f"ChromaDB connection verification failed: {e}")

    return {
        "status": "healthy" if db_status == "healthy" and chroma_status == "healthy" else "degraded",
        "database": db_status,
        "chromadb": chroma_status,
        "ai_mode": "local_demo",
        "llm_provider": settings.LLM_PROVIDER,
        "embedding_provider": "chroma_default",
        "vector_collection": "lore_chunks_local",
        "vector_dimension": 384
    }
