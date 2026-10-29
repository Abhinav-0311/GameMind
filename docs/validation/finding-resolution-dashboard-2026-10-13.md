# Finding review dashboard — chunk 3

## Status

Follow-up: the authorized migration and isolated real database/browser acceptance
are now complete. See [live acceptance](finding-resolution-live-acceptance-2026-10-13.md).
The implementation-stage snapshot below is retained as historical evidence.

UI and backend read contract implemented; isolated verification passed.
**Live database-backed acceptance is pending migration authorization.**
No NVIDIA calls, migration, live QA-data writes, environment edits, package
installation, commit or push were performed.

## User flow

The existing Design Agent critique panel now supports:

1. See the original AI finding, severity and recommendation, unchanged.
2. For a known-origin model finding, select **Review finding**. Only authenticated
   workspace owners/editors at the current unapproved checkpoint can record it.
3. Select the exact draft field. Read its current value beside the frozen source
   excerpt; paste an exact supporting quote and explain why it is not a defect.
4. **Record human review** saves the separate assertion only. It does not resume,
   approve, confirm proposals, generate content or call NVIDIA.
5. Reloaded server policy shows **Human-reviewed, not AI-verified** when the
   resolution applies. The original AI verdict remains visible. The audit disclosure
   includes the reviewer, timestamp, judgment, reason, captured field and quote.
6. Proposal confirmation and explicit **Approve run** remain separate. Real
   approval revalidates the persisted draft, evidence, critique and resolutions.

System blockers and unknown/legacy/stale origins are not dismissible. Incomplete
historical drafts remain readable but cannot gain approval eligibility through
the preview. A negative critic verdict without findings is not overridden.

## Implementation

- `frontend/src/components/DesignFindingReviews.tsx`: inline form and separate
  audit disclosure; no new page, dialog library or independent AI workflow.
- `frontend/src/app/design-agent/page.tsx`: version-bound policy state and approval
  display; existing hosted-scorecard and proposal requirements remain independent.
- `frontend/src/lib/api.ts`: typed, workspace-scoped read/write methods.
- Backend finding catalog adds server-derived origin, eligibility, applicable
  resolution status, actor write permission, frozen snapshot ID and critique-blocked
  status. Preview and actual approval share the same policy helpers.
- Missing audit storage returns a safe 503, not a SQL error or fabricated success.
- Responses must match the displayed artifact/critique/findings. Frozen evidence
  must match both the artifact and catalog snapshot. Stale saves block and offer
  an explicit reload; no optimistic approval or silent overwrite.

## Design review and iteration

The Emil design skill guided restraint, hierarchy and keyboard continuity; the
browser-QA skill guided responsive, theme, interaction and error-state checks.

| Before | After | Why |
| --- | --- | --- |
| Static critique with no evidence-backed human review | Review lives beside the finding, in the existing panel | Keeps one understandable workflow |
| Raw technical field labels and inconsistent form controls | Shorter record/field labels, existing theme surfaces and focus rings | Improves hierarchy and learnability without decoration |
| Form open/cancel could lose keyboard position | Focus enters the field selector; Escape/Cancel restores the trigger | Accessible continuity without unnecessary motion |
| Potential confusion between dismissed AI finding and approval | Original verdict retained; human assertion, proposals and approval are distinct | Reduces false trust and accidental approval |

## Verification

- Backend RED: five initial catalog tests failed for absent policy/permission fields.
- Browser RED: the record-flow test failed because **Review finding** was absent.
- Final bounded backend regression set: **191 passed**, no deselections, **15.28 s**.
  Same eight test files as chunk 2, with six additional catalog/error cases.
- Full existing dashboard-state browser script: **92 passed**. Includes 12 new
  finding-review scenarios. After visual polish, those **12 passed again**.
- Browser coverage: record -> reload -> separate approval at 1440/768/375px;
  invalid exact quote; viewer/anonymous read-only; legacy/system findings; stale
  catalog; unavailable service and retry; save conflict; independent proposal
  confirmation; wrong frozen snapshot; keyboard entry and Escape focus return.
- Light/dark form label contrast passed the 4.5:1 threshold at all three widths.
  Existing broader semantic-text checks measured a **5.11:1** minimum. Screenshots
  were generated and desktop-dark/mobile-light forms visually inspected, then
  control styling and field labels were improved and the scenarios rerun.
- TypeScript `tsc --noEmit --incremental false` and scoped ESLint passed. No
  production build was run against the active dev server's `.next` directory.
- Backend tests used disposable SQLite/mocks, HTTP/PostgreSQL guards, bytecode
  disabled, `--noconftest -p no:cacheprovider`. No shared schema reset/app lifespan.
- Browser tests intercepted every API request and blocked unexpected mutations
  and external traffic. All approval/record POSTs were simulated fixtures, not
  real application acceptance. No browser page errors or unexpected requests were
  reported by successful checks. Fonts used the offline OS fallback.
- One backend warning: anyio was already imported and could not be assertion-
  rewritten. No full backend-suite, coverage percentage, production-performance,
  automated axe audit or fresh generation-quality claim is made.
- `.env` and `.env.example` hashes match the chunk-2 baseline; unrelated dirty
  worktree changes were preserved.

## Live deployment gate and next step

A read-only database query confirmed:

- Current Alembic revision: `c6e7f8a9b0d1`.
- `public.design_agent_finding_resolutions` does **not** exist.
- Prepared migration: `d2e4f6a8b901`; not applied.

The dashboard dev server already answers at `http://127.0.0.1:3000/design-agent`.
An initial sandbox start failed due access restrictions; the existing listener
was subsequently identified and reused, not restarted or replaced.

With explicit authorization, apply the prepared migration using the existing
deployment process and verify the live schema. Then, in a new isolated local QA
workspace, exercise the real record -> reload -> explicit approval gate, including
permission denial, stale data and unconfirmed proposals. Do not use this as
authorization to approve an existing game workspace or send data to NVIDIA.

Existing Frostpeak QA critiques were not retroactively assigned trusted origins;
their previous runtime blockers and unconfirmed proposals remain unchanged.
