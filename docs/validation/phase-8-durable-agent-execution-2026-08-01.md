# Phase 8 Durable Agent Execution Validation

Date: 2026-08-01

## Purpose

Phase 8 moves long design-agent work out of FastAPI request handling without
replacing LangGraph, Chroma, SQLAlchemy, or the provider abstraction. PostgreSQL
stores delivery state; LangGraph remains the authority for workflow transitions
and checkpoints.

## Execution contract

```text
HTTP create/review
  -> transactionally persist run state and job
  -> return queued run
  -> worker claims with FOR UPDATE SKIP LOCKED
  -> heartbeat lease while LangGraph executes
  -> succeed, retry with bounded backoff, or fail visibly
```

Jobs are project-scoped and use immutable idempotency keys. Start jobs are keyed
to the run. Resume jobs are keyed to the reviewed artifact, preventing duplicate
approval or revision work from repeated UI submissions.

The queue does not duplicate workflow state. Job payloads contain only the
operation and typed human-review decision. Documents, evidence, artifacts,
critiques, checkpoints, and final output remain in their existing authoritative
tables.

## Failure behavior

- A running job refreshes its lease from a separate database session.
- A worker process that dies stops heartbeating; another worker reclaims the
  stale job after the configured lease.
- Failed attempts are bounded by `DESIGN_AGENT_JOB_MAX_ATTEMPTS`.
- Retry reuses the same LangGraph thread and idempotent node side effects.
- Terminal failure updates both the job and run with a visible error.
- Review retries preserve retrieval revision 1 and do not query Chroma again.

## Verification evidence

The focused queue suite proves:

- transactional API enqueue;
- exclusive job claim;
- stale lease recovery;
- successful worker completion;
- bounded terminal failure;
- real LangGraph start, reject, revision, second critique, approval, and
  finalization through queued jobs;
- one retrieval call across the complete rejection cycle.

Final local gates:

```text
Backend: 229 passed, 1 load test deselected
Frontend lint: passed with zero warnings
Frontend production build: passed
Production Compose config: valid
Migration: a4c5d6e7f8b9 -> b5d6e7f8a9c0 -> c6e7f8a9b0d1 applied locally
```

## Deliberate boundaries

This phase does not add Redis, Celery, billing, a new vector store, or a second
workflow engine. PostgreSQL is sufficient for the current bounded workload and
keeps operational complexity honest. External monitoring, encrypted off-host
backup automation, deployment-host capacity testing, and public hosting remain
future production work.
