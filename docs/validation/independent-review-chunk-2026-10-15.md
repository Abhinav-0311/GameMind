# Independent review and design-only acceptance chunk

## Scope delivered

- Fresh governed critique requests omit only section-level `warnings` and `confidence`. Evidence, content, citations, record assumptions, integration notes, dialogue, quest contracts and original JSON pointers remain available. Legacy critique projection is unchanged.
- Saved artifacts are not rewritten. Review provenance and approval validation still bind to the complete original artifact, including excluded metadata; changing that metadata after review invalidates provenance.
- Fixed repeated actionable validation treating digits in declared bookkeeping IDs inside helper notes as unsupported gameplay quantities. Only declared underscore-form identifiers are removed from the notes' numeric scan. Actual action values, unsupported numeric mechanics and undeclared numeric identifiers remain checked. Notes and source content are never edited by that scan.
- Brief export binds source document IDs as UUID objects, consistent with its citation lookup. This corrects the strict UUID binding failure observed in the isolated SQLite flow; it is not evidence that a production PostgreSQL export failed.

## Local proof

**494 selected tests passed, 5 shared-database fixture cases deselected**, with one existing Starlette/AnyIO deprecation warning. The selection includes 27 existing audit-API tests not previously selected and three new regressions; it does not mean 30 new tests were added. It is not a full backend-suite or coverage result.

New checks in `backend/test_independent_critic_boundary.py` verify:

1. A real adapter request with mocked HTTP excludes generator self-assessments, preserves content/evidence and retains original-artifact provenance. Later metadata changes invalidate the stored review.
2. Revalidating a freshly assembled draft is idempotent despite generated numeric IDs. Unsupported quantities in notes/actions and undeclared numeric IDs remain rejected.
3. The normal FastAPI and LangGraph design workflow, with synthetic indexed source data, mocked retrieval/NVIDIA responses, disposable SQLite and in-memory checkpoints:
   - rejects missing hosted consent before making any model call;
   - persists a draft and independent critique, then pauses for review;
   - rejects a duplicate active run and pre-approval export;
   - rejects approval without required proposal confirmations;
   - accepts explicit confirmation and design approval, creates an immutable final artifact and approved blueprint, and leaves the draft unchanged;
   - exports a brief containing its source title;
   - rejects runtime export because the run explicitly defers runtime integration;
   - rejects duplicate approval without additional model/retrieval calls.

The guarded runner disabled shared conftest, cache, bytecode and plugin autoload; PostgreSQL/external connections were blocked, and HTTP was mocked. The API test adapts one PostgreSQL document-ID array-containment expression to SQLite solely inside its disposable fixture. It does not verify native PostgreSQL containment, durable PostgreSQL checkpoints, real ingestion, live NVIDIA content quality or browser behavior.

Read-only replay preserved historical QA failures and original hashes, retained three failure-predicate plus six dialogue-stage blockers, and prevented approval from an empty model review. Existing-row fingerprints matched across 39 tables. Environment hashes were unchanged; backend health returned 200.

## Remaining acceptance gate

No NVIDIA requests, saved-workspace changes, runtime approvals, migrations, installs, commits or pushes occurred in this chunk. The model configuration and 1,024-token critic cap are unchanged. Removing generator self-assessments is an input-boundary correction, not proof of a causal improvement in model judgment.

The next gate is fresh, bounded hosted acceptance against the unchanged saved draft/evidence, followed by a normal dashboard generation/review flow using genuinely acceptable content. Local scripted approval/export is not a claim that real AI generation or production reliability is complete. Do not weaken blockers or retrofit historical failed outputs to obtain that proof.
