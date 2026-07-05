import pytest
import uuid
import datetime
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.graph import WorldEntity, WorldEntityVersion, WorldRelationship, PendingIngest, ConsistencyOverride
from app.models.npc import NPCProfile
from app.models.memory import NPCMemory
from app.repositories.graph_repository import graph_repo
from app.services.graph_validation import GraphValidationService, ValidationError
from app.services.contradiction_engine import contradiction_engine
from app.services.memory_service import MemoryService
from app.services.rag_service import RAGService

@pytest.fixture(scope="function")
def db():
    db_session = SessionLocal()
    try:
        yield db_session
    finally:
        db_session.rollback()
        # Cleanup all created entities and tables
        db_session.query(ConsistencyOverride).delete()
        db_session.query(PendingIngest).delete()
        db_session.query(WorldRelationship).delete()
        db_session.query(WorldEntityVersion).delete()
        db_session.query(WorldEntity).delete()
        db_session.query(NPCMemory).delete()
        db_session.query(NPCProfile).delete()
        db_session.commit()
        db_session.close()

def test_lock_ordering_works(db):
    """Verify that lock ordering locks entities lexicographically by slug."""
    slug_z = f"slug_z_{uuid.uuid4().hex[:6]}"
    slug_a = f"slug_a_{uuid.uuid4().hex[:6]}"
    
    graph_repo.create_entity(db, slug_z, "faction", "Faction Z", "Z")
    graph_repo.create_entity(db, slug_a, "faction", "Faction A", "A")
    
    # Try calling GraphRepository._lock_entities_ordered
    locked = graph_repo._lock_entities_ordered([slug_z, slug_a], db=db)
    assert len(locked) == 2
    # Ensure they are sorted lexicographically (A first, then Z)
    assert locked[0].slug == slug_a
    assert locked[1].slug == slug_z


def test_contradictions_blocked_and_stored_in_pending(db):
    """Verify that contradictory relationships are blocked and logged in pending ingests."""
    slug_u = f"char_u_{uuid.uuid4().hex[:6]}"
    slug_v = f"char_v_{uuid.uuid4().hex[:6]}"
    
    # 1. Create allowed taxonomy rules first (safely checking existence)
    from app.models.graph import RelationshipTypeRule
    rule1 = db.query(RelationshipTypeRule).filter_by(rel_type="allied_with", allowed_source_type="character", allowed_target_type="character").first()
    if not rule1:
        rule1 = RelationshipTypeRule(rel_type="allied_with", allowed_source_type="character", allowed_target_type="character")
        db.add(rule1)
    rule2 = db.query(RelationshipTypeRule).filter_by(rel_type="at_war_with", allowed_source_type="character", allowed_target_type="character").first()
    if not rule2:
        rule2 = RelationshipTypeRule(rel_type="at_war_with", allowed_source_type="character", allowed_target_type="character")
        db.add(rule2)
    db.commit()

    # 2. Create entities
    graph_repo.create_entity(db, slug_u, "character", "Hero U", "U")
    graph_repo.create_entity(db, slug_v, "character", "Hero V", "V")
    
    # 3. Create active 'allied_with' relationship using validation service
    val_service = GraphValidationService(db)
    val_service.validate_and_create_relationship(slug_u, slug_v, "allied_with")
    
    # 4. Attempt to create contradictory 'at_war_with' relationship
    with pytest.raises(ValidationError) as excinfo:
        val_service.validate_and_create_relationship(slug_u, slug_v, "at_war_with")
    
    # Check that error states the contradiction reason
    assert "Contradiction detected" in excinfo.value.message
    
    # Verify it is saved in pending ingests
    pending = db.query(PendingIngest).filter(PendingIngest.validation_id == excinfo.value.validation_id).first()
    assert pending is not None
    assert pending.payload["rel_type"] == "at_war_with"
    assert "Contradiction detected" in pending.reason_blocked


