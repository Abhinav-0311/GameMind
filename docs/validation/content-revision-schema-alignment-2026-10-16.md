# Content-revision schema alignment — 2026-10-16

## Completed local chunk

The revision response schema now matches the existing server-owned identity and readable-action rules. The raw Frostpeak QA failures remain immutable failures; they were not edited into passing artifacts.

### Implemented

- `content_revision_model(targets, artifact)` now receives the frozen artifact. Existing quest IDs are literal selectors or null for a new quest. Existing NPC trigger selectors are constrained to the named NPC; a new/renamed NPC can return only null mapping selectors. Null mappings still receive unique backend-allocated keys.
- The existing citation-grounding schema helper preserves each NPC selector variant instead of losing identity restrictions while adding citation restrictions.
- One shared `QuestEventAction` annotation exposes the existing three-to-1000-character/two-word action requirement in JSON Schema as well as local validation. It covers objective completion actions, proposed failure causes, restart actions and governed event actions. This is structural readability, not semantic correctness.
- A historical single-word failure label may use its already-saved readable action in the revision projection. The existing event key is retained through the saved action lookup; no action or fact is invented and the original artifact is not changed.
- The content-first prompt explicitly says to copy existing selectors or use null, never invent an identity.
- The existing bounded unfinished-progress check now covers the observed “fewer than 5 ... extracted from ...” wording. Paired deadline and negation controls avoid classifying those particular alternatives as bare unfinished-progress failure. This remains a narrow English check, not general semantic validation.
- Final ownership, duplicate/reference checks, selected-section merging, provenance, proposal confirmation, consent, runtime deferral and approval gates remain in place. No model, token, retry or environment configuration changed.

### Files touched by this chunk

Production: `backend/app/design_agent/content_draft.py`, `contracts.py`, `nvidia_provider.py`, `grounding.py`.

Tests: `backend/test_content_revision.py`, `test_design_contract_v2.py`, `test_independent_critic_boundary.py`.

This extends the existing assembler/provider/tests. No new production service, dependency, endpoint or workflow was introduced. Fourteen focused cases were added to existing test modules; 579 is the selected regression total, not the number of new tests or a count of the entire backend suite.

## Verification and exact coverage

1. Red/green:
   - Initial new context/compatibility tests: nine failures against the previous implementation.
   - The observed fewer-than-five predicate test failed separately before its focused guard fix.
   - Final selected offline run: **579 passed, five database-fixture cases deselected, one existing Starlette/AnyIO deprecation warning, 22.04 s**.
2. Identity checks:
   - foreign quest IDs, invented trigger IDs, another NPC's trigger and renamed NPCs attempting to keep old triggers reject before assembly;
   - existing and null/new selectors validate, including new records and stable IDs after reordering;
   - citation-grounded response models retain the same ownership restrictions;
   - invalid governed responses do not trigger semantic format-repair requests.
3. Native JSON Schema:
   - installed Ajv compiled the actual grounded revision schema;
   - nine valid/invalid controls passed, including null/new records, owned selectors, foreign/cross-NPC selectors and unreadable completion/failure/restart actions;
   - this does not prove NVIDIA's live decoder obeys the updated schema.
4. Saved raw failure replay:
   - the first complete saved response rejects at the identity schema boundary;
   - the third complete saved response rejects at the readable-action schema boundary;
   - no response was transformed into an acceptable candidate. Both accounting ledgers remain closed; no new hosted requests were sent.
5. Existing controlled API acceptance was extended, not replaced:
   - consent required before mocked NVIDIA generation;
   - generation and independent mocked critique;
   - one scoped NPC + quest revision, including a null new completion mapping and explicitly proposed abandonment failure;
   - fresh mocked critique, explicit proposal confirmation and design-only approval;
   - immutable approved artifact and successful technical-brief export containing the revised dialogue and failure guidance;
   - original artifact/unselected sections unchanged, frozen retrieval reused once;
   - deferred runtime export and duplicate approval both reject.
   - This uses the real API/provider/workflow with HTTP MockTransport, disposable SQLite and in-memory checkpoints. It is not browser, hosted generation, or native PostgreSQL acceptance.
6. Integrity:
   - all 39 application-table fingerprints match the pre-QA baseline; historical telemetry comparison is bounded by the recorded cutoff;
   - historical failed QA artifact/ledger unchanged; its new revision QA still has one copied artifact, zero critiques and zero approved blueprints;
   - saved QA results/report hashes unchanged;
   - `.env` and `.env.example` hashes unchanged;
   - backend/database/Chroma health healthy;
   - syntax parsing passed for all seven touched Python files; scoped whitespace check passed.

Offline tests disabled shared conftest, pytest cache and plugin autoload, denied PostgreSQL connections and external sockets, and permitted only mocked HTTP/TestClient traffic. Shared-schema fixture rebuilding was never run.

## Not established / remaining risks

- No NVIDIA calls, browser walkthrough, frontend build, fresh full generation, real independent critique or live approval/export occurred in this chunk.
- No full backend-suite or measured coverage claim. Ruff, Pyright, coverage and pytest-cov are absent locally and were not installed.
- Numeric presence checks and the unfinished-state regex do not prove quest semantics. Proposed faction dialogue, unsupported gameplay specifics, voice and useful integration guidance still need independent review against the GDD.
- The new literal/union schema still needs a newly authorized hosted check. JSON Schema acceptance locally is not live decoder proof.
- Broad six-section revisions may still truncate at the unchanged per-call allowance; this chunk did not raise token settings or switch models.
- Frostpeak NPC memory is genuinely unspecified. No missing facts were fabricated and no completeness/approval gates were relaxed.
- Existing dirty-worktree changes were preserved. No migrations, production-data writes, installs, commits or pushes were performed.

## Next acceptance gate

Use the existing selected-section revision flow for one coherent NPC/quest correction in new QA isolation, then inspect fresh independent critique. Any new hosted requests require a fresh bounded authorization because the prior three-request budget is closed.

Do not equate another passing safety test with useful generated output. Full product acceptance still requires a genuinely acceptable normal-flow generation followed by explicit design approval and successful brief export; runtime remains deferred.

Ponytail kept the fix in four existing production files and reused the existing API acceptance test. Python Testing provided red/green controls; Verification Loop separates offline contracts, integrity checks and outstanding live evidence.

