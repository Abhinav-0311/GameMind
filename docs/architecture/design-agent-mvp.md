# GameMind Design Agent MVP Contract

Status: Flagship MVP Phases 1-4 implemented and verified
Case study: CyberRakshak
Last reviewed: 2026-07-29

## Objective

GameMind's flagship AI workflow converts a real game design document into an
evidence-grounded, human-approved blueprint and exportable runtime artifact.
The MVP proves durable agent orchestration and output quality without replacing
the application's existing RAG, database, authentication, or frontend systems.

## Success scenario

A developer uploads the CyberRakshak GDD and starts a design-agent run.
GameMind identifies the required design outputs, retrieves cited evidence,
generates a structured blueprint, detects incomplete level coverage, produces a
separate critique, and pauses for human review.

The developer rejects the draft because its level-design output is inaccurate.
GameMind revises the draft using the same evidence snapshot, critiques the
revision, and pauses again. After approval, GameMind stores an immutable final
artifact and exports a technical brief and runtime bundle. The trace shows each
node, attempt, provider, latency, token count, and outcome.

## Workflow

```text
START
  -> plan
  -> retrieve evidence
  -> generate blueprint
  -> critique
  -> human review

approved:
  human review -> finalize -> export -> END

rejected:
  human review -> revise -> critique -> human review
```

Ordinary rejection must reuse the saved evidence snapshot. Retrieval may run
again only when a later product phase adds an explicit request for additional
evidence.

## Included in the flagship MVP

- One generic GameMind design-agent workflow, validated with CyberRakshak.
- Explicit LangGraph state and conditional routing.
- Durable checkpointing and restart-safe resume.
- A real human-review interrupt.
- Run-level approval or rejection with one reason.
- One bounded rejection and revision cycle, with a configurable maximum.
- Existing project-scoped Chroma retrieval and citations.
- Pydantic validation at every workflow-node boundary.
- A deterministic design-agent mock provider.
- NVIDIA inference with timeout, bounded retry, and structured-output repair.
- Visible degraded status when a configured fallback is used.
- One trace view covering node status, attempts, provider, tokens, and latency.
- Immutable approved output.
- Technical brief and runtime bundle export.
- A five-metric CyberRakshak quality scorecard.

## Explicitly deferred

- Section-level approval or editing.
- Automatic retrieval after ordinary rejection.
- pgvector migration.
- Application-wide asynchronous SQLAlchemy migration.
- Redis, Celery, Kafka, or Kubernetes.
- Multiple hosted inference providers.
- Open-ended ReAct or multi-agent loops.
- Generic business-research workflows.
- New game-engine integrations.
- Additional Unity scene work before the agent workflow passes acceptance.
- Production billing and enterprise administration.
- A new frontend component framework or design-system migration.

## Architecture ownership

| Concern | Owner |
| --- | --- |
| Workflow transitions and interrupts | LangGraph |
| Model messages and selected structured-output utilities | LangChain Core |
| Durable application records and audit history | PostgreSQL |
| Database schema evolution | Alembic |
| Semantic retrieval | Existing Chroma-backed RAG service |
| Document and chunk source of truth | Existing PostgreSQL document models |
| Deterministic tests | Design-agent MockProvider |
| Real hosted inference | NvidiaProvider |
| API and workspace authorization | Existing FastAPI application |
| Review and trace experience | Existing Next.js application |

LangChain must not replace working GameMind document ingestion, chunking,
retrieval, citations, or domain services merely for framework conformity.

## Persistence rules

- Every run and artifact is scoped to one `game_project_id`.
- A run stores the provider and per-node model configuration used to execute it.
- Retrieval creates a versioned evidence snapshot referenced by later nodes.
- Revision reads the existing evidence snapshot rather than querying Chroma.
- Human decisions record the authenticated actor, action, reason, and timestamp.
- Approved artifacts are immutable; a later change creates a new version.
- Node side effects are idempotent because interrupted nodes may re-execute.
- Model fallback and JSON repair are visible execution events, not hidden logic.

## CyberRakshak scorecard

| Metric | MVP measurement |
| --- | --- |
| Citation relevance | Relevant cited chunks divided by reviewed cited chunks |
| Unsupported-claim rate | Unsupported factual claims divided by factual claims |
| Critique usefulness | Actionable correct findings divided by critique findings |
| Revision correctness | Requested corrections applied without unrelated regression |
| Approval persistence | Review and final artifact survive process restart and reload |

The scorecard may begin with manually reviewed CyberRakshak expectations backed
by deterministic integration tests. A generalized evaluation platform is not
part of the MVP.

## Acceptance gates

The flagship MVP is accepted only when:

1. The graph reaches a durable human-review interrupt.
2. A stopped process can resume the same run from its checkpoint.
3. Approval finalizes exactly one immutable artifact.
4. Rejection revises the draft and returns through critique.
5. Ordinary rejection does not execute retrieval again.
6. MockProvider tests are deterministic and require no paid API.
7. NVIDIA failures produce bounded retries and an explicit degraded outcome.
8. The CyberRakshak scorecard is recorded from a real end-to-end run.
9. Backend tests, frontend lint/build, and a reproducible browser journey pass.

## Scope-change rule

New work that is not required by an acceptance gate must be recorded as
post-MVP work. It may not enter the flagship implementation without an explicit
scope review.

## Delivery status

| Capability | Status |
| --- | --- |
| LangGraph plan, retrieve, generate, critique, review, revise, finalize graph | Implemented in Phase 1 |
| PostgreSQL checkpoints managed by Alembic | Implemented in Phase 1 |
| Restart-safe review resume | Implemented and tested in Phase 1 |
| Evidence snapshot reuse after rejection | Implemented and tested in Phase 1 |
| Project-scoped run records, artifacts, critiques, reviews, and traces | Implemented in Phase 1 |
| Deterministic zero-cost MockProvider | Implemented in Phase 1 |
| Immutable final artifact and existing GameBlueprint export bridge | Implemented in Phase 1 |
| NVIDIA provider, retry, timeout, JSON repair, and explicit fallback | Implemented and deterministically tested in Phase 2 |
| Minimal review and trace console | Implemented and browser-verified in Phase 3 |
| Five-metric CyberRakshak evaluation | Implemented and verified in Phase 4 |

The workflow API is available under `/api/v1/design-agent`. The dashboard
console is available at `/design-agent`. Phase 4 deliberately keeps evaluation
authoring outside the product UI: a completed run displays one immutable
scorecard, while rubric judgments are recorded through the project-scoped API.
