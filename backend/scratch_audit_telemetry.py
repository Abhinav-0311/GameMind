import logging
import json
import uuid
import sys
import math
from app.database import SessionLocal
from app.models.graph import WorldEntity, WorldEntityVersion, WorldRelationship, RelationshipTypeRule
from app.models.npc import NPCProfile
from app.models.memory import NPCMemory
from app.repositories.graph_repository import graph_repo
from app.services.memory_service import MemoryService
from app.services.gemini_service import GeminiService
from app.services.rag_service import RAGService

# Create a custom log handler to intercept metrics in memory
class TelemetryInterceptor(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        try:
            self.records.append(json.loads(record.getMessage()))
        except Exception:
            pass

def simulate_memory_retrieval_and_boosting():
    db = SessionLocal()
    interceptor = TelemetryInterceptor()
    
    # Attach interceptor to llm_telemetry_logs logger
    telemetry_logger = logging.getLogger("llm_telemetry_logs")
    telemetry_logger.setLevel(logging.INFO)
    telemetry_logger.addHandler(interceptor)
    
    try:
        print("=== TELEMETRY RUNTIME AUDIT ===")
        # Seed test data
        npc_slug = f"audit_npc_{uuid.uuid4().hex[:6]}"
        friend_slug = f"audit_friend_{uuid.uuid4().hex[:6]}"
        other_slug = f"audit_other_{uuid.uuid4().hex[:6]}"
        
        npc = NPCProfile(slug=npc_slug, name="Audit NPC", personality_summary="Telemetry auditor.")
        db.add(npc)
        db.commit()
        db.refresh(npc)
        
        # World graph setup
        graph_repo.create_entity(db, npc_slug, "character", "Audit NPC", "Auditor")
        graph_repo.create_entity(db, friend_slug, "character", "Friend NPC", "Friend")
        graph_repo.create_entity(db, other_slug, "character", "Unrelated NPC", "Other")
        
        # Connect NPC to friend (allied_with)
        graph_repo.create_relationship(db, npc_slug, friend_slug, "allied_with")
        
        # RAG / Memory setup
        gemini = GeminiService()
        gemini.is_available = lambda: True
        # Standard mockup vector
        gemini.generate_embedding = lambda text: [0.1] * 768
        
        rag = RAGService(gemini)
        mem_service = MemoryService(gemini, rag)
        mem_service._init_memory_collection()
        
        # Add memories: m1 has no adjacent slugs, m2 contains the adjacent friend_slug
        m1 = mem_service.create_memory(
            db=db,
            npc_id=npc.id,
            memory_text=f"Encountered {other_slug} at the gate.",
            importance_score=5.0
        )
        m2 = mem_service.create_memory(
            db=db,
            npc_id=npc.id,
            memory_text=f"Encountered {friend_slug} at the market.",
            importance_score=5.0
        )
        
        # Retrieve memories
        print("Retrieving memories to trigger graph-aware boosting...")
        results = mem_service.retrieve_memories(db, npc.id, "Where did you go?", limit=5)
        print("Retrieved output:")
        print(results)
        
        # Inspect captured telemetry
        print("\nCaptured Telemetry Records:")
        boosts_total_records = [r for r in interceptor.records if r.get("metric") == "graph_memory_boosts_total"]
        duration_records = [r for r in interceptor.records if r.get("metric") == "graph_memory_boost_duration_seconds"]
        
        print(f"Total graph_memory_boosts_total metrics count: {len(boosts_total_records)}")
        for r in boosts_total_records:
            print(f"  - Value: {r.get('value')} | Timestamp: {r.get('timestamp')}")
            
        print(f"Total graph_memory_boost_duration_seconds metrics count: {len(duration_records)}")
        for r in duration_records:
            print(f"  - Value: {r.get('value')} | Timestamp: {r.get('timestamp')}")
            
    finally:
        # Detach interceptor
        telemetry_logger.removeHandler(interceptor)
        # Cleanup seeded data
        db.query(WorldRelationship).delete()
        db.query(WorldEntityVersion).delete()
        db.query(WorldEntity).delete()
        db.query(NPCMemory).delete()
        db.query(NPCProfile).delete()
        db.commit()
        db.close()

if __name__ == "__main__":
    simulate_memory_retrieval_and_boosting()
