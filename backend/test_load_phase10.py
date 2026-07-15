import pytest
import time
import uuid
import threading
import gc
from fastapi.testclient import TestClient
from main import app
from app.database import SessionLocal, get_db
from app.models.npc import NPCProfile
from app.models.graph import WorldEntity, WorldEntityVersion
from app.services.dynamic_quest_generator import DynamicQuestGenerator
from app.services.memory_service import MemoryService
from app.services.rag_service import RAGService

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_isolated_db():
    """Override database dependency to yield fresh thread-local sessions for concurrency tests."""
    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)


def get_memory_usage_bytes() -> int:
    """Return private process memory usage in bytes, falling back to RSS if psutil is absent."""
    try:
        import psutil
        process = psutil.Process()
        if hasattr(process, "memory_full_info"):
            full_info = process.memory_full_info()
            if hasattr(full_info, "uss"):
                return full_info.uss
        return process.memory_info().rss
    except ImportError:
        try:
            with open("/proc/self/status", "r") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        parts = line.split()
                        return int(parts[1]) * 1024
        except Exception:
            pass
    return 0

# Helper to create basic entities
def setup_npc_helper(db_sess, slug="eldrin"):
    npc = db_sess.query(NPCProfile).filter(NPCProfile.slug == slug).first()
    if not npc:
        npc = NPCProfile(
            slug=slug,
            name="Eldrin",
            personality_summary="Mage of the Order",
            faction_alignment="mages"
        )
        db_sess.add(npc)
        db_sess.commit()

        ent = WorldEntity(id=uuid.uuid4(), slug=slug, entity_type="npc")
        db_sess.add(ent)
        db_sess.commit()

        ver = WorldEntityVersion(
            entity_id=ent.id,
            version=1,
            name="Eldrin",
            description="Mage npc",
            importance_score=8
        )
        db_sess.add(ver)
        db_sess.commit()
    return npc


def run_concurrent_workloads(concurrency: int) -> dict:
    """Run concurrent API simulated requests."""
    db = SessionLocal()
    setup_npc_helper(db)
    db.close()

    # Warm the local vector path so this load test measures steady-state request
    # growth, not one-time Chroma client/embedding-function initialization.
    warm_memory = MemoryService(RAGService())
    try:
        if warm_memory.memory_collection and warm_memory.memory_collection.count() > 0:
            warm_memory.memory_collection.query(query_texts=["warmup"], n_results=1)
    except Exception:
        pass

    results = []
    errors = []

    def client_worker():
        start = time.time()
        try:
            # 1. Dialogue chat request
            chat_payload = {
                "npc_slug": "eldrin",
                "player_message": "Hello there",
                "player_id": f"player_{threading.get_ident()}"
            }
            res = client.post("/api/v1/dialogue/chat", json=chat_payload)
            if res.status_code != 200:
                errors.append(f"Dialogue status {res.status_code}")

            # 2. Graph traversal request (using seeds=eldrin parameter instead of slug=eldrin)
            res = client.get("/api/v1/graph/subgraph?seeds=eldrin&depth=2")
            if res.status_code != 200:
                errors.append(f"Traversal status {res.status_code}")

            # 3. Quest generation request
            d = SessionLocal()
            try:
                DynamicQuestGenerator.generate_quest(d, "eldrin", f"player_{threading.get_ident()}", 5)
            except ValueError as val_err:
                if "Duplicate quest found" not in str(val_err):
                    raise
            finally:
                d.close()

            results.append(time.time() - start)
        except Exception as e:
            errors.append(str(e))

    # Measure retained process memory after one-time warmups and garbage collection.
    gc.collect()
    mem_before = get_memory_usage_bytes()

    threads = []
    start_time = time.time()
    for _ in range(concurrency):
        t = threading.Thread(target=client_worker)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    duration = time.time() - start_time
    gc.collect()
    mem_after = get_memory_usage_bytes()
    mem_growth = mem_after - mem_before

    throughput = len(results) / duration if duration > 0 else 0
    avg_lat = sum(results) / len(results) if results else 0
    p95 = sorted(results)[int(len(results) * 0.95)] if results else 0
    p99 = sorted(results)[int(len(results) * 0.99)] if results else 0

    return {
        "concurrency": concurrency,
        "throughput": throughput,
        "duration": duration,
        "avg_latency": avg_lat,
        "p95": p95,
        "p99": p99,
        "errors_count": len(errors),
        "memory_growth_bytes": mem_growth
    }


def test_load_scaling_thresholds():
    """Exercise each supported load tier within one stable app/database lifecycle."""
    thresholds = [
        (10, 100 * 1024 * 1024),
        (25, 100 * 1024 * 1024),
        (50, 150 * 1024 * 1024),
    ]

    for concurrency, max_memory_growth in thresholds:
        result = run_concurrent_workloads(concurrency)
        assert result["errors_count"] == 0, result
        assert result["memory_growth_bytes"] < max_memory_growth, result
