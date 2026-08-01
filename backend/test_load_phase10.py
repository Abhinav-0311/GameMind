import asyncio
import gc
import math
import time
import uuid
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.database import SessionLocal, get_db
from app.models.graph import WorldEntity, WorldEntityVersion
from app.models.npc import NPCProfile
from main import app


LOAD_PROJECT_PREFIX = "load_harness"
WORKER_TIMEOUT_SECONDS = 15.0
TIER_TIMEOUT_SECONDS = 30.0


@pytest.fixture(autouse=True)
def setup_isolated_db():
    """Give every concurrent request its own SQLAlchemy session."""

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
    """Return private process memory usage, falling back to RSS when needed."""
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
            with open("/proc/self/status", "r", encoding="ascii") as status_file:
                for line in status_file:
                    if line.startswith("VmRSS:"):
                        return int(line.split()[1]) * 1024
        except OSError:
            pass
    return 0


def setup_npc_helper(db_session, project_id: str, slug: str = "eldrin") -> None:
    """Create the project-scoped runtime records required by the workload."""
    npc = db_session.query(NPCProfile).filter(
        NPCProfile.game_project_id == project_id,
        NPCProfile.slug == slug,
    ).first()
    if npc is not None:
        return

    db_session.add(
        NPCProfile(
            slug=slug,
            name="Eldrin",
            personality_summary="Mage of the Order",
            faction_alignment="mages",
            game_project_id=project_id,
        )
    )
    entity = WorldEntity(
        id=uuid.uuid4(),
        slug=slug,
        entity_type="npc",
        game_project_id=project_id,
    )
    db_session.add(entity)
    db_session.flush()
    db_session.add(
        WorldEntityVersion(
            entity_id=entity.id,
            version=1,
            name="Eldrin",
            description="Mage NPC",
            importance_score=8,
        )
    )
    db_session.commit()


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


async def _run_worker(worker_id: int, project_id: str) -> dict[str, Any]:
    """Exercise one representative runtime path entirely through HTTP APIs."""
    player_id = f"load_player_{worker_id}_{uuid.uuid4().hex[:8]}"
    headers = {
        "X-Game-Project-ID": project_id,
        "X-Player-ID": player_id,
    }
    stage_latencies: dict[str, float] = {}
    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://gamemind.test",
        headers=headers,
    ) as client:
        started = time.perf_counter()

        stage_started = time.perf_counter()
        dialogue = await client.post(
            "/api/v1/dialogue/chat",
            json={
                "npc_slug": "eldrin",
                "player_message": "Hello there",
                "player_id": player_id,
            },
        )
        stage_latencies["dialogue"] = time.perf_counter() - stage_started
        if dialogue.status_code != 200:
            raise RuntimeError(f"dialogue returned {dialogue.status_code}: {dialogue.text[:240]}")

        stage_started = time.perf_counter()
        traversal = await client.get(
            "/api/v1/graph/subgraph",
            params={"seeds": "eldrin", "depth": 2},
        )
        stage_latencies["graph"] = time.perf_counter() - stage_started
        if traversal.status_code != 200:
            raise RuntimeError(f"graph returned {traversal.status_code}: {traversal.text[:240]}")

        stage_started = time.perf_counter()
        quest = await client.post(
            "/api/v1/quests/generate",
            json={
                "npc_slug": "eldrin",
                "player_id": player_id,
                "player_level": 5,
            },
        )
        stage_latencies["quest"] = time.perf_counter() - stage_started
        if quest.status_code not in {200, 422}:
            raise RuntimeError(f"quest returned {quest.status_code}: {quest.text[:240]}")
        if quest.status_code == 422 and "Duplicate quest" not in quest.text:
            raise RuntimeError(f"quest was rejected unexpectedly: {quest.text[:240]}")

    return {
        "worker_id": worker_id,
        "latency": time.perf_counter() - started,
        "stage_latencies": stage_latencies,
        "quest_domain_rejected": quest.status_code == 422,
    }


