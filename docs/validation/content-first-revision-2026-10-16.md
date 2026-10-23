# Content-first scoped revision

## Implemented

Contract-2 NVIDIA revision now uses the same content-first approach as generation. The model returns objective/completion-action pairs, readable failure causes, an explicit restart action and dialogue stage/quest-index mappings. It does not regenerate state contracts, objective flags, eligibility objects or manual tests.

Existing quest IDs and dialogue triggers are selectors for existing records. Foreign/duplicate selectors fail assembly; null selects a new record/line, whose key is allocated locally without reusing existing keys. Unchanged objective text retains its flag/event pair, including after reordering. The backend builds completion/failure/restart bookkeeping and dialogue eligibility, then validates references against the entire draft. Only selected sections are merged; unselected content is not normalized or rewritten. Existing freshness state remains server-owned.

Revision prompts retain original human requirements, the rejection reason, citations, source text, assumptions and authored integration guidance. Exact server-generated duplicate notes are removed from the projection, not from saved artifacts. NPC-only edits receive read-only quest context. Contract-1 revision and dialogue-patch behavior remain on their existing paths.

Invalid governed revision fields are rejected without asking a format-repair model to invent missing content. Existing syntax-repair preservation checks remain in effect. Assembly failures are sanitized and retain available provider diagnostics. No approval, provenance, runtime-deferral or quality gates were relaxed.

## Verification

- **565 selected offline tests passed; five shared-database fixture cases deselected; one existing Starlette/AnyIO warning.** This adds eleven focused cases, not 565 new tests. It is not a full-suite or measured-coverage result.
- Checks cover exact source/input preservation, selected-section boundaries, reordered records, stable IDs/flags, newly allocated keys, unknown/duplicate selectors, absent quest/failure references and invalid schema responses without content repair.
- The existing controlled API acceptance case now exercises generation → rejection → content-first NPC revision → fresh mocked critique → explicit proposal confirmation → design approval → brief export. It verifies old drafts and unselected quests remain unchanged, frozen retrieval is reused, duplicate approval is rejected, and deferred runtime export remains blocked. HTTP is mocked; the database and checkpoints are in memory.
- The native JSON Schema compiled with installed Ajv. A valid content response and five invalid controls were checked; this does not verify NVIDIA's live decoder behavior.
- A read-only capture replay of the saved failed Frostpeak run reduced its revision user-message size from **30,761 to 19,372 characters (37.0%)**. That measures characters, not tokens, latency, cost or generation quality. The saved failure and its closed six-request ledger remained unchanged.
- Existing application fingerprints matched across all 39 tables, with historical telemetry bounded by the original cutoff. Environment hashes were unchanged; backend health returned 200. Whitespace checks passed.

Ponytail kept this in the existing adapter/assembler and extended the existing normal-flow test rather than creating a new revision service or workflow.

## Limits and next gate

No NVIDIA calls, installations, model/environment changes, existing application-workspace data changes, migrations, commits or pushes occurred. No frontend code changed; browser/build checks were not repeated. Dedicated Python lint/type tools were unavailable and were not installed.

Fresh hosted revision quality is still unverified. The historical failed run was not converted into a success or approved. Source-silent sections such as Frostpeak NPC memory still require an explicit input/scope decision; this change does not fabricate missing facts or weaken completeness to obtain approval. The next acceptance gate is a newly bounded hosted check of this smaller revision contract and its independent critique.
