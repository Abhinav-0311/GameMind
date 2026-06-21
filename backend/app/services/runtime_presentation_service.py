from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from uuid import UUID

class RuntimePresentationService:
    @staticmethod
    def get_normalized_emotions(emotions: Dict[str, int]) -> Dict[str, float]:
        """Normalizes integer emotions (0-100) to float range (0.0-1.0)."""
        normalized = {}
        for key in ["trust", "fear", "anger", "curiosity", "loyalty"]:
            val = emotions.get(key, 50)
            normalized[key] = float(val) / 100.0
        return normalized

    @staticmethod
    def dominant_emotion(emotions: Dict[str, int]) -> str:
        """Determines the dominant emotion name (highest value). Defaults to 'trust'."""
        if not emotions:
            return "trust"
        
        target_keys = ["trust", "fear", "anger", "curiosity", "loyalty"]
        filtered = {k: v for k, v in emotions.items() if k in target_keys}
        if not filtered:
            return "trust"
            
        # Find the emotion with the maximum value
        return max(filtered, key=filtered.get)

    @staticmethod
    def resolve_animation(dominant: str, animation_hints: Optional[Dict[str, Any]]) -> str:
        """Resolves animation key from NPC's hints, falling back to 'idle' or neutral if unmapped."""
        if not animation_hints:
            return "idle"
        
        # Look up the animation mapped to the dominant emotion
        anim = animation_hints.get(dominant)
        if not anim:
            # Fallback to generic mappings or default idle
            anim = animation_hints.get("default", animation_hints.get("idle", "idle"))
        return anim

    @staticmethod
    def resolve_citations(retrieved_chunks: List[Any], player_message: str, rag_service: Any, game_project_id: str, db: Session) -> List[Dict[str, Any]]:
        """Resolves citations by matching similarities from RAG service query and fetching DB titles."""
        from app.models.document import Document
        
        if not retrieved_chunks:
            return []
            
        similarity_map = {}
        try:
            results = rag_service.query_lore(player_message, limit=10, game_project_id=game_project_id)
            for r in results:
                similarity_map[UUID(r["chunk_id"])] = r["similarity"]
        except Exception:
            pass
            
        citations = []
        for chunk in retrieved_chunks:
            chunk_id = chunk.id
            doc_id = chunk.document_id
            
            doc = db.query(Document).filter(Document.id == doc_id).first()
            title = doc.title if doc else "Lore Document"
            
            sim = similarity_map.get(chunk_id, 0.95)
            
            citations.append({
                "document_id": doc_id,
                "chunk_id": chunk_id,
                "title": title,
                "similarity": sim
            })
        return citations
