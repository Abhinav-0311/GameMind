# Export integrity and dashboard verification

## Delivered

Confirmed and fixed loss of structured game-design content in portable Markdown briefs. `BlueprintBriefService._value_lines` previously rendered named records using only their title/name/objective. NPCs consequently exported as just names; quest objectives, rewards, dependencies, dialogue hooks and failure states were omitted even when present in the approved artifact. Existing quest-state JSON and its integration notes were the exception.

The shared formatter now retains the other populated record fields underneath the record heading. This reaches both the blueprint brief endpoint and the design-agent technical-brief endpoint without changing their API contracts. NPC dialogue mappings retain their eligibility and repetition policies; source chunk IDs, integration notes and assumptions survive. Existing quest-state JSON remains explicitly labelled as a design proposal, not runtime bindings, and its notes are emitted once. Legacy records without a state contract retain their details too.

No content is generated, approved, reinterpreted or written back by the formatter. Saved drafts and historical QA results are not repaired by this export change. The brief will be longer because it now contains the content developers need.

## Verification

- Regression-first: the extended quest export check and new NPC/legacy export check both failed before the formatter change. The failures reproduced an omitted quest ID and an NPC exported only as `Mira`.
- **495 selected backend checks passed, 5 database-fixture cases deselected**, in 25.07 seconds, with one existing Starlette/AnyIO deprecation warning. This is one additional test case, not 495 new cases, and is not a full-suite or measured-coverage result.
- The guarded backend runner disabled shared conftest, plugin autoload, pytest cache and bytecode. It blocked PostgreSQL and external connections, permitting mocked/in-process HTTP and internal Windows test sockets only.
- The existing normal-path API test now verifies the approved brief actually contains NPC archetype/dialogue text, quest objectives and integration notes. It still exercises consent, duplicate-run protection, explicit proposal confirmations, immutable finalization, unchanged draft content, successful design brief export and blocked deferred-runtime export. Its database is disposable SQLite and its checkpoint saver is in memory; retrieval and NVIDIA responses are scripted fixtures.
- **110 dashboard state checks passed** in isolated system-Chrome contexts against the existing Next dev server. All backend requests were intercepted; real backend mutations and hosted calls were zero. Cases include consent, workspace headers, review blockers, finding-review boundaries, proposal confirmation, revision budgets/scopes, source recovery, account recovery, keyboard focus, mobile layout and light/dark states. Measured semantic-text contrast on the sampled analytics states was at least 5.11:1; this is not a whole-dashboard accessibility certification.
- `npm run lint` exited successfully. `npm run build` passed compilation, TypeScript and prerendering. The frontend at `http://127.0.0.1:3000` returned 200 and was left running.
- Scoped `git diff --check` passed. `.env` and `.env.example` hashes match their pre-check values. No dependencies were installed, no model/environment files were changed, and nothing was committed or pushed.

## Native-stack limitation and next gate

Docker's Linux-engine named pipe was absent and backend port 8000 refused connections at the start of this chunk. No local PostgreSQL tools were found on PATH or in the standard Program Files PostgreSQL location. Docker/the existing backend were not started: the configured backend startup also runs Alembic migrations, which this check deliberately did not apply to the application database.

Native PostgreSQL document-ID containment, durable checkpoints and restart/resume are therefore **not verified this turn**. Neither are real ingestion, a live dashboard-to-backend flow or fresh hosted generation quality. All earlier NVIDIA request budgets remain closed.

When the backend infrastructure is available, the next coherent gate is:

1. Create a uniquely named disposable QA database; verify both the parsed database name and `current_database()` before writes. Keep it separate from `gamemind` and the shared `gamemind_test` database.
2. Apply existing migrations only to that new database. Bypass the current shared conftest: it loads `.env.test` with override enabled and drops/recreates the public schema, with only a substring database-name guard.
3. Run native consent, durable-pause, rejection/evidence reuse, fresh-service restart/resume, explicit design approval, brief export and deferred-runtime rejection checks with mocked provider responses and external model calls blocked.
4. Independently perform the read-only dashboard walkthrough against saved normal-flow QA data. Keep known bad drafts blocked; do not convert test success into a claim of AI-quality acceptance.
5. Fresh hosted acceptance remains a separate, explicitly bounded data/request authorization gate. Do not reuse an exhausted budget.

Ponytail kept the implementation in the existing shared formatter: no new export format, dependency, model switch, test harness or runtime feature was added.
