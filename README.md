<p align="center">
  <img src="assets/brand/gamemind-logo.svg" alt="GameMind" width="360" />
</p>

# GameMind

A dashboard-first assistant for turning game design documents into cited,
reviewable NPC dialogue, quests and implementation guidance.

**MVP status: NOT ACCEPTED.** Useful hosted generation, correction, reliable
critique and the complete approval/export journey remain unresolved. See
[MVP.md](MVP.md) for the single current checklist, blockers and evidence. Passing
infrastructure tests is not acceptance of generated content. Unity comes last.

## Product workflow

```text
Workspace → Sources → Local review/decisions → Explicit hosted consent
          → Draft → Critique → Human review/revision → Approval → Design brief
```

The dashboard must be useful without a game engine. Runtime materialization and
the existing Unity adapter are downstream features, not prerequisites for a
design-only brief. GameMind assists a designer; it does not build a complete game
or guarantee that model output is correct.

## What exists

- Project-scoped workspaces, authentication and membership roles.
- TXT/Markdown/PDF ingestion, source revisions, duplicate detection and citations.
- Local GDD review, design decisions and labelled change-proposal sources.
- Deterministic local blueprint extraction and a separate hosted design-agent path.
- Durable LangGraph runs, frozen evidence, versioned drafts, scoped revision,
  human review and immutable final snapshots.
- Design-brief export and separately gated runtime materialization/contracts.
- Runtime NPC, quest, hint, memory and world-state services; a Unity C# adapter.

These are implemented capabilities, not a claim that every end-to-end flow passes.

## Stack and code map

| Area | Technology / entry point |
| --- | --- |
| Dashboard | Next.js 16, React 19, TypeScript, Tailwind 4; `frontend/src/app/` |
| API | Python 3.11, FastAPI, Pydantic; `backend/main.py`, `backend/app/api/v1/` |
| Durable data | PostgreSQL 15, SQLAlchemy, Alembic; `backend/app/models/`, `backend/alembic/` |
| Retrieval | ChromaDB 0.5.23 with deterministic 384-dimensional lexical embeddings; `rag_service.py` |
| Agent | LangGraph with PostgreSQL checkpoints; `backend/app/design_agent/` |
| Hosted inference | NVIDIA via HTTPX; two logical tiers for planning and artifact work |
| Runtime | Existing REST services and `Unity/Assets/Scripts/` |
| Verification | pytest, frontend lint/build, Playwright state checks; `.github/workflows/verify.yml` |

LangChain Core is a declared dependency; LangGraph, not a separate application
LangChain chain, owns orchestration. [Architecture](ARCHITECTURE.md) and
[domain boundaries](DOMAIN_MODEL.md) describe the current implementation.

## Local setup

Prerequisites: Docker Engine/Compose, Node.js 20 and npm.

From the repository root in PowerShell (create `.env` only if it is absent):

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose up -d --build
```

In another terminal:

```powershell
cd frontend
npm ci
npm run dev
```

- Dashboard: <http://localhost:3000>
- API documentation: <http://localhost:8000/docs>
- Dependency health: <http://localhost:8000/health>

The local Compose stack starts PostgreSQL, Chroma and the API; migrations run on
startup. The agent worker is opt-in through the `agent` profile. Production uses
the separate queued configuration described in [deployment.md](docs/deployment.md).

### Local versus hosted behavior

The example environment defaults to mock/local behavior and needs no hosted key.
Local blueprints extract existing text; they are not fresh NVIDIA generation.
The general runtime dialogue provider is also currently local/mock. NVIDIA is
implemented in the design-agent provider, not every endpoint with an AI label.

For hosted design work, configure `.env` deliberately using `.env.example`:

- `LLM_PROVIDER=nvidia`, or an explicit `DESIGN_AGENT_PROVIDER=nvidia` override.
- Planning uses `NVIDIA_PLAN_MODEL` and the key named by `NVIDIA_PLAN_API_KEY_ENV`.
- Generation/critique/revision use `NVIDIA_ARTIFACT_MODEL` and the key named by
  `NVIDIA_ARTIFACT_API_KEY_ENV`. Point this selector to `NVIDIA_SUPER_API_KEY` when
  using a separate artifact key; it may intentionally share the planning key.
- Decide explicitly whether mock fallback is allowed. Fallback is degraded local
  output, never successful hosted generation.

Keep keys out of Git. Actual model availability/quality is recorded in MVP.md.
The configured pair is Nano Omni for planning and Nemotron 3.5 Super for design
generation/revision/critique. `NVIDIA_GUIDED_JSON_ENABLED=false` sends the schema
as instructions because the new endpoint failed the full native-guided request;
local typed validation and evidence/approval gates still apply. One generation
passed; critique truncated, so hosted reliability remains unaccepted.
Do not switch models or increase limits implicitly. Hosted source transfer requires explicit
consent. Unknown provider costs must remain unavailable, not a fabricated zero.
The [Chunk 1 execution contract](MVP.md#chunk-1-execution-contract--decided-2026-10-18)
fixes model roles and advisory-review boundaries. Existing bound human finding
reviews and mandatory system gates remain; configured models and UI copy do not
establish accepted content or a successful correction.

## Verification — protect the database

**Do not run pytest inside the normal application container.**
`backend/conftest.py` drops and recreates its target schema. A test-looking database
name alone is not proof that its contents are disposable.

- CI's [verification workflow](.github/workflows/verify.yml) creates fresh services.
- For local full-suite work, follow the guarded, fresh-empty-database procedure in
  [MVP.md, Baseline reproduction](MVP.md#7-current-blockers-and-next-work).
- Never reuse the application database or a retained QA database for schema resets.
- `--noconftest` alone does not block database or network access in individual tests.

Frontend checks, from `frontend`:

```powershell
npm run lint
npm run build
```

With the dashboard running separately:

```powershell
npm run test:dashboard-states
```

Dashboard-state tests intercept backend responses and stub hosted fonts. They do
not establish live authentication, NVIDIA quality or successful approval/export.
Use an installed browser supported by the runner; see MVP.md for the Edge command.
Live acceptance is separate and must retain failed attempts and actual output.

## Demo and further documentation

- [Dashboard workflow](docs/workflows/dashboard_workspace.md)
- [CyberRakshak GDD](docs/demo/cyberrakshak_gdd.md) and [walkthrough](docs/demo/cyberrakshak_dashboard_demo.md)
- [Synthetic Frostpeak sample](docs/demo/sample_gdd_frostpeak.md)
- [Runtime API contracts](docs/integrations/runtime_api.md)
- [Production deployment](docs/deployment.md) and [security baseline](SECURITY_BASELINE.md)

Historical phase reports and QA recordings are evidence, not current release
sign-off. Do not present a local/mock demo as hosted generation, or backend
contract tests as Unity execution. The next work item is always in MVP.md.