async def _run_tier(
    concurrency: int,
    project_id: str,
) -> tuple[list[dict[str, Any]], list[str], int]:
    tasks = [
        asyncio.create_task(
            asyncio.wait_for(
                _run_worker(worker_id, project_id),
                timeout=WORKER_TIMEOUT_SECONDS,
            ),
            name=f"load-worker-{worker_id}",
        )
        for worker_id in range(concurrency)
    ]

    try:
        outcomes = await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=TIER_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        unfinished = [task.get_name() for task in tasks if not task.done()]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        return [], [f"tier deadline exceeded; unfinished={unfinished}"], len(unfinished)

    results: list[dict[str, Any]] = []
    errors: list[str] = []
    timed_out = 0
    for worker_id, outcome in enumerate(outcomes):
        if isinstance(outcome, TimeoutError):
            timed_out += 1
            errors.append(f"worker {worker_id} exceeded {WORKER_TIMEOUT_SECONDS:.0f}s")
        elif isinstance(outcome, BaseException):
            errors.append(f"worker {worker_id}: {type(outcome).__name__}: {outcome}")
        else:
            results.append(outcome)
    return results, errors, timed_out


def run_concurrent_workloads(concurrency: int) -> dict[str, Any]:
    """Run a bounded concurrency tier and return actionable diagnostics."""
    project_id = f"{LOAD_PROJECT_PREFIX}_{concurrency}_{uuid.uuid4().hex[:8]}"
    db = SessionLocal()
    try:
        setup_npc_helper(db, project_id)
    finally:
        db.close()

    gc.collect()
    memory_before = get_memory_usage_bytes()
    started = time.perf_counter()
    results, errors, timed_out = asyncio.run(_run_tier(concurrency, project_id))
    duration = time.perf_counter() - started
    gc.collect()
    memory_growth = max(0, get_memory_usage_bytes() - memory_before)

    latencies = [result["latency"] for result in results]
    stage_p95 = {
        stage: _percentile(
            [result["stage_latencies"][stage] for result in results],
            0.95,
        )
        for stage in ("dialogue", "graph", "quest")
        if results
    }
    return {
        "concurrency": concurrency,
        "completed": len(results),
        "timed_out": timed_out,
        "errors_count": len(errors),
        "errors": errors,
        "duration": duration,
        "throughput": len(results) / duration if duration > 0 else 0.0,
        "avg_latency": sum(latencies) / len(latencies) if latencies else 0.0,
        "p95": _percentile(latencies, 0.95),
        "p99": _percentile(latencies, 0.99),
        "stage_p95": stage_p95,
        "quest_domain_rejections": sum(
            bool(result["quest_domain_rejected"]) for result in results
        ),
        "memory_growth_bytes": memory_growth,
    }


def _assert_healthy_tier(result: dict[str, Any], max_memory_growth: int) -> None:
    assert result["completed"] == result["concurrency"], result
    assert result["timed_out"] == 0, result
    assert result["errors_count"] == 0, result
    assert result["duration"] < TIER_TIMEOUT_SECONDS, result
    assert result["p95"] < WORKER_TIMEOUT_SECONDS, result
    assert result["memory_growth_bytes"] < max_memory_growth, result


def test_load_harness_two_worker_smoke():
    """Keep deadline and isolation behavior covered by the default CI suite."""
    result = run_concurrent_workloads(2)
    _assert_healthy_tier(result, max_memory_growth=100 * 1024 * 1024)


@pytest.mark.load
def test_load_scaling_thresholds():
    """Detect deadlocks and severe regressions in the local single-process stack."""
    thresholds = [
        (5, 100 * 1024 * 1024),
        (10, 125 * 1024 * 1024),
        (15, 150 * 1024 * 1024),
    ]

    for concurrency, max_memory_growth in thresholds:
        result = run_concurrent_workloads(concurrency)
        print(f"load tier: {result}")
        _assert_healthy_tier(result, max_memory_growth=max_memory_growth)
