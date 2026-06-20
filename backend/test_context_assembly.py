import pytest
import uuid
import time
from datetime import datetime
from fastapi.testclient import TestClient
from main import app
from app.database import SessionLocal
from app.models.graph import WorldEntity, WorldEntityVersion, WorldRelationship
from app.repositories.graph_repository import graph_repo
from app.services.graph_cache import graph_cache
from app.services.graph_traversal import graph_traversal_service
from app.services.prompt_fragment import prompt_fragment_service
from app.services.context_assembler import context_assembler_service
from app.models.npc import NPCProfile

client = TestClient(app)

@pytest.fixture(scope="module")
def db():
    db_session = SessionLocal()
    try:
        yield db_session
    finally:
        # Cleanup
        db_session.query(WorldRelationship).delete()
        db_session.query(WorldEntityVersion).delete()
        db_session.query(WorldEntity).delete()
        db_session.query(NPCProfile).delete()
        db_session.commit()
        db_session.close()

def test_prompt_fragment_correctness_and_cache_coherence(db):
    """Gate B & Gate C: Verify fragment identifiers, metadata, version stamps, hit, miss, mismatch rebuild."""
    slug = f"entity_{uuid.uuid4().hex[:6]}"
    ent = graph_repo.create_entity(
        db, slug, "character", "Hero", "A brave fighter.", importance_score=50
    )

    # 1. Compile fragment - first run (Cache Miss)
    fragment = prompt_fragment_service.get_or_create_entity_fragment(db, slug)
    assert fragment["fragment_id"] == f"entity:{slug}:current"
    assert fragment["fragment_type"] == "entity"
    assert fragment["source_entities"] == [slug]
    assert "A brave fighter" in fragment["content"]
    assert fragment["token_estimate"] > 0

    # Verify cached meta and content keys exist in Redis mock
    meta_key = f"graph:fragment_meta:entity:{slug}:current"
    content_key = f"graph:fragment:entity:{slug}:current"
    assert graph_cache.redis.exists(meta_key)
    assert graph_cache.redis.exists(content_key)

    # 2. Get fragment again (Cache Hit)
    fragment2 = prompt_fragment_service.get_or_create_entity_fragment(db, slug)
    assert fragment2 == fragment

    # 3. Mutate entity (Version Stamp increments)
    graph_repo.update_entity(db, slug, description="A seasoned fighter.")
    
    # 4. Get fragment after mutation (Cache Mismatch Rebuild)
    fragment3 = prompt_fragment_service.get_or_create_entity_fragment(db, slug)
    assert "A seasoned fighter" in fragment3["content"]
    assert fragment3["version_stamp"] != fragment["version_stamp"]


def test_context_assembly_pipeline_and_ranking(db):
    """Gate A: Verify context assembly pipeline correctness, ranking, and deduplication."""
    slug_a = f"node_a_{uuid.uuid4().hex[:6]}"
    slug_b = f"node_b_{uuid.uuid4().hex[:6]}"
    slug_c = f"node_c_{uuid.uuid4().hex[:6]}"

    # A has importance 10, B has importance 90, C has importance 40
    graph_repo.create_entity(db, slug_a, "location", "Node A", "Node A info", importance_score=10)
    graph_repo.create_entity(db, slug_b, "location", "Node B", "Node B info", importance_score=90)
    graph_repo.create_entity(db, slug_c, "location", "Node C", "Node C info", importance_score=40)

    # Path: A -> B -> C
    graph_repo.create_relationship(db, slug_a, slug_b, "leads_to")
    graph_repo.create_relationship(db, slug_b, slug_c, "leads_to")

    # BFS results (Path: A -> B)
    bfs_res = graph_traversal_service.traverse(db, slug_a, slug_b, algorithm="bfs")
    
    # Subgraph results (All nodes)
    subgraph_res = graph_traversal_service.get_subgraph(db, seeds=[slug_a, slug_b, slug_c], depth=1)

    # Assemble context
    context = context_assembler_service.assemble_context(
        db=db,
        bfs_results=bfs_res,
        subgraph_results=subgraph_res
    )

    assert "[World Graph Lore Context]" in context
    assert f"Node A ({slug_a})" in context
    assert f"Node B ({slug_b})" in context
    assert f"Node C ({slug_c})" in context

    # Verify ranking:
    # 1. BFS elements first: Node A, then Node B
    # 2. Subgraph elements sorted by importance: Node C (importance 40)
    # So order of entities in text should be A, B, C
    idx_a = context.find(slug_a)
    idx_b = context.find(slug_b)
    idx_c = context.find(slug_c)
    assert idx_a < idx_b
    assert idx_b < idx_c


def test_context_assembly_token_budget(db):
    """Gate D: Verify token budget enforcement and deterministic truncation."""
    slug_1 = f"entity_1_{uuid.uuid4().hex[:6]}"
    slug_2 = f"entity_2_{uuid.uuid4().hex[:6]}"
    slug_3 = f"entity_3_{uuid.uuid4().hex[:6]}"

    # Entity 1 (imp 100), Entity 2 (imp 50), Entity 3 (imp 10)
    graph_repo.create_entity(db, slug_1, "faction", "F1", "F1 description text very long " * 10, importance_score=100)
    graph_repo.create_entity(db, slug_2, "faction", "F2", "F2 description text very long " * 10, importance_score=50)
    graph_repo.create_entity(db, slug_3, "faction", "F3", "F3 description text very long " * 10, importance_score=10)

    subgraph = graph_traversal_service.get_subgraph(db, seeds=[slug_1, slug_2, slug_3], depth=1)

    # Assemble with very small budget (only Entity 1 fits)
    context_limited = context_assembler_service.assemble_context(
        db=db,
        subgraph_results=subgraph,
        token_budget=100
    )

    assert slug_1 in context_limited
    assert "[Context Truncated: Token Budget Exceeded]" in context_limited
    # Entity 3 should be truncated due to low importance ranking and small budget
    assert slug_3 not in context_limited


def test_dialogue_integration(db):
    """Gate F: Verify prompt assembly injection of world graph context in dialogue service."""
    # Create test NPC matching our slug
    npc_slug = f"npc_wizard_{uuid.uuid4().hex[:6]}"
    npc = NPCProfile(
        slug=npc_slug,
        name="Oracle",
        personality_summary="Enigmatic oracle.",
        voice_profile="soft"
    )
    db.add(npc)
    db.commit()

    # Create adjacent entities to the NPC to compile into graph context
    slug_item = f"item_{uuid.uuid4().hex[:6]}"
    graph_repo.create_entity(db, npc_slug, "character", "Oracle", "NPC Oracle", importance_score=80)
    graph_repo.create_entity(db, slug_item, "item", "Staff", "Oracle staff", importance_score=50)
    graph_repo.create_relationship(db, npc_slug, slug_item, "holds")

    # Trigger dialogue prompt assembly
    payload = {
        "npc_slug": npc_slug,
        "player_message": "What do you hold?",
        "selected_chunk_ids": []
    }
    
    response = client.post("/api/v1/dialogue/assemble", json=payload)
    assert response.status_code == 200
    data = response.json()
    assembled = data["assembled_prompt"]
    
    assert "[World Graph Lore Context]" in assembled
    assert f"Oracle ({npc_slug})" in assembled
    assert f"Staff ({slug_item})" in assembled
    assert "holds" in assembled
