import sys
import uuid
import datetime
from app.database import SessionLocal
from app.repositories.graph_repository import GraphRepository
from app.services.graph_cache import cache_service
from app.models.graph import (
    WorldEntity,
    WorldEntityVersion,
    WorldRelationship,
    RelationshipTypeRule
)

db = SessionLocal()
repo = GraphRepository(db)

def cleanup():
    db.rollback()
    
    # 1. Delete matching relationships
    db.query(WorldRelationship).filter(
        WorldRelationship.source_id.in_(
            db.query(WorldEntity.id).filter(WorldEntity.slug.in_(["cache_node_a", "cache_node_b", "cache_node_c"]))
        ) | WorldRelationship.target_id.in_(
            db.query(WorldEntity.id).filter(WorldEntity.slug.in_(["cache_node_a", "cache_node_b", "cache_node_c"]))
        )
    ).delete(synchronize_session=False)

    # 2. Delete entity versions
    db.query(WorldEntityVersion).filter(
        WorldEntityVersion.entity_id.in_(
            db.query(WorldEntity.id).filter(WorldEntity.slug.in_(["cache_node_a", "cache_node_b", "cache_node_c"]))
        )
    ).delete(synchronize_session=False)

    # 3. Delete entities
    db.query(WorldEntity).filter(WorldEntity.slug.in_(["cache_node_a", "cache_node_b", "cache_node_c"])).delete(synchronize_session=False)

    # 4. Delete test rules
    db.query(RelationshipTypeRule).filter(
        RelationshipTypeRule.rel_type == "located_in",
        RelationshipTypeRule.allowed_source_type == "NPC",
        RelationshipTypeRule.allowed_target_type == "Location"
    ).delete()

    db.commit()
    
    # Reset in-memory cache
    cache_service.in_memory_cache.clear()

def seed_rules():
    rule = db.query(RelationshipTypeRule).filter(
        RelationshipTypeRule.rel_type == "located_in",
        RelationshipTypeRule.allowed_source_type == "NPC",
        RelationshipTypeRule.allowed_target_type == "Location"
    ).first()
    
    if not rule:
        rule = RelationshipTypeRule(
            id=uuid.uuid4(),
            rel_type="located_in",
            allowed_source_type="NPC",
            allowed_target_type="Location"
        )
        db.add(rule)
        db.commit()

