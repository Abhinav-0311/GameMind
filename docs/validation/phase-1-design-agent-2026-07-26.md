# Phase 1 Design-Agent Verification

Date: 2026-07-26
Product: GameMind
Reference case study: CyberRakshak

## Purpose

Phase 1 establishes the durable, zero-cost workflow foundation for GameMind's
flagship design agent. CyberRakshak is test evidence, not product-specific
application logic.

## Implemented workflow

```text
plan
  -> retrieve evidence
  -> generate blueprint
  -> critique
  -> human review interrupt

approve -> finalize
reject  -> revise -> critique -> human review
```

The revision branch reads the persisted evidence snapshot. It has no edge back
to retrieval.

## Persistence

Alembic revision `f1a2b3c4d5e6` adds:

- `design_agent_runs`
- `design_agent_evidence_snapshots`
- `design_agent_artifacts`
- `design_agent_critiques`
- `design_agent_review_events`
- `design_agent_node_executions`
- LangGraph's four PostgreSQL checkpoint tables

The checkpoint schema mirrors pinned
`langgraph-checkpoint-postgres==3.1.0`. Application startup does not call
`PostgresSaver.setup()`; Alembic remains the schema authority.

## API surface

```text
POST /api/v1/design-agent/runs
GET  /api/v1/design-agent/runs
GET  /api/v1/design-agent/runs/{run_id}
POST /api/v1/design-agent/runs/{run_id}/review
GET  /api/v1/design-agent/runs/{run_id}/trace
GET  /api/v1/design-agent/runs/{run_id}/exports/technical-brief
GET  /api/v1/design-agent/runs/{run_id}/exports/runtime
```

All operations use the existing `X-Game-Project-ID` authorization boundary.

## Automated verification

Focused gate:

```text
14 passed
```

This covers:

- clean migration from zero
- exact SQLAlchemy/Alembic schema parity
- durable checkpoint creation
- human interrupt
- restart with a fresh workflow instance
- rejection and revision
- unchanged evidence snapshot and one retrieval call
- approval and immutable finalization
- project isolation
- duplicate-review protection
- technical-brief and runtime exports
- existing local RAG behavior

Full backend gate:

```text
193 passed, 1 deselected in 39.35s
```

The deselected test remains the intentionally excluded load benchmark described
in the Phase 0 baseline. It is not a skipped functional test.

## Real local case-study run

Source:

- Workspace: `cyberrakshak`
- Document: `cyberrakshak_gdd.md`
- Indexed chunks: 17

Run:

- Run ID: `c27cf3c9-1174-4218-8336-df0924bc4f12`
- Initial state: `awaiting_review`
- Retrieval revision: 1
- Rejection reason targeted incomplete level-design coverage
- Revised state: `awaiting_review`, revision count 1
- Retrieval-node executions after revision: 1
- Final state: `completed`
- Final artifact: immutable
- Approved blueprint ID: `94f5f5d8-a267-4e29-96d5-e12cf2da02ff`
- Runtime export mode: `mock`
- Technical brief response: HTTP 200, 9,480 bytes

This verifies the orchestration and persistence contract against real indexed
GameMind data. It does not claim that deterministic mock output meets the final
quality scorecard. NVIDIA output quality and the five-metric case-study
evaluation remain later phases.

## Phase 1 verdict

The backend workflow foundation is complete:

- orchestration is explicit
- state is durable
- review is a real interrupt
- resume survives service reconstruction
- evidence is reused
- outputs are versioned and finalized immutably
- every node is traceable at zero provider cost

Phase 2 may add real NVIDIA inference and reliability controls without changing
the workflow or replacing the existing RAG layer.