def test_override_bypasses_contradiction(db):
    """Verify administrative override bypasses contradiction and applies the relationship."""
    slug_u = f"char_x_{uuid.uuid4().hex[:6]}"
    slug_v = f"char_y_{uuid.uuid4().hex[:6]}"
    
    # Create allowed rules
    from app.models.graph import RelationshipTypeRule
    rule1 = db.query(RelationshipTypeRule).filter_by(rel_type="allied_with", allowed_source_type="character", allowed_target_type="character").first()
    if not rule1:
        rule1 = RelationshipTypeRule(rel_type="allied_with", allowed_source_type="character", allowed_target_type="character")
        db.add(rule1)
    rule2 = db.query(RelationshipTypeRule).filter_by(rel_type="at_war_with", allowed_source_type="character", allowed_target_type="character").first()
    if not rule2:
        rule2 = RelationshipTypeRule(rel_type="at_war_with", allowed_source_type="character", allowed_target_type="character")
        db.add(rule2)
    db.commit()

    # Create entities
    graph_repo.create_entity(db, slug_u, "character", "Hero X", "X")
    graph_repo.create_entity(db, slug_v, "character", "Hero Y", "Y")
    
    val_service = GraphValidationService(db)
    val_service.validate_and_create_relationship(slug_u, slug_v, "allied_with")
    
    # Attempt contradictory relation (will be blocked and stored in pending_ingests)
    validation_id = None
    try:
        val_service.validate_and_create_relationship(slug_u, slug_v, "at_war_with")
    except ValidationError as e:
        validation_id = e.validation_id
        
    assert validation_id is not None
    
    # Apply override
    res = val_service.apply_override(validation_id, applied_by="governor_auditor", reason="Approved for narrative development.")
    assert res is True
    
    # Verify both active relationships exist in DB now (contradiction bypassed)
    active_allied = graph_repo.get_active_relationship(db, slug_u, slug_v, "allied_with")
    active_war = graph_repo.get_active_relationship(db, slug_u, slug_v, "at_war_with")
    assert active_allied is not None
    assert active_war is not None
    
    # Verify pending ingest is deleted
    pending = db.query(PendingIngest).filter(PendingIngest.validation_id == validation_id).first()
    assert pending is None


def test_historical_graph_state_no_contradiction(db):
    """Verify that historical relationships (valid_to is not null) do not trigger active contradictions."""
    slug_u = f"char_m_{uuid.uuid4().hex[:6]}"
    slug_v = f"char_n_{uuid.uuid4().hex[:6]}"
    
    # Create entities
    graph_repo.create_entity(db, slug_u, "character", "Hero M", "M")
    graph_repo.create_entity(db, slug_v, "character", "Hero N", "N")
    
    # Create relationship
    rel = graph_repo.create_relationship(db, slug_u, slug_v, "allied_with")
    
    # Soft-delete the relationship to make it historical
    graph_repo.delete_relationship(db, slug_u, slug_v, "allied_with")
    
    # Validate and create 'at_war_with' should succeed now because 'allied_with' is historical
    val_service = GraphValidationService(db)
    new_rel = val_service.validate_and_create_relationship(slug_u, slug_v, "at_war_with")
    assert new_rel is not None
    assert new_rel.rel_type == "at_war_with"


