# Native checkpoints and live dashboard verification

## Result

The native PostgreSQL verification previously blocked by stopped Docker is now complete for the selected scope. No application fix was required. This verifies durable workflow mechanics and saved-review safety, not the quality of fresh NVIDIA-generated game content.

## Isolation

- Existing backend, PostgreSQL and Chroma health checks passed. The application database was already at `d2e4f6a8b901` when inspected.
- Created and retained a new empty database: `gamemind_test_qa_20261015_419f941a`. Its name reflects the UTC start date; the local verification date is October 16.
- Applied the existing migration chain only to this new database, after checking its parsed name, `current_database()` and empty public schema.
- Bypassed shared `conftest.py` with `--noconftest -p no:cacheprovider`. A process-local fixture supplied sessions from the new database; no shared-schema reset was used.
- Both PostgreSQL drivers were guarded to permit only that exact QA database on `db:5432`. External Python socket connections and non-mocked/non-TestClient HTTP were blocked. Test settings were process-local; no environment files changed.

## Native regression selection

`test_design_agent_workflow.py` and `test_design_agent_jobs.py`: **27 passed in 11.48 seconds**.

These existing cases cover native durable pause/trace, consent, scoped retrieval and decisions, rejected incomplete drafts, independent-critique approval blocking, rejection/evidence reuse, fresh-service checkpoint resume, project scoping, revision budgets, duplicate active runs, queued execution, lease ownership/reclamation and bounded worker failure. The legacy mock-provider approval case also exports a mock runtime bundle; that is not proof of a governed production runtime release.

## Separate-process governed acceptance

Synthetic source data and scripted responses passed through the real NVIDIA adapter, normal FastAPI routes, real LangGraph graph and native `PostgresSaver`. Retrieval remained a counting fixture; NVIDIA HTTP used `httpx.MockTransport`.

- Project: `qa-native-governed-38d73a4c`
- Run: `cf6b259c-0d29-4c2f-8693-a289954485db`
- Draft: `a2e2b27e-51d3-4a13-b88e-526f2478eb24`
- Final approved QA blueprint: `cf6820fc-cc4a-41d9-a963-1731549c192b`

Process **303** created the controlled review, then exited. Missing consent returned 409 before any model transport request. With simulated consent, three mocked completions and one fixture retrieval produced a reviewable draft and six native checkpoints. Duplicate active review returned 409, wrong-workspace access returned 404, and pre-approval brief export and approval without proposal confirmations returned 409. The critic request omitted generator self-assessment metadata as intended.

Separate process **340** loaded that persisted draft and verified its hash/checkpoint count. Explicit proposal confirmations and design approval succeeded, producing one immutable final artifact and one approved QA blueprint. The original draft remained unchanged. Checkpoints increased from six to eight. Brief export returned 200 with **9,662 bytes**, containing the source title, NPC dialogue/profile details, quest objectives and integration notes. Runtime export returned 409 because runtime was explicitly deferred. Duplicate approval returned 409; there was exactly one final artifact and approval event. Resume made **zero additional model or retrieval calls**.

This was a genuine new Python process using persisted checkpoints, not a restart of the running backend container or a PostgreSQL server failover test. The approved records exist only in the separate synthetic QA database, not in an existing application workspace.

## Read-only live dashboard

Isolated system-Chrome contexts visited the saved Frostpeak review, home, source detail, decisions and blueprints at **1440, 768 and 375 pixels**: **15 page visits** against the real running application backend. Browser routing allowed local GET/HEAD/OPTIONS only; mutations and external services were blocked. Hosted font CSS was stubbed, so layout checks used fallback fonts.

The saved run `7c23d226-c291-4358-82e7-2e942e110e34` in workspace `qa-frostpeak-citations-20261015-058037fe` remained blocked: six NPC dialogue findings, three quest findings and one missing-memory finding. Approval was disabled, its exhausted revision action stayed disabled, and export buttons were absent. The review page was checked in light and dark themes; all visited pages fit the sampled widths without horizontal overflow. Each context reported zero console/runtime errors, failed requests, unexpected HTTP errors and mutation attempts. This was a targeted live walkthrough, not a full accessibility, performance, authentication or fresh-generation acceptance test.

## Preservation and remaining gate

Before/after fingerprints matched across all **39 application-database tables**, and its migration revision was unchanged. Existing telemetry was compared through a fixed timestamp so unrelated new background telemetry would not be mistaken for edited historical rows. `.env` and `.env.example` hashes matched the previous verified values. The sampled backend logs contained zero `ERROR:` or traceback lines. No application source edits, installations, model changes, NVIDIA requests, commits, pushes or existing-workspace approvals occurred this turn.

The isolated QA database is retained for inspection; it contains synthetic fixtures and approved test records. It must not be used as evidence of real hosted-generation quality.

**Remaining:** fresh bounded NVIDIA quality acceptance and a genuinely generated normal dashboard generation → review → approval → export journey. Earlier request budgets remain closed. Do not weaken saved blockers or relabel scripted QA content as model-quality proof.