try:
    print("==================================================")
    print("Testing Graph Cache Invalidation Framework")
    print("==================================================")
    
    cleanup()
    seed_rules()
    
    # 1. Authority Verification
    print(f"1. Verifying Caching Authority...")
    print(f"   Redis Available: {cache_service.redis_available}")
    print(f"   Fallback to In-Memory: {not cache_service.redis_available}")
    
    # 2. Read-Through Entity Caching
    print("\n2. Creating entity 'cache_node_a'...")
    entity_a = repo.create_entity(
        slug="cache_node_a",
        entity_type="NPC",
        name="Cache Node A",
        description="Test node A for caching",
        importance_score=50,
        properties={}
    )
    db.commit()
    
    print("   Querying 'cache_node_a' (should trigger SQL and set cache)...")
    ent_res, ver_res = repo.get_active_entity_by_slug("cache_node_a")
    print(f"   Name from SQL: '{ver_res.name}', Version: {ver_res.version}")
    
    # Verify key in cache
    has_cache = f"graph:entity:cache_node_a" in cache_service.in_memory_cache
    print(f"   Cached key exists in memory cache: {has_cache}")
    assert has_cache is True
    
    print("   Querying 'cache_node_a' again (should hit cache directly)...")
    db.expire_all()
    ent_hit, ver_hit = repo.get_active_entity_by_slug("cache_node_a")
    print(f"   Name from cache: '{ver_hit.name}', Version: {ver_hit.version}")
    assert ver_hit.version == 1

    # 3. Dirty-Transaction Read Bypass
    print("\n3. Testing Dirty-Transaction Read Bypass...")
    # Repopulate cache
    repo.get_active_entity_by_slug("cache_node_a")
    
    # Update entity A without committing (session is now dirty)
    repo.update_entity(
        slug="cache_node_a",
        name="Cache Node A Temp",
        description="Uncommitted dirty version",
        importance_score=80,
        properties={}
    )
    
    # Session is now dirty
    is_dirty = cache_service._is_dirty(db)
    print(f"   Is Session dirty: {is_dirty}")
    assert is_dirty is True
    
    # Fetch entity - should bypass cache and read SQL directly
    print("   Querying active entity while session is dirty...")
    db_ent, db_ver = repo.get_active_entity_by_slug("cache_node_a")
    # Should get the uncommitted name 'Cache Node A Temp'
    print(f"   Name fetched (bypassed cache): '{db_ver.name}'")
    assert db_ver.name == "Cache Node A Temp"
    
    # Rollback to clean session and clear dirty state
    db.rollback()
    print("   Session rolled back. Repopulating cache...")
    repo.get_active_entity_by_slug("cache_node_a")
    
    db_ent2, db_ver2 = repo.get_active_entity_by_slug("cache_node_a")
    print(f"   Name fetched (hit cache): '{db_ver2.name}'")
    assert db_ver2.name == "Cache Node A"

    # 4. Invalidation on Update/Delete
    print("\n4. Updating entity 'cache_node_a' (should trigger invalidation)...")
    repo.update_entity(
        slug="cache_node_a",
        name="Cache Node A Updated",
        description="Updated description",
        importance_score=55
    )
    db.commit()
    
    # Cache key should be deleted
    has_cache_post_update = f"graph:entity:cache_node_a" in cache_service.in_memory_cache
    print(f"   Cached key exists after update: {has_cache_post_update}")
    assert has_cache_post_update is False
    
    # 5. 1-Hop and 2-Hop Path Invalidation Verification
    print("\n5. Setting up graph path validation...")
    
    node_b = repo.create_entity(
        slug="cache_node_b",
        entity_type="Location",
        name="Cache Node B Castle",
        description="Location for 1-hop",
        importance_score=70
    )
    node_c = repo.create_entity(
        slug="cache_node_c",
        entity_type="NPC",
        name="Cache Node C Hero",
        description="NPC for 2-hop",
        importance_score=80
    )
    db.commit()
    
    # Create relationships
    rel_ab = repo.create_relationship(
        source_slug="cache_node_a",
        target_slug="cache_node_b",
        rel_type="located_in",
        weight=1.0,
        properties={}
    )
    rel_cb = repo.create_relationship(
        source_slug="cache_node_c",
        target_slug="cache_node_b",
        rel_type="located_in",
        weight=1.0,
        properties={}
    )
    db.commit()
    
    # Query relationships to populate cache
    repo.get_active_relationship("cache_node_a", "cache_node_b", "located_in")
    repo.get_active_relationship("cache_node_c", "cache_node_b", "located_in")
    repo.get_active_entity_by_slug("cache_node_a")
    repo.get_active_entity_by_slug("cache_node_b")
    repo.get_active_entity_by_slug("cache_node_c")
    
    # Verify all keys are populated in cache
    print("   Active keys in cache:")
    for k in sorted(cache_service.in_memory_cache.keys()):
        print(f"    - {k}")
        
    print("\n6. Running 1-Hop Invalidation on 'cache_node_a'...")
    cache_service.invalidate_entity(db, "cache_node_a", hop_level=1)
    print("   Active keys in cache after 1-hop:")
    for k in sorted(cache_service.in_memory_cache.keys()):
        print(f"    - {k}")
    # Verify graph:entity:cache_node_a is gone
    assert f"graph:entity:cache_node_a" not in cache_service.in_memory_cache
    # Verify graph:relationship:cache_node_a:cache_node_b:located_in is gone (1-hop relation)
    assert f"graph:relationship:cache_node_a:cache_node_b:located_in" not in cache_service.in_memory_cache
    # Verify graph:relationship:cache_node_c:cache_node_b:located_in is still present (not 1-hop of A)
    assert f"graph:relationship:cache_node_c:cache_node_b:located_in" in cache_service.in_memory_cache
    
    # Repopulate A's cache
    repo.get_active_relationship("cache_node_a", "cache_node_b", "located_in")
    repo.get_active_entity_by_slug("cache_node_a")
    
    print("\n7. Running 2-Hop Invalidation on 'cache_node_a'...")
    cache_service.invalidate_entity(db, "cache_node_a", hop_level=2)
    print("   Active keys in cache after 2-hop:")
    for k in sorted(cache_service.in_memory_cache.keys()):
        print(f"    - {k}")
    assert f"graph:entity:cache_node_a" not in cache_service.in_memory_cache
    assert f"graph:relationship:cache_node_a:cache_node_b:located_in" not in cache_service.in_memory_cache
    assert f"graph:relationship:cache_node_c:cache_node_b:located_in" not in cache_service.in_memory_cache

    print("\n==================================================")
    print("ALL CACHE FRAMEWORK TESTS PASSED SUCCESSFULLY!")
    print("==================================================")

finally:
    db.close()
