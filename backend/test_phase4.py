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
from app.services.gemini_service import GeminiService
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


def test_graph_aware_memory_boosting(db):
    """Verify that memories referencing adjacent graph slugs receive score boosts and rank higher."""
    # 1. Create NPC and neighbor entities in world graph
    npc_slug = f"npc_mystic_{uuid.uuid4().hex[:6]}"
    friend_slug = f"friend_slug_{uuid.uuid4().hex[:6]}"
    other_slug = f"other_slug_{uuid.uuid4().hex[:6]}"
    
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
    
    # 2. Add two candidate memories to vector database (mock mode / active database mock client)
    gemini = GeminiService()
    gemini.is_available = lambda: True
    gemini.generate_embedding = lambda text: [0.1] * 768
    rag = RAGService(gemini)
    mem_service = MemoryService(gemini, rag)
    
    # Initialize collection
    mem_service._init_memory_collection()
    
    # Memory 1 (references unrelated slug): "Mystic fought with other_slug."
    # Memory 2 (references adjacent slug): "Mystic fought with friend_slug."
    m1 = mem_service.create_memory(
        db=db,
        npc_id=npc_profile.id,
        memory_text=f"Mystic fought with {other_slug}.",
        importance_score=5.0
    )
    m2 = mem_service.create_memory(
        db=db,
        npc_id=npc_profile.id,
        memory_text=f"Mystic fought with {friend_slug}.",
        importance_score=5.0
    )
    
    # 3. Retrieve memories and verify ranking changes.
    # Since they both have similarity and importance parameters, Memory 2 should rank higher
    # because 'friend_slug' is an adjacent entity in the graph (boost of +0.3 applied).
    retrieved = mem_service.retrieve_memories(db, npc_profile.id, "Who did you fight with?", limit=5)
    
    # Retrieved format is a markdown block of bullet points:
    # - Mystic fought with friend_slug.
    # - Mystic fought with other_slug.
    lines = retrieved.splitlines()
    assert len(lines) >= 2
    # Ensure Memory 2 (containing friend_slug) is listed first!
    assert friend_slug in lines[0]
    assert other_slug in lines[1]
