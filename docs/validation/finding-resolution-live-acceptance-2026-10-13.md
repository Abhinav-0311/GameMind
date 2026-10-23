# Finding review — live database and dashboard acceptance

## Result and scope

The authorized migration and real save -> reload -> separate explicit approval
flow passed against the existing local backend, PostgreSQL and dashboard.
Application code was not changed during this acceptance check.

This is **synthetic review-policy acceptance**, not fresh NVIDIA generation,
semantic-quality evaluation, RAG-ingestion acceptance or production certification.
Only a new QA workspace was seeded and approved. No existing game workspace was
approved or modified. No runtime materialization/export action was performed.

## Migration safety

- Before: Alembic `c6e7f8a9b0d1`; finding-resolution table absent.
- Backup: database-container file
  `/tmp/gamemind-before-d2e4f6a8b901-20261013.dump`, PostgreSQL custom format,
  3,280,357 bytes, mode `0600`; archive listing validated (265 entries).
  It contains private database data: do not commit or publish it. This is a
  container-local backup, not durable off-host storage; container replacement
  can lose it. No restore or downgrade was run.
- Applied only the prepared target, with transactional DDL and bounded waits:

  ```powershell
  cd E:\College\Project\Bot
  docker compose exec -T -e PYTHONDONTWRITEBYTECODE=1 -e 'PGOPTIONS=-c lock_timeout=5000 -c statement_timeout=60000' backend alembic upgrade d2e4f6a8b901
  ```

- After: revision `d2e4f6a8b901`, new audit table present and initially empty.
- All 37 pre-existing tables had identical counts and canonical row-content
  fingerprints immediately after migration. Existing artifact/critique tables
  held 48/35 rows, respectively; no production-scale locking claim is made.

## Isolated fixture

- Workspace: `qa-finding-review-20261013-39c03bcd`.
- Run: `9ee0c1d3-22ca-4755-a197-c6ba31986518`.
- Draft: `0b3ccce9-dcae-4a76-a353-33de803c341c`.
- Critique: `f5760612-41ce-4c8a-a79b-11c85e947ed7`.
- Audit: `2b2ed9b7-b100-4bee-bbc0-b1d76a118e5a`.
- Approved QA blueprint: `7bd2973f-2929-4c8a-b174-10653a5e6ed9`.

The new document, frozen excerpt, draft, critique and owner/viewer accounts are
explicitly synthetic. The fixture compares `formal, slow` with the frozen source
sentence `Mira speaks in a formal and slow manner.` Its punctuation-only critique
is deliberately disputable; the check does not establish that arbitrary human
judgments are correct.

The fixture uses the `nvidia` policy branch to exercise hosted-review safeguards,
but its model name is `offline-fixture-NOT-NVIDIA`, the run has `synthetic_qa=true`
and the workspace/objective/critique visibly identify it as synthetic. Review
provenance was generated locally for this **new test fixture**; no historical
critique was retroactively assigned trusted origins. Do not count this run as a
successful hosted generation or include it in real model-quality metrics.

The real durable LangGraph checkpoint was seeded immediately before human review;
plan, retrieval, generation and critique nodes were not executed. The synthetic
document/chunk were not indexed in Chroma. QA sessions were minted only for the
new accounts and held in browser-process memory, never printed or saved to files.
No registration email or external auth delivery was triggered.

## Live checks

All API responses below came from the real application; no backend response was
mocked. A fresh browser context used only the new QA workspace. Browser network
guards blocked external traffic and allowed writes only to this run's finding
review and explicit approval endpoints.

