# GameMind architecture

Current implementation map. Acceptance and future scope belong in [MVP.md](MVP.md),
not historical Release 2/3 or Phase 1–8 labels.

## Components

```text
Next.js dashboard
  → FastAPI /api/v1
    → PostgreSQL: sources, projects, decisions, runs, artifacts, audit and runtime data
    → Chroma: project/document-scoped lexical retrieval
    → LangGraph: persisted design workflow and human-review interrupt
      → configured mock provider OR NVIDIA planning/artifact tiers

Approved design → implementation brief
Separately approved runtime bindings → materialization → runtime API → Unity
```

## Source and local design path

`backend/app/services/rag_service.py` extracts TXT/Markdown/PDF, chunks text
(1000 characters with 200-character overlap), and maintains source revisions and
the `lore_chunks_local_lexical_v1` Chroma collection. Its 384-dimensional vectors
are deterministic lexical embeddings, not a learned semantic embedding model.

`gdd_review_service.py` performs local rule-based gap/conflict triage.
`design_decision_service.py` records human direction and supporting evidence.
`blueprint_service.py` extracts a local blueprint from primary/supporting sources.
Local extraction is distinct from fresh hosted content generation.

## Hosted design-agent path

`backend/app/design_agent/service.py` enforces project ownership, consent and
lifecycle boundaries. `provider_factory.py` selects the configured provider.
`workflow.py` uses LangGraph with PostgreSQL checkpoints:

```text
plan → retrieve/freeze evidence → generate → critique → human review
                                                reject → revise → critique
                                                approve → finalize
```

Ordinary revision reuses frozen evidence and resolved decisions. Drafts/revisions
are versioned; finalized snapshots are immutable. `jobs.py` and the optional
`design_agent_worker` support queued execution; local inline execution also exists.
Agent brief exports use the final artifact, frozen excerpts and recorded run
decisions, not later workspace edits. Runtime preview exports also read the final
artifact; they remain distinct from a materialized runtime bundle.
Briefs include the frozen GDD excerpts; review source disclosure before sharing.

Contract-v2 corrections normally return bounded `artifact_path`/`replacement`
changes, not complete rewritten sections. Conservative dialogue-only requests
reuse the existing compact NPC patch route: profile/quest state stays read-only,
bound triggers cannot disappear, and eligibility is restored server-side. Its
governed schema errors are not repaired into different content. Profile/roster or
multi-section edits retain the existing field contract. Paths stay within selected content/metadata;
replacement shapes reuse the scoped revision contract's field types/constraints,
including null/empty fields. Omitted fields are preserved. Invalid value shapes
fail before application; existing assembly and frozen-citation validation
run after atomic application to a copy, followed by material-change checks and
critique. Objective text edits preserve their state keys. Public review requests,
canonical artifacts and legacy-v1 revisions retain their existing contracts.

Known revision validation/provider failures retain the previous reviewed draft and
return to human review, consuming one revision-budget slot without an automatic
retry or re-critique. The failed execution stays in the trace; inline callers get
409 and reload the budget/trace without clearing the correction. Queued rejection
jobs fail without retrying; a later explicit attempt gets its own budget-bound
idempotency key. Other workflow failures remain failures; old failed runs are not
silently repaired. Approval and export still require all existing quality gates.

NVIDIA calls use HTTPX and Pydantic response contracts. Planning and artifact work
have separate logical routes; generation/critique/revision share the artifact tier.
Retries, truncation recovery and repair are bounded and traced. A separate critique
call is not proof of independent semantic correctness. Current quality failures
remain recorded in MVP.md.

## Trust boundaries

- GDD text, proposals and historical transcripts are data, not instructions.
- Project scoping applies to source selection, retrieval, runs and exports.
- Citations identify source text; citation membership alone does not prove a claim.
- Model findings, local checks and human resolutions remain distinct.
- Unknown sections are not automatically verified source absence.
- Design-only approval does not release runtime content or invent engine bindings.
- No silent mock fallback presented as hosted success; unavailable usage/cost stays honest.

`grounding.py`, `review_policy.py` and `finding_reviews.py` enforce these boundaries.
They do not turn passing structure checks into general semantic correctness.

## Dashboard, runtime and deployment

`frontend/src/lib/api.ts` handles API access; DashboardLayout owns active-workspace,
session and theme UI. Page-level state loads sources, decisions, blueprints and
design-agent runs. The current local and hosted screens still coexist.

Runtime services cover NPC dialogue, quests, hints, memories, graph/world state
and telemetry. Their generic dialogue provider remains local/mock; hosted NVIDIA
design generation is a different provider path. Unity consumes REST contracts and
owns rendering/input/animation, not backend approval policy.

Local authentication may be disabled. Production requires authentication,
workspace roles, secure session cookies, queued execution and deployment secrets.
See [deployment](docs/deployment.md) and [domain model](DOMAIN_MODEL.md).
