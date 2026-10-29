# Explicit design approval without runtime release

## Implemented contract

New reviews can opt into **Design only — defer runtime integration**. The API's
strict boolean `defer_runtime` defaults to false. The choice is stored at creation
in the run's existing JSON configuration, carried through generation/revision and
critique, and included in the review fingerprint only when true. There is no
review-time switch, automatic source-text inference or retrofit of historical runs.

With this choice, only an empty, uncited runtime preview may be deferred, and all
quest runtime bindings must remain null. The other eight sections retain their
grounding/completeness requirements. Dialogue, restart, source, recovery, proposal
confirmation and independent critique checks remain effective. A conflicting
runtime claim produces a scope blocker rather than being silently discarded.

The design-quality score explicitly identifies its deferred section and explains
that runtime was not assessed. It does not score an empty preview as grounded or
complete. Normal runs retain the existing nine-section policy and legacy review
fingerprint shape.

Finalization rechecks persisted approval and stamps server-owned
`unity_runtime_preview.runtime_deferred: true` into the final snapshot and blueprint.
Model JSON cannot grant this authority. These blueprints can supply a reviewed
design brief, but cannot materialize or serve runtime data. The marker is intentionally
retained even if a materialization manifest happens to exist.

Both runtime-preview export endpoints reject deferred output with HTTP 409:

- `/api/v1/design-agent/runs/{run_id}/exports/runtime`
- `/api/v1/blueprints/{blueprint_id}/export`

Materialization and the materialized runtime-bundle service independently reject
the deferred state. A new properly reviewed runtime-enabled workflow is needed
later; this change does not add an unsafe toggle to release an old design snapshot.

## Dashboard use and design review

Select the checkbox in the normal GDD review consent dialog or the advanced
Design Agent new-run form, then confirm governed review separately. Merely selecting
the option or opening consent does not authorize or send a provider request.
It is unselected by default and fixed for the created run.

| Before | After | Why |
| --- | --- | --- |
| No way to declare postponed runtime work | One labelled, keyboard-accessible checkbox with explanatory text | Make the review scope explicit without another workflow. |
| Approved output could imply runtime readiness | Persistent design-only message and Runtime deferred status | Keep design approval distinct from client integration. |
| Runtime export/materialization actions offered normally | Disabled runtime actions; design brief remains available | Show the useful next action and avoid predictable failed requests. |

Emil design-engineering guided restraint: reused existing form, typography, focus
styles and layout; no new visual system, decoration, motion or dependencies.
Self-review kept the option in the normal flow, retained separate hosted consent,
and added Blueprint Studio status/action handling instead of relying only on the
advanced console or a disabled button. API guards remain authoritative.

## Changed areas

- Creation/response schemas and service: `backend/app/design_agent/schemas.py`,
  `service.py`; state contract: `contracts.py`.
- Scope fingerprint and quality: `review_policy.py`, `grounding.py`.
- Graph propagation and finalization: `workflow.py`.
- Hosted and local provider boundaries: `nvidia_provider.py`, `provider.py`.
- Release protection: `backend/app/services/blueprint_readiness.py`,
  `materializer_service.py`, `backend/app/api/v1/blueprints.py`.
- Dashboard: `frontend/src/lib/api.ts`, `src/app/design-agent/page.tsx`,
  `src/app/decisions/page.tsx`, `src/app/blueprints/page.tsx`.
- Regression coverage: `backend/test_runtime_deferral.py`, existing dispatch test
  in `test_revision_completeness_guards.py`, `frontend/tests/dashboard-states.mjs`.

No database migration, model selection change, environment setting, new package,
Unity change or generic exemption for missing sections was introduced.

## Verification and limits

- Final bounded backend selection: **259 passed, 3 deselected in 15.09 s**.
  Covers explicit scope, remaining design blockers, independent/raw review
  preservation, stale scope, provider-boundary and local-provider parity, both
  preview exports, materialization/runtime release, and review dispatch -> queued
  worker -> finalization for legacy and deferred runs using in-memory doubles.
- The three deselected tests require shared `db_session`. Repository conftest
  remained disabled; no shared schema reset was permitted. The first expanded run
  reported those missing fixtures, not application failures. It also exposed an
  older dispatch double missing persisted artifact fields and conflating final and
  editable-draft queries. The double and stale-finalization expectation were
  updated to match existing approval hardening; production checks were not relaxed.
- **97 dashboard fixture checks passed**, including consent/opt-in at 375 and
  1440 px, completed design-only export blocking, focus handling, and existing
  state/error/contrast checks. Minimum measured semantic-text contrast: **5.11:1**.
  A subsequently added targeted Blueprint Studio deferred-action check also
  passed separately. This is not a claim of one final 98-check full-suite run.
- TypeScript no-emit checks, scoped ESLint, and scoped Git whitespace checks passed.
- Offline backend tests disabled bytecode, plugin autoload, shared conftest and
  pytest cache; socket/PostgreSQL connections were blocked. HTTP used mocks or
  in-process TestClient; finding-audit tests used disposable in-memory SQLite.
- Browser API calls were intercepted. Existing Chromium was used without installation;
  a process-local browser-cache path was supplied after sandbox profile lookup
  failed. No project environment configuration changed.
- Read-only PostgreSQL replay confirmed the actual saved Frostpeak run still has
  its legacy scope. Its empty preview still blocks approval. A synthetic in-memory
  deferral does not clear its dialogue or restart defects.
- Saved artifact SHA-256 remains
  `4b33c1baab65696dac5513db588f0fd9b7c7d67268c08d526be5b1383705cd32`;
  saved critic SHA-256 remains
  `199b12b7fe40e9c7b21d0422ca2160b223f432c47b88196727322b4a807f37b8`.
  Environment hashes matched the baseline.

ECC AI Regression Testing guided focused boundary and provider-path parity checks.
The new contract initially failed its positive scope/schema/release checks; one
initial synthetic binding used the wrong quantity field and was corrected as a
test-fixture error, not claimed as a project defect.

No NVIDIA requests, real workflow creation/approval/materialization, saved QA-data
changes, installs, environment-file changes, commit or push occurred. The test
configuration used synthetic isolated data; no full shared-DB suite, production
build, fresh hosted generation or live runtime acceptance is claimed.

## Remaining

The actual saved draft remains unapproved. Its critic false positive/miss and fresh
generation usefulness are still open. Next, establish one corrected, human-reviewed
candidate and a clear acceptance checklist, then verify the ordinary dashboard
flow. Do not resume model switching or infer fresh NVIDIA consent from this feature
authorization. Unity remains last.
