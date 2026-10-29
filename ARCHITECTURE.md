# GameMind architecture

Current implementation map. Acceptance and future scope belong in [MVP.md](MVP.md),
not historical Release 2/3 or Phase 1–8 labels.

## Components

```text
Next.js dashboard
  → FastAPI /api/v1
    → PostgreSQL: sources, projects, decisions, runs, artifacts, audit, Gemini budgets and runtime data
    → Chroma: project/document-scoped lexical retrieval
    → LangGraph: persisted design workflow and human-review interrupt
      → profile-selected mock OR Gemini; legacy optional NVIDIA

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

### Revision failure and recorded rejection

If a revision fails before a new artifact is saved, `workflow.py` retains the
previous artifact and critique and routes back to `human_review`, without an
automatic correction retry or re-critique. `revision_count` counts saved revisions,
not failed attempts. The run's `model_config.consecutive_revision_failures`
increments separately; `DESIGN_AGENT_MAX_CONSECUTIVE_REVISION_FAILURES` defaults
to 3. Saving a successful revision consumes a revision slot and resets that
failure counter. The API refuses further corrections at either limit. Failed
revision jobs are marked failed without automatic job retry; resume idempotency
keys include the saved-revision count and consecutive-failure count (`jobs.py`).

For inline review, invalid structured output/local value validation maps to
**502**; provider unavailability/transport timeout maps to **503**. A wholly
no-op correction from the offline mock provider returns **409** with its capability
message; other recoverable failures without a specific mapping use 409. Revision-budget
and review conflicts also return 409. These are not claims that every exception
is a provider outage; genuinely unexpected resume errors retain a generic 500.
The response reports saved revision slots and consecutive failures separately.

The f79e059 guard in `service.review()` refuses a decision conflicting with an
existing review event for the current artifact **before resuming or queueing**.
In particular, reject → failed correction → approve of that unchanged artifact
returns **409**: the recorded rejection is not superseded. This preserves one
recorded decision per artifact and avoids faulting the human-review checkpoint.
The dashboard receives `approval_blocked_reason`, disables Approve and shows the
reason. Another same-decision correction remains possible within both limits;
a successfully revised, new artifact can be reviewed and approved. Otherwise,
start a new isolated run with fresh consent. Historical faulted runs are not
automatically repaired. Approval and export retain all other quality gates.

### Provider selection and shared adapter

`provider_factory.py` gives `LLM_PROFILE` precedence over legacy selectors:

- `test` selects deterministic `MockDesignAgentProvider` and skips Gemini startup
  verification; no hosted key is needed.
- `dev` selects Gemini with `GEMINI_DEV_MODEL` for all hosted nodes.
- `showcase` uses `GEMINI_DEV_MODEL` for planning and `GEMINI_SHOWCASE_MODEL` for
  generation, critique and revision. Model IDs come from settings, not hardcoded
  routing choices.
- With no profile, `DESIGN_AGENT_PROVIDER` overrides `LLM_PROVIDER`; this legacy
  path accepts mock or NVIDIA. NVIDIA is optional, not the current DEV path.

`llm_provider.py` defines the shared `CompletionRequest`/`CompletionResult`
boundary and validation/repair/truncation machinery. The naming is historical:
shared agent prompt builders and typed artifact/review adaptation live in
`nvidia_provider.py`. `GeminiDesignAgentProvider` reuses that adapter and
`GeminiProvider` subclasses the existing completion implementation, replacing the
transport rather than duplicating prompt builders. NVIDIA uses HTTPX; Gemini
uses google-genai `client.interactions.create`, `store=False`, without
`previous_interaction_id`. The Gemini boundary places policy in system instructions
and labels source/artifact data untrusted in the user input at the known builder
boundaries. Only output text/usage and reasoning-discard metadata are returned,
not model reasoning. Provider-neutral naming/cleanup is planned after the MVP
([MVP.md](MVP.md)); it has not renamed this code.

With `DESIGN_AGENT_FALLBACK_TO_MOCK=true`, the resilient wrapper may substitute
mock for eligible provider errors in plan, generate and critique. It marks the
result degraded and records the actual fallback provider and failure. Errors
marked `stop_run` (including Gemini auth/budget/exhaustion failures) bypass mock;
arbitrary unexpected exceptions are not caught as successful fallback. For Gemini
profiles, `DESIGN_AGENT_FALLBACK_DISABLED_NODES` defaults to `["revise"]`, so
revision errors do not save a mock replacement. **Legacy NVIDIA caveat:** its
factory branch does not pass this exclusion setting; its wrapper retains the
legacy default with no disabled nodes.

Approval checks the run's degraded marker and scoped node-execution history,
including fallback returned before later validation failed (`review_policy.py`).
Degraded output needs explicit, artifact-bound `acknowledge_degraded=true` in
addition to ordinary proposal confirmations. The dashboard requires a deliberate
checkbox; the approval event records the acknowledgement. It waives no quality
gate and is rechecked during resumed review and finalization.

### Gemini request budgets and wire schemas

`gemini_budget.py` and `models/gemini_usage.py` own the local reservation ledger:

- Env limits: `GEMINI_DEV_RPM/RPD` default to **5/500**;
  `GEMINI_SHOWCASE_RPM/RPD` to **3/20**. RPM is a shared **in-process** sliding
  window, bounded by `GEMINI_RPM_MAX_WAIT_SECONDS` (60 by default), not a
  distributed limiter. If both model IDs coincide, the stricter limits apply.
- `gemini_daily_usage` is keyed by model ID and the `America/Los_Angeles`
  calendar date via `zoneinfo` (including DST), not workspace. HTTP request hooks
  reserve and commit **before sending**: failed requests, retries, repair,
  truncation resends and startup GETs count. Database failure stops the send.
  Reservations are conservative: a crash before transmission can overcount.
- `DesignAgentRun.gemini_request_count` enforces
  `GEMINI_MAX_REQUESTS_PER_RUN` (12 default), across revisions. Startup verification
  counts daily, not against a saved run. Preflight refuses run creation if any
  selected model is exhausted or below `GEMINI_RUN_BUDGET_ESTIMATE` (8 default);
  it does not reserve the whole estimate. Preflight returns 429, or 503 if the
  budget database is unavailable; each later send still checks its limits.
- On 429, one retry uses a `google.rpc.RetryInfo.retryDelay` of at most 60 seconds,
  otherwise waits 60 seconds, subject to request limits. A second 429 persists
  model exhaustion for that Pacific day. Showcase may fall back to its dev model
  for daily exhaustion/rate limiting, with degraded model provenance; otherwise
  the failure stops instead of becoming mock. Exhausted models are not sent to.
- HTTP 400 with `API_KEY_INVALID`, or 401/403, becomes `authentication_error`,
  without retry/mock substitution. Other 400s are not retried. Transport/5xx
  errors have at most two retries with exponential backoff and jitter; each
  actual attempt remains budgeted (`gemini_provider.py`).

`validate_llm_startup()` runs for dev/showcase in API and worker startup. It checks
each distinct selected model through Google's model GET. Success is cached by
credential hash/model **within the process only**; a new process spends a GET per
uncached model, plus any transport retries. Verification failures abort startup.
`backend/gemini_usage.py` reads today's local counts, limits, remaining budget and
exhaustion flags without contacting Google. These local limits/reservations are
not a guarantee of Google's quotas, billing or AI Studio counter equality.

`GEMINI_SCHEMA_REDUCTION_NODES` defaults to `["revise"]`: plan,
`generate_blueprint` and critique keep their full schemas. For revise, the shared
reducer first keeps enum/const while stripping the other decoder constraints;
if compact UTF-8 JSON exceeds `GEMINI_REVISE_KEEP_LITERALS_MAX_BYTES` (6,000
default), it also strips literals. Types, required fields and structure remain.
Each send logs node/mode/byte size, not content. Other explicitly selected nodes
use full reduction. **Full original local validation is unchanged**, as is the
NVIDIA wire path; reducing the wire schema does not certify model compliance.

### Critique and finalization integrity

The v2 critic instructions distinguish source-backed `missing` (specific evidence
index required) from `not_specified` when the source is silent. In the shared
`llm_provider.py` completion boundary, a critique failing **only** the exact
source-anchored-omissions rule gets one corrective re-ask with the original inputs
and exact error. Both Gemini and NVIDIA use it. No findings are fabricated or
mechanically rewritten; the same validator applies and another invalid response
fails without a third corrective completion. Diagnostics record the outcome;
Gemini counts every HTTP attempt against daily/run budgets. This is distinct
from bounded transport retries. A separate model critique is **not independent
semantic proof**; its misses/false positives remain in the acceptance reports.

Finalize validates with the frozen design contract version and compares canonical
sorted-key JSON digests before saving a blueprint/final artifact. The checkpoint
draft must equal the persisted reviewed draft; the candidate final may differ
only by these deterministic server additions:

- `/npc_memory_design/memory_unspecified=true` when the reviewed memory is empty,
  uncited and warned, and frozen `allow_unspecified_memory` is true
  (`grounding.memory_is_unspecified`).
- `/unity_runtime_preview/runtime_deferred=true`, plus the exact warning
  **"Runtime integration explicitly deferred. Approved design only; no runtime release or materialization."**,
  when frozen `defer_runtime` is true.

An integrity mismatch saves no final/blueprint, retains the reviewed draft,
records the failure and returns to human review. Raw hashes can differ for these
enumerated metadata additions only. `backend/verify_final_integrity.py`
independently derives them from reviewed content/frozen settings and reports
`EXACT`, `EQUAL_EXCEPT_DOCUMENTED_METADATA` or `MISMATCH`, both raw hashes and all
changed/offending paths. Its CLI reads the approval-linked pair in a PostgreSQL
READ ONLY snapshot without a model. Moving the flags before review is planned
after the MVP. Run C met this policy, not strict byte equality; neither this
policy nor passing offline guards establishes whole-MVP acceptance
([Run C](docs/acceptance/2026-10-27-live-approval-export.md#fresh-run-approval-attempts),
[E64/E68](MVP.md#8-evidence-ledger)).

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
and telemetry. Their generic dialogue provider remains local/mock; hosted agent
design generation is a different provider path. Unity consumes REST contracts and
owns rendering/input/animation, not backend approval policy.

Local authentication may be disabled. Production requires authentication,
workspace roles, secure session cookies, queued execution and deployment secrets.
See [deployment](docs/deployment.md) and [domain model](DOMAIN_MODEL.md).
