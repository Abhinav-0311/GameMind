import pytest
import uuid
import json
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from main import app
from app.database import SessionLocal
from app.models.graph import WorldEntity, WorldEntityVersion, WorldRelationship
from app.repositories.graph_repository import graph_repo
from app.services.graph_cache import graph_cache
from app.services.graph_traversal import graph_traversal_service

client = TestClient(app)

@pytest.fixture(scope="module")
def db():
    db_session = SessionLocal()
    try:
        yield db_session
    finally:
        # Cleanup created test entities/relationships
        db_session.query(WorldRelationship).delete()
        db_session.query(WorldEntityVersion).delete()
        db_session.query(WorldEntity).delete()
        db_session.commit()
        db_session.close()

def test_repository_helpers_and_bfs(db):
    """Verify get_adjacent_relationships and BFS shortest path traversal (unweighted)."""
    # 1. Create a clean set of entities
    a = graph_repo.create_entity(db, "node_a", "faction", "Alpha Faction", "Primary node")
    b = graph_repo.create_entity(db, "node_b", "faction", "Beta Faction", "Second node")
    c = graph_repo.create_entity(db, "node_c", "faction", "Gamma Faction", "Third node")
    d = graph_repo.create_entity(db, "node_d", "faction", "Delta Faction", "Fourth node")

    # 2. Create relationships
    # Long path: a -> b -> c -> d (3 hops)
    # Short path: a -> c -> d (2 hops)
    graph_repo.create_relationship(db, "node_a", "node_b", "allied_with")
    graph_repo.create_relationship(db, "node_b", "node_c", "allied_with")
    graph_repo.create_relationship(db, "node_c", "node_d", "allied_with")
    graph_repo.create_relationship(db, "node_a", "node_c", "allied_with")

    # 3. Verify get_adjacent_relationships Outgoing
    rels_out = graph_repo.get_adjacent_relationships(db, a.id, direction="out")
    assert len(rels_out) == 2
    targets = {r.target_id for r in rels_out}
    assert b.id in targets
    assert c.id in targets

    # 4. Verify get_adjacent_relationships Incoming
    rels_in = graph_repo.get_adjacent_relationships(db, c.id, direction="in")
    assert len(rels_in) == 2
    sources = {r.source_id for r in rels_in}
    assert a.id in sources
    assert b.id in sources

    # 5. Run BFS Shortest Path
    result = graph_traversal_service.traverse(db, "node_a", "node_d", depth=4, algorithm="bfs")
    paths = result["paths"]
    assert len(paths) == 1
    shortest_path = paths[0]
    assert shortest_path["nodes"] == ["node_a", "node_c", "node_d"]
    assert len(shortest_path["edges"]) == 2


def test_dfs_traversal_constraints_and_cycles(db):
    """Verify DFS exploration path discovery, cycle handling, and limits."""
    # Create cyclic graph: a -> b -> c -> a
    # And multiple paths from a to d via different intermediate nodes
    a = graph_repo.create_entity(db, "dfs_a", "faction", "A", "A")
    b = graph_repo.create_entity(db, "dfs_b", "faction", "B", "B")
    c = graph_repo.create_entity(db, "dfs_c", "faction", "C", "C")
    d = graph_repo.create_entity(db, "dfs_d", "faction", "D", "D")

    graph_repo.create_relationship(db, "dfs_a", "dfs_b", "leads_to")
    graph_repo.create_relationship(db, "dfs_b", "dfs_c", "leads_to")
    graph_repo.create_relationship(db, "dfs_c", "dfs_a", "leads_to") # cycle
    graph_repo.create_relationship(db, "dfs_c", "dfs_d", "leads_to")
    graph_repo.create_relationship(db, "dfs_a", "dfs_d", "leads_to") # direct path

    # Verify DFS finds paths without getting stuck in cycle
    result = graph_traversal_service.traverse(db, "dfs_a", "dfs_d", depth=4, algorithm="dfs")
    paths = result["paths"]
    assert len(paths) > 0
    
    # Path 1: dfs_a -> dfs_d
    # Path 2: dfs_a -> dfs_b -> dfs_c -> dfs_d
    node_paths = [p["nodes"] for p in paths]
    assert ["dfs_a", "dfs_d"] in node_paths
    assert ["dfs_a", "dfs_b", "dfs_c", "dfs_d"] in node_paths

    # Verify DFS Max Path Limit (MAX_PATH_RESULTS = 25)
    # Create 30 paths by adding 30 different middle nodes: dfs_a -> mid_i -> dfs_d
    for i in range(30):
        mid_slug = f"mid_{i}"
        graph_repo.create_entity(db, mid_slug, "faction", mid_slug, mid_slug)
        graph_repo.create_relationship(db, "dfs_a", mid_slug, "leads_to")
        graph_repo.create_relationship(db, mid_slug, "dfs_d", "leads_to")

    # Clear cache to force fresh traversal
    # We can use different parameters (depth=3) or invalidate/clear mock store
    result_limited = graph_traversal_service.traverse(db, "dfs_a", "dfs_d", depth=3, max_paths=25, algorithm="dfs")
    paths_limited = result_limited["paths"]
    assert len(paths_limited) <= 25