def test_graph_aware_memory_boosting_unit(db):
    """Unit test: Verify that memories referencing adjacent graph slugs receive score boosts and rank higher, with mocked vector results."""
    # 1. Create NPC and neighbor entities in world graph
    npc_slug = f"npc_mystic_unit_{uuid.uuid4().hex[:6]}"
    friend_slug = f"friend_slug_unit_{uuid.uuid4().hex[:6]}"
    other_slug = f"other_slug_unit_{uuid.uuid4().hex[:6]}"
    
    # NPC
    npc_profile = NPCProfile(slug=npc_slug, name="Mystic", personality_summary="A mystic.")
    db.add(npc_profile)
    db.commit()
    
    # Faction entities
    graph_repo.create_entity(db, npc_slug, "character", "Mystic NPC", "A mystic character", importance_score=50)
    graph_repo.create_entity(db, friend_slug, "character", "Friend", "NPC's friend", importance_score=50)
    graph_repo.create_entity(db, other_slug, "character", "Other", "Unrelated character", importance_score=50)
    
    # Graph: NPC --(allied_with)--> Friend
    graph_repo.create_relationship(db, npc_slug, friend_slug, "allied_with")
    
    # 2. Mock MemoryService vector retrieval through Chroma's collection boundary
    rag = RAGService()
    mem_service = MemoryService(rag)
    
    # Seed memories in Postgres (leaving chroma_indexed=False since we mock Chroma)
    m1 = NPCMemory(
        npc_id=npc_profile.id,
        memory_text=f"Mystic fought with {other_slug}.",
        memory_type="episodic",
        importance_score=5.0,
        chroma_indexed=False
    )
    m2 = NPCMemory(
        npc_id=npc_profile.id,
        memory_text=f"Mystic fought with {friend_slug}.",
        memory_type="episodic",
        importance_score=5.0,
        chroma_indexed=False
    )
    db.add(m1)
    db.add(m2)
    db.commit()
    
    # 3. Mock the Chroma collection count and query calls to return results
    class MockCollection:
        def count(self):
            return 2
        def query(self, query_texts, where, n_results):
            # Return m1 first, then m2, to verify that score boosting re-ranks m2 above m1
            return {
                "ids": [[str(m1.id), str(m2.id)]],
                "distances": [[0.5, 0.5]]
            }
            
    mem_service.memory_collection = MockCollection()
    
    # Retrieve memories and verify ranking changes.
    # Since they both have similarity and importance parameters, Memory 2 should rank higher
    # because 'friend_slug' is an adjacent entity in the graph (boost of +0.3 applied).
    retrieved = mem_service.retrieve_memories(db, npc_profile.id, "Who did you fight with?", limit=5)
    
    lines = retrieved.splitlines()
    assert len(lines) >= 2
    # Ensure Memory 2 (containing friend_slug) is sorted first despite vector database returning m1 first
    assert friend_slug in lines[0]
    assert other_slug in lines[1]


def test_graph_aware_memory_boosting_integration(db):
    """Integration test: Verify query clamping and Chroma retrieval using a unique isolated collection name."""
    npc_slug = f"npc_mystic_int_{uuid.uuid4().hex[:6]}"
    friend_slug = f"friend_slug_int_{uuid.uuid4().hex[:6]}"
    
    npc_profile = NPCProfile(slug=npc_slug, name="Mystic Integration", personality_summary="A mystic.")
    db.add(npc_profile)
    db.commit()
    
    rag = RAGService()
    mem_service = MemoryService(rag)
    
    # Create isolated collection name for this test run
    unique_col_name = f"npc_memories_test_{uuid.uuid4().hex[:8]}"
    try:
        mem_service.memory_collection = rag.chroma_client.get_or_create_collection(
            name=unique_col_name,
            metadata={"hnsw:space": "cosine"}
        )
    except Exception as e:
        pytest.skip(f"ChromaDB connection unavailable, skipping integration test: {e}")
        
    try:
        # Seed exactly two memories into vector database
        m1 = mem_service.create_memory(
            db=db,
            npc_id=npc_profile.id,
            memory_text=f"Mystic fought with {friend_slug}.",
            importance_score=5.0
        )
        
        # Verify collection count is exactly 1
        assert mem_service.memory_collection.count() == 1
        
        # Retrieve memories with a limit of 5 (which normally requests 10 results from HNSW)
        # Clamping must reduce query limit to 1 and prevent contiguous array crash
        retrieved = mem_service.retrieve_memories(db, npc_profile.id, "Who did you fight with?", limit=5)
        
        assert "No relevant memories." not in retrieved
        assert friend_slug in retrieved
        
    finally:
        # Teardown: Delete the isolated collection
        try:
            rag.chroma_client.delete_collection(unique_col_name)
        except Exception:
            pass
