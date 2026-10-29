# Finding resolution approval policy — chunk 2

## Outcome and limits

An evidence-linked human resolution can now inform a later **explicit approval**
at the API (inline or queued), worker human-review and finalization boundaries.
Recording a resolution alone still does not approve, resume, generate, confirm a
proposal or materialize anything. `approval_effect: none` on the recording API
describes that immediate action, not whether a later approval may consider it.

This is human adjudication, not proof of semantic correctness. A valid quote and
field pointer establish what the reviewer inspected; they cannot prove that the
reviewer's conclusion is right. Raw model findings and verdicts remain unchanged.

## Narrow policy

- The NVIDIA adapter captures its validated raw critique before deterministic
  findings are appended. The workflow persists server-generated provenance in a
  JSON sidecar, bound to the exact draft, frozen evidence and original request.
  Model-supplied origin fields are discarded. No new schema migration is needed
  for this sidecar.
- Only that known-origin model finding can be excluded in an in-memory approval
  projection. Legacy/unknown-origin, recovered and fallback reviews do not gain
  dismissal eligibility. Existing saved QA critiques are not retroactively tagged.
- Every considered resolution is rechecked against scope, IDs, draft version,
  all content fingerprints, original finding, captured field value, exact frozen
  quote, recorded authenticated actor, reason and timestamp.
- A negative raw verdict requires all its reported model findings to be resolved.
  A negative verdict with no findings is not overridden. Ordinary ready reviews
  retain the existing severity policy.
- Deterministic findings are recomputed after filtering model findings, including
  when a model duplicated a deterministic finding. Structural checks, citations,
  original-request coverage, quest consistency, freshness and explicit proposal
  confirmation remain enforced by the existing pure approval validator.
- Worker and finalization gates reload the scoped saved critique/evidence and
  reject checkpoint content that differs from the persisted review. Neither API
  input nor queued state supplies a trusted list of dismissed finding IDs.

Implementation: `backend/app/design_agent/review_policy.py`, NVIDIA adapter
metadata, workflow critique persistence and the three approval boundaries.

## Verification

- RED: 18 initial policy cases failed because the policy module was absent.
- Final bounded regression set: **185 passed**, no deselections, in **12.77 s**.
  The policy file contributes 27 cases; the earlier audit API contributes 27.
- Covers positive human resolution, partial/legacy/dirty/stale resolution rejection,
  quote/value/actor/version mismatches, proposal blockers, deterministic blockers
  (including model duplicates), unexplained negative verdicts, checkpoint mismatch,
  model-origin spoofing and workflow provenance persistence.
- API inline/queued tests exercise the real gate with isolated SQLite and stub
  downstream dispatch. Worker/finalization tests exercise the real gate and stop
  before review-event or runtime writes. This is boundary verification, not a live
  completed approval or production reliability claim.
- Updated existing boundary-test doubles to include actual artifact scope and
  immutability fields and separate final/draft lookups. Original request-coverage
  and fresh-dialogue rejection assertions remain intact.
- Test files: `test_design_finding_resolutions.py`, `test_finding_approval_policy.py`,
  `test_design_agent_evidence.py`, `test_nvidia_design_agent_provider.py`,
  `test_design_agent_llm_provider.py`, `test_quest_state_contract.py`,
  `test_phase3_generation_contract.py`, `test_generation_quality_guards.py`.
- Existing Linux container; outbound HTTP and PostgreSQL guards active;
  `--noconftest -p no:cacheprovider`, bytecode disabled. No app lifespan, shared
  test-schema reset, NVIDIA request, live migration or live QA-data write.
- One pytest warning: anyio was already imported and cannot be assertion-rewritten.
  No full-suite, browser, live PostgreSQL, coverage-percentage or hosted-generation
  acceptance is claimed. Coverage tooling remains unavailable; nothing installed.
- `.env` and `.env.example` hashes match the chunk-1 baseline. No commit or push.

## Next: chunk 3 and deployment verification

Chunk 3 UI and isolated verification are now implemented; see
`finding-resolution-dashboard-2026-10-13.md`. Live acceptance still needs the
prepared migration. The steps below remain the deployment/acceptance boundary,
not a claim that the live flow has passed.

1. Integrate eligible finding review and audit status into the existing dashboard
   critique/evidence panel. Distinguish human-reviewed from AI-verified and keep
   proposal confirmation separate. No new dashboard or independent AI workflow.
2. Apply/revalidate prepared migration `d2e4f6a8b901` only with explicit migration
   authorization. The recording endpoints and resolution-dependent approval are
   not deployment-ready against an unmigrated database.
3. Browser-test record -> reload -> explicit approval gating, including anonymous,
   viewer, stale, deterministic-blocker and unresolved-proposal cases, in isolated QA.
4. Any new hosted critique/generation requires fresh bounded NVIDIA consent.

The saved Frostpeak QA critique and its 18 unconfirmed proposals remain unchanged;
this chunk does not approve that run or establish fresh creative-generation quality.