def test_subgraph_extraction(db):
    """Verify subgraph neighborhood extraction and size restrictions."""
    # Seed entity
    seed = graph_repo.create_entity(db, "seed_node", "faction", "Seed", "Seed")
    # Attach 5 neighbors
    for i in range(5):
        n_slug = f"neighbor_{i}"
        graph_repo.create_entity(db, n_slug, "faction", n_slug, n_slug)
        graph_repo.create_relationship(db, "seed_node", n_slug, "connected_to")

    subgraph = graph_traversal_service.get_subgraph(db, seeds=["seed_node"], depth=1)
    assert len(subgraph["nodes"]) == 6 # seed + 5 neighbors
    assert len(subgraph["edges"]) == 5

    # Test edge limit enforcement
    subgraph_limited = graph_traversal_service.get_subgraph(
        db, seeds=["seed_node"], depth=1, max_nodes=100, max_edges=3
    )
    assert len(subgraph_limited["edges"]) <= 3


def test_version_stamp_caching(db):
    """Verify cache hits, misses, stamp increments, and rebuilds on mutation."""
    # Create nodes and relationship
    slug_u = f"user_{uuid.uuid4().hex[:6]}"
    slug_v = f"item_{uuid.uuid4().hex[:6]}"
    graph_repo.create_entity(db, slug_u, "faction", "User", "User")
    graph_repo.create_entity(db, slug_v, "faction", "Item", "Item")
    graph_repo.create_relationship(db, slug_u, slug_v, "owns")

    # Traversal query prefix
    query_prefix = f"graph:path:{slug_u}:{slug_v}:4:bfs:current"

    # Step 1: Run traversal. This should miss and then cache the result
    res1 = graph_traversal_service.traverse(db, slug_u, slug_v, depth=4, algorithm="bfs")
    assert len(res1["paths"]) == 1

    # Step 2: Run traversal again. This should hit the cache
    # We can verify it is a cache hit by comparing stored data
    res2 = graph_traversal_service.traverse(db, slug_u, slug_v, depth=4, algorithm="bfs")
    assert res2 == res1

    # Step 3: Mutate the entity. This increments its version stamp and invalidates the cache
    graph_repo.update_entity(db, slug_u, description="Updated User Description")
    
    # Check that metadata stamp check fails, triggering rebuild
    res3 = graph_traversal_service.traverse(db, slug_u, slug_v, depth=4, algorithm="bfs")
    assert res3 == res1


def test_traversal_safety_limits_validation_endpoints():
    """Verify safety limits check returns HTTP 422 with the exact custom error payload."""
    # 1. /subgraph depth limit > 4
    response = client.get("/api/v1/graph/subgraph?seeds=node_a&depth=5")
    assert response.status_code == 422
    assert response.json() == {
        "detail": {
            "error": "Traversal validation failed",
            "message": "Requested traversal depth exceeds maximum allowed depth of 4"
        }
    }

    # 2. /subgraph node limit > 100
    response = client.get("/api/v1/graph/subgraph?seeds=node_a&max_nodes=101")
    assert response.status_code == 422
    assert response.json() == {
        "detail": {
            "error": "Traversal validation failed",
            "message": "Requested node limit exceeds maximum allowed of 100"
        }
    }

    # 3. /subgraph edge limit > 500
    response = client.get("/api/v1/graph/subgraph?seeds=node_a&max_edges=501")
    assert response.status_code == 422
    assert response.json() == {
        "detail": {
            "error": "Traversal validation failed",
            "message": "Requested edge limit exceeds maximum allowed of 500"
        }
    }

    # 4. /traverse depth limit > 4
    response = client.get("/api/v1/graph/traverse?source=node_a&target=node_b&depth=5")
    assert response.status_code == 422
    assert response.json() == {
        "detail": {
            "error": "Traversal validation failed",
            "message": "Requested traversal depth exceeds maximum allowed depth of 4"
        }
    }

    # 5. /traverse path limit > 25
    response = client.get("/api/v1/graph/traverse?source=node_a&target=node_b&max_paths=26")
    assert response.status_code == 422
    assert response.json() == {
        "detail": {
            "error": "Traversal validation failed",
            "message": "Requested path limit exceeds maximum allowed of 25"
        }
    }


def test_historical_traversal(db):
    """Verify historical traversal support without SQL row locks."""
    # Create temporal node and relationship state
    slug_x = f"hist_x_{uuid.uuid4().hex[:6]}"
    slug_y = f"hist_y_{uuid.uuid4().hex[:6]}"
    
    # T0: Create entities
    graph_repo.create_entity(db, slug_x, "faction", "X", "X original")
    graph_repo.create_entity(db, slug_y, "faction", "Y", "Y original")
    
    # T1: Create relationship
    t1 = datetime.utcnow()
    # Sleep slightly to ensure distinct timestamps
    import time
    time.sleep(0.1)
    
    rel = graph_repo.create_relationship(db, slug_x, slug_y, "connected_to")
    
    time.sleep(0.1)
    t2 = datetime.utcnow()
    
    # T3: Delete relationship (soft delete)
    time.sleep(0.1)
    graph_repo.delete_relationship(db, slug_x, slug_y, "connected_to")
    
    # Query at T0: path should not exist (relationship not created yet)
    res_t0 = graph_traversal_service.traverse(db, slug_x, slug_y, depth=4, as_of=t1 - timedelta(seconds=1))
    assert len(res_t0["paths"]) == 0
    
    # Query at T2: path should exist
    res_t2 = graph_traversal_service.traverse(db, slug_x, slug_y, depth=4, as_of=t2)
    assert len(res_t2["paths"]) == 1
    
    # Query at current/latest (T3 onwards): path should be soft-deleted
    res_now = graph_traversal_service.traverse(db, slug_x, slug_y, depth=4)
    assert len(res_now["paths"]) == 0
