# Phase 6 Performance and Resilience Validation

Date: 2026-08-01

## Scope

Phase 6 repairs the repository's opt-in runtime concurrency benchmark and makes
the production database connection budget explicit. It does not claim public
internet capacity, add worker infrastructure, migrate to async SQLAlchemy, or
change the design-agent graph.

## Root cause

The previous benchmark shared one global FastAPI `TestClient` across 10, 25,
and 50 operating-system threads and joined every thread without a deadline. A
worker stalled inside the shared in-process transport could therefore block the
entire pytest process indefinitely. The test also mixed API requests with a
direct quest-service call, which made the measured boundary inconsistent.

The historical command produced no result before a 94-second external timeout.
Earlier Phase 4 execution had remained stuck for more than five minutes.

## Remediation

- Replaced shared synchronous client access with isolated asynchronous HTTP
  clients using FastAPI's ASGI transport.
- Exercised dialogue, graph traversal, and quest generation through their real
  API routes.
- Added unique project and player identities so tiers do not inherit state.
- Added 15-second worker and 30-second tier deadlines.
- Added per-stage p95 latency, completion, timeout, domain-rejection, error,
  throughput, and retained-memory diagnostics.
- Added a two-worker smoke test to the default CI suite.
- Kept 5, 10, and 15 worker tiers behind the explicit `load` marker. Fifteen
  matches the default one-process database budget of five pooled plus ten
  overflow connections.
- Added validated SQLAlchemy pool settings with connection pre-ping and recycle.

Duplicate quest responses remain valid domain behavior: concurrent requests can
produce the same deterministic quest title, and GameMind's duplicate guard may
reject later requests with HTTP 422. The harness records these separately and
does not misclassify them as infrastructure failures.

## Local measurements

Environment: existing Docker Compose development stack, deterministic mock LLM.

| Workers | Completed | Infrastructure errors | Timeouts | Duration | Throughput | p95 end-to-end | Retained memory |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 5 | 5 | 0 | 0 | 1.13 s | 4.44 workflows/s | 1.12 s | 6.0 MiB |
| 10 | 10 | 0 | 0 | 1.56 s | 6.42 workflows/s | 1.55 s | 0.9 MiB |
| 15 | 15 | 0 | 0 | 2.44 s | 6.15 workflows/s | 2.43 s | 1.1 MiB |

An exploratory 20-worker run exceeded the configured 15-connection database
budget. SQLAlchemy reported `QueuePool limit of size 5 overflow 10 reached`
rather than proving a 20-request capacity target. The release regression gate
therefore stops at the configured budget instead of increasing connections to
make an arbitrary test tier pass.

At 15 workers, stage p95 was approximately 1.89 seconds for dialogue, 0.17
seconds for graph traversal, and 0.49 seconds for quest generation. Dialogue is
the dominant local runtime cost and should be measured first when provider or
retrieval behavior changes.

## Interpretation

The repaired harness proves bounded completion and catches local regressions in
the current one-process topology. It does not establish a public SLA because it
does not include TLS termination, network latency, hosted NVIDIA inference,
multiple API processes, or a managed PostgreSQL service.

Before public deployment, repeat the same workload against the deployed API,
set a product traffic target, and size PostgreSQL connections using:

```text
backend process count * (DATABASE_POOL_SIZE + DATABASE_MAX_OVERFLOW)
```

Leave additional database capacity for Alembic, backup jobs, and operators.

## Verification gates

```text
Focused configuration and smoke tests: 8 passed, 1 load test deselected
Explicit load benchmark: 1 passed, 1 smoke test deselected
Full backend suite: 215 passed, 1 load test deselected
Frontend lint: passed
Frontend production build: passed (19 routes)
```

The default suite intentionally runs the two-worker smoke and deselects only the
larger benchmark. Run the explicit `-m load` command before a release that
changes database access, dialogue assembly, graph traversal, quest generation,
or deployment pool settings.
