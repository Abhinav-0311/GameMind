# GameMind Narrative Platform - Operations Runbook

This runbook outlines standard operating procedures, disaster recovery protocols, troubleshooting guidelines, and incident response workflows for the GameMind Narrative Platform.

---

## 1. Database Operations & Recovery (PostgreSQL)

### A. Manual Vacuuming & Query Optimization
* **Symptom**: Query performance degrades over time on `llm_telemetry_logs` or `generated_quests`.
* **Action**: Execute vacuuming to reclaim disk space and rebuild statistics.
  ```sql
  -- Run simple vacuum on telemetry logs
  VACUUM ANALYZE llm_telemetry_logs;
  -- Run full vacuum (locks table, perform during maintenance windows)
  VACUUM FULL ANALYZE generated_quests;
  ```

### B. Connection Pool Saturation
* **Symptom**: Logs show `QueuePool limit of size 5 overflow 10 reached, connection timed out`.
* **Action**:
  1. Inspect active connection counts in PostgreSQL:
     ```sql
     SELECT count(*), state FROM pg_stat_activity GROUP BY state;
     ```
  2. Increase `pool_size` and `max_overflow` in `backend/app/database.py` or adjust PostgreSQL `max_connections` settings.

---

## 2. Cache Operations & Recovery (Redis)

### A. Redis Connection Failure & Failover
* **Symptom**: Service logs report `Could not connect to Redis: Connection refused. Falling back to direct SQL bypass`.
* **Action**:
  * The caching service degrades gracefully to direct SQL queries or in-memory dictionary cache fallback. No manual intervention is needed for service uptime.
  * To restore Redis:
    ```bash
    docker restart gamemind_redis
    ```

### B. Cache Rebuild & Stamp Invalidation
* **Symptom**: Stale graph data is served to conversation prompts.
* **Action**:
  * Increment the entity version stamp to force O(1) cache mismatch and rebuild:
    ```python
    from app.services.graph_cache import graph_cache
    graph_cache.increment_entity_stamp("eldrin")
    ```

---

## 3. Vector DB Operations & Recovery (ChromaDB)

### A. ChromaDB Offline Fallback
* **Symptom**: Vector searches fail or time out.
* **Action**:
  * The `MemoryService` catches the exception and falls back to relational DB lookup from the `npc_memories` table directly.
  * To restart Chroma:
    ```bash
    docker restart gamemind_chroma
    ```

---

## 4. Incident Response Workflow

1. **Detection**: Alerts triggered by telemetry warnings, high error counts, or slow latency spikes.
2. **Containment**:
   * If memory leak is detected, restart the uvicorn processes.
   * If transaction locks are blocked, locate and terminate slow PID transactions:
     ```sql
     SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE age(clock_timestamp(), query_start) > interval '10 seconds';
     ```
3. **Rollback**: If a bad deployment causes regressions, run rollback commands:
   * Revert git commit: `git revert HEAD`
   * Revert database migration: `alembic downgrade -1`
