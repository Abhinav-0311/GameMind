# Finding-review audit — chunk 1

## Scope

Record an evidence-backed human assertion that a critic finding is not a defect.
This chunk does **not** dismiss a finding for approval, alter an AI verdict, resume
the graph, generate a new draft, confirm proposals or approve runtime content.
Reviewer assertions are not source facts or proof that the critic is wrong.

## Contract

`GET /api/v1/design-agent/runs/{run_id}/artifacts/{artifact_id}/finding-resolutions`
returns the raw finding catalog, content fingerprints and separate audit records.
`POST` to the same route records one assertion. It requires an authenticated
workspace owner/editor, the exact critique ID, draft/critique/evidence SHA-256
fingerprints, the server-issued finding ID, a substantive reason, an existing
artifact JSON pointer and an exact quotation from the draft's frozen evidence.

Writes are restricted to the current non-final, non-immutable draft at an
`awaiting_review` checkpoint. The server captures the field value, original
finding, draft version, evidence snapshot, authenticated actor and timestamp.
Responses explicitly say `approval_effect: none`.

Exact retries return the existing record. Conflicting retries cannot overwrite
it. There are no update/delete endpoints. Composite foreign keys bind records to
the same project/run/artifact/critique. Deleting a user preserves the audit label.
Database administrators are not prevented from editing records directly; this
is append-only at the application API, not a tamper-proof audit ledger.

## Implementation

- New service: `backend/app/design_agent/finding_reviews.py`.
- Separate `DesignAgentFindingResolution` table and strict API schemas.
- Existing final approve/reject review events remain unchanged.
- Migration `d2e4f6a8b901` follows `c6e7f8a9b0d1`.
- No changes to provider prompts, configured models, environment files,
  approval validation, worker behavior, or frontend.

## Verification

- Valid RED: all 24 initial API cases failed because the new route was absent.
- Initial GREEN: the same 24 cases passed against disposable in-memory SQLite.
- Final adjacent regression run: **158 passed**, no deselections, in 8.44 seconds.
  Includes database-level cross-workspace rejection in disposable SQLite.
  Included the new API, frozen evidence, provider,
  quest state-contract, phase-3 contract and generation-quality tests.
- Offline PostgreSQL migration SQL compiled successfully; checked the scoped
  foreign keys, user-deletion behavior, evidence restriction and single head.
  **No live migration was applied.**
- PostgreSQL connection and outbound HTTP guards were active during container
  tests. Tests used `--noconftest -p no:cacheprovider`; no application lifespan,
  shared-schema reset, NVIDIA request or live QA data write was performed.
- The Windows API runner hung before returning test results and was stopped;
  successful API verification used the existing Linux backend container.
- Coverage tooling is unavailable in the container and local venv. No package
  was installed, and no coverage percentage or full-suite result is claimed.

## Remaining work

1. Apply/revalidate the migration only when explicitly authorized; new endpoints
   are not deployment-ready against an unmigrated database.
2. Chunk 2 backend policy is now implemented and isolated-tested; see
   `finding-resolution-policy-2026-10-13.md`. This storage chunk alone never
   establishes model-vs-server origin. Server blockers and unconfirmed proposals
   remain non-dismissible; existing legacy QA critiques are not retroactively tagged.
3. Chunk 3: integrate the existing dashboard critique/evidence panels and verify
   the actual user flow. No browser/UI acceptance is claimed here.

The saved Frostpeak finding and its 18 unconfirmed proposals remain unresolved
for runtime approval. Do not copy QA metadata into an approval decision.
