# Proposal confirmation acceptance — 2026-10-08

Result: the database-backed approval contract passes with deterministic local provider fixtures. This does not establish NVIDIA generation quality or production reliability.

## Verified

- Real authenticated FastAPI requests enforce signed-session identity, editor/viewer roles and workspace access.
- Missing, stale, partial, duplicate and altered confirmations are rejected before a review event, job or blueprint is written.
- Inline approval and queued approval through a newly constructed worker persist exact proposal selections, draft identity/version, reviewer identity and review timestamp.
- A newer draft arriving after queuing prevents approval at the worker boundary. No review event or blueprint is created for that stale job.
- Approval uses the draft's frozen evidence even when a newer empty evidence snapshot exists. Final content retains proposal labels; historical critique/scorecard content is unchanged.
- Final design records are immutable and their blueprints are approved but not materialized. Repeated approval is rejected rather than duplicating review records.

## Scope and checks

- Added one acceptance test in `backend/test_revision_completeness_guards.py`: `test_proposal_confirmation_persists_through_authenticated_api_and_worker`. Its three scenarios cover inline, queued and stale queued approval; hosted transports are forbidden and the NVIDIA-named provider is a local deterministic fixture.
- Acceptance check: **1 passed**. Related completeness/workflow regression run: **41 passed in 15.15 seconds**, with two pytest plugin assertion-rewrite warnings. Syntax and whitespace checks passed. No Python lint/type/coverage or full-suite result is claimed.
- Fresh PostgreSQL database: `gamemind_test_proposals_20261008_a37c15`, migrated with the existing Alembic chain. Execution used `--noconftest -p no:cacheprovider` and a process-local database fixture after checking both the resolved URL database name and `current_database()`. The default conftest was bypassed because it clears the shared test schema.
- This isolated QA database and its fixture records were retained. Neither `gamemind` nor the shared `gamemind_test` schema was reset. No normal workspace approval, runtime materialization, vector ingestion, hosted request, environment edit, installation, commit or push occurred.
- `.env` and `.env.example` hashes match the pre-check baseline.
- Prior dashboard verification: 72 intercepted browser state checks plus lint, TypeScript and production build passed. At the database-only gate, browser-to-live-database approval had not been exercised together; the connected check below closes that specific gap.

## Connected browser acceptance

- Three scenarios passed against the real FastAPI routes and PostgreSQL database: browser sign-in/workspace access, proposal selection and durable approval, and stale-draft rejection/reset. Product API responses were forwarded from the QA backend, not replaced with response fixtures.
- Existing dashboard assets ran on port 3000. A temporary QA-only backend ran on port 8002 with process-local settings, a fresh JWT signing secret, deterministic provider/retrieval fixtures, outbound hosted HTTP blocked, and startup/vector ingestion disabled. No project application source or environment file changed for this check.
- Workspace: `qa_browser_proposals_20261008_78156992`. Successful run: `79fa8945-e39e-41cd-b2a2-090704097f73`. Stale-draft test run: `e45b9b1b-b419-4cbf-82c6-8cdfa9b7e952` remains awaiting review, unapproved.
- Opening consent and selecting checkboxes did not save or dispatch approval. Approval sent the displayed artifact ID and exact selections, saved one reviewer-attributed review record, and survived reload as a locked final artifact.
- A newer QA draft inserted between selection and submission produced HTTP 409 without recording review. Choices cleared; refresh showed the newer version unchecked. Selecting all proposals could not bypass its mismatched critique. Switching run history also reset unsaved choices.
- Desktop/light and 375px mobile/dark views had no horizontal overflow. The first dark-mode image caught a CSS color transition; a settled capture and computed-style check confirmed 14.76:1 contrast for New run, Refresh and Request revision. This is not a full accessibility certification.
- No browser crashes or unexpected API failures were observed. Expected responses included unauthenticated session 401, stale-review 409, missing optional evaluation 404, and canonical document-path redirects. QA health correctly displayed degraded because the vector dependency was disabled.
- SQL checks found one completed run, one unapproved review run, one authenticated approval, and no materialization, NPC or quest runtime rows in this workspace. The temporary QA backend was stopped; its isolated database records were retained.
- Initial probe failures were test-harness issues: waiting for global development-server network idle, then cross-port redirect handling in URL rewriting. The probe switched to visible/API readiness and forwarding actual QA responses. No application fix was needed.

Limitations: the source was pre-indexed by a database fixture; upload/vector ingestion, native deployment URL/CORS behavior, queued browser approval, fresh model output quality, load and production readiness were not established here. Queued approval was covered by the preceding real database/worker test.

Next gate: fresh generation-quality review with renewed, bounded NVIDIA consent. Keep results isolated; do not approve or repair saved CyberRakshak QA drafts or materialize runtime data as part of that check.