| Check | Observed result |
| --- | --- |
| Signed-in owner, current draft | Eligible model-origin finding; approval initially blocked |
| Anonymous audit write | HTTP 401; no record |
| Viewer catalog/write | Read-only catalog; HTTP 403 write denial |
| QA owner reads another workspace | HTTP 403 |
| Stale draft fingerprint | HTTP 409; no record |
| Approval before finding review, including proposal choices | HTTP 409 |
| Inline form with exact field, frozen quote and reason | Real POST returned HTTP 201 |
| Save without approval | Run still `awaiting_review`; original draft nonfinal/unlocked, no blueprint |
| Exact retry | Same audit ID; still one record |
| Conflicting overwrite | HTTP 409; original audit preserved |
| Approval without proposal confirmations | HTTP 409 |
| Browser reload and fresh browser context | Saved judgment, reviewer, reason, captured JSON field and quote retained |
| Select both proposals, then explicitly approve | HTTP 200; real graph completes; final artifact v2 locked |
| Reload after approval | Completed state and historical finding/audit retained; no record/approval action |
| Late audit write on completed run | HTTP 409 |
| Durable PostgreSQL graph state | Ended; final artifact ID matches persisted final row |
| Trace | Only human-review/finalize nodes; no provider node or token usage |
| Responsive layouts | No page-level horizontal overflow at 1440, 768 and 375 px |
| Browser exceptions/unexpected HTTP errors | None in final read-only verification |

Light-mode pre-approval screenshots and dark-mode completed screenshots were
captured at all three widths under the task visualization directory:
`finding-review-2026-10-13/live-reviewed-{width}.png` and
`finding-review-2026-10-13/live-final-dark-{width}.png`.
Mobile light and tablet dark screenshots were visually inspected. Prior mock
browser checks cover keyboard behavior and form/error states; those are not
reclassified as new live checks here.

### Verification-script corrections and expected responses

The stateful check was completed in stages, not claimed as a single clean
full-suite runner result:

- A browser assertion initially expected an unquoted string. The audit uses
  JSON serialization and correctly displayed `"formal, slow"`; inspected the DOM
  and verified the actual captured value on reload. No UI fix was needed.
- The completed page requests the optional human evaluation. It returns the
  documented HTTP 404: `No quality scorecard has been recorded for this run.`
  The initial response monitor treated it as unexpected. A fresh read-only run
  verified this specific contract response, completed UI, zero browser exceptions
  and no other HTTP failures. No fabricated evaluation was saved to silence it.
- Read-only diagnostics initially hit a detached ORM instance and a query using
  incorrect telemetry column names. Corrected the diagnostic scripts and reran
  them; these were not application failures and caused no database mutations.

## Persisted integrity and boundaries

Direct PostgreSQL checks confirmed:

- One audit record and one explicit approval event, both attributed to the new
  authenticated QA owner.
- One approved QA blueprint and immutable final artifact v2; durable graph ended.
- Original draft, independent critique and frozen evidence SHA-256 values match
  their pre-review values. The original draft remains nonfinal and has no
  blueprint ID; finalization created a separate final artifact.
- No NPCs or quests materialized into runtime tables for the QA workspace.
- Existing workspace data and existing checkpoints match their pre-test
  fingerprints after excluding only the new QA scope.
- Shared telemetry grew from 7,908 to 7,909 rows during the check. The sole new
  row is the already-running cleanup worker's
  `graph_pending_ingest_cleanup_run` (`database` / `pruner`) heartbeat. Excluding
  that appended row reproduces the exact original telemetry fingerprint; no
  prior telemetry row changed. The service was reused, not restarted.
- `.env` and `.env.example` SHA-256 values remain unchanged:
  `639E3F7AFAB903AA7F8323F6845C86E5977193C5430D91F9EC295461B88EF9EB` and
  `19AB99C641BAF7A63419AF8FF82553420E79D24639470EB653E840CE6BEE1A0E`.
- No NVIDIA request, dependency install, commit, push, deletion, environment
  modification or existing-workspace approval.

The new QA workspace/accounts/fixture/audit/approval/checkpoints are deliberately
retained. Cleanup would be a separate authorized action; no deletion was done.

## What this closes / what remains

Closes the missing live migration and finding-review save -> reload -> explicit
approval gate described in `finding-resolution-dashboard-2026-10-13.md`.

Does not close fresh generation usefulness, NVIDIA reliability, ingestion,
queued-worker execution (the existing deployment uses inline execution), runtime
materialization, Unity, or full-suite/production readiness. The previous bounded
191 backend and 92 mocked-browser results were not rerun or promoted to a full
backend-suite result in this turn.

The next separately scoped step is real-content acceptance of the agreed GDD
workflow, preserving the human-review audit boundary and existing workspaces.
Any new hosted generation/critique needs a fresh, bounded user authorization;
this migration authorization did not grant NVIDIA requests.
