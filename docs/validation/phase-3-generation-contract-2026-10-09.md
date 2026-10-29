# Phase 3 focused generation fixes

Status: implementation and local verification complete. Fresh hosted-generation acceptance is still open; do not advance on test counts alone.

## Changes

- NPC generation now requests one set of spoken lines in `dialogue_triggers`. The existing Pydantic contract derives omitted `dialogue_hooks` locally; explicit mismatched hooks in historical drafts still fail validation. Server-derived hooks and manual tests remain in saved artifacts but are omitted from the model-facing JSON schema.
- The normal run form accepts explicit fresh-dialogue intent and an optional shared repeat/reset policy (10–240 characters). The policy is stored in the run's existing JSON configuration and applied verbatim to each mapping during generation and revisions; manual tests are regenerated from the applied policy. It is human direction, not a GDD fact. A fixed policy requires a new run to change.
- Existing source-reuse warnings block approval when fresh dialogue was explicitly requested. This applies to the API and worker/finalization paths, including the local/mock provider. Confirming proposals cannot dismiss this blocker. No new score framework was added.
- Existing generation/revision prompts require final success to depend on all recorded required actions, plus concrete proposed failure/restart Event/State/Check notes. Unfinished objectives alone are not a failure event; source-unspecified ordering and controls remain proposals.

## Verification

- Three grouped regressions in `backend/test_phase3_generation_contract.py` reproduced failures before the edits and pass afterward. They cover schema/legacy alignment, immutable policy and fresh-reuse approval rejection, bounded API input, real workflow callbacks using an in-memory database double, and quest prompt requirements.
- Focused offline regression selection: 166 passed, 5 database-dependent cases deselected. This is not a full backend-suite result. Tests used `--noconftest -p no:cacheprovider` to avoid the normal test-schema rebuild.
- TypeScript, targeted ESLint and the frontend production build passed.
- All 74 existing/extended mocked dashboard state checks passed. The two new mobile/desktop form checks verify keyboard operation, policy validation, correct request fields and no submission before consent. All backend actions were intercepted. Minimum measured semantic-text contrast across the suite: 5.11:1.
- The running backend's public OpenAPI schema exposes both new request fields.
- Saved QA run `ada62fd0-40a8-48f8-9337-c766fb387665` was read without writes: its original ambiguous output still fails. A clearly labelled in-memory projection omitting the now-derived hooks produces aligned lines and preserves the fixed policy. This is a counterfactual contract check, not repaired or fresh model output.
- No hosted inference, model/env change, installation, migration, commit, push, approval or runtime materialization in this work. Environment-file hashes remain unchanged. The existing frontend dev server was started for browser checks.

## Remaining acceptance gate

One PATCH profile, three genuinely fresh useful warnings with matching situations and the agreed reset policy, and one Firewall Fortress quest with independently necessary actions, combined success and concrete failure/restart transitions must pass semantic review on a fresh response. The earlier bounded NVIDIA authorization is exhausted; this work did not reuse it.

Exact/source-normalized reuse detection does not prove originality or catch every superficial paraphrase. Prompt checks do not prove the model follows quest instructions. Profile claim support, voice, semantic fit and integration usefulness still need actual output review. No claims of runtime playtesting or production reliability.

## Repeat locally

From `backend`:

```powershell
.\.venv312\Scripts\python.exe -B -m pytest --noconftest -p no:cacheprovider test_phase3_generation_contract.py -q
```

From `frontend`, against the running dashboard:

```powershell
$env:DASHBOARD_TEST_URL='http://127.0.0.1:3000'
$env:DASHBOARD_TEST_FILTER='Phase 3'
node tests/dashboard-states.mjs
```
