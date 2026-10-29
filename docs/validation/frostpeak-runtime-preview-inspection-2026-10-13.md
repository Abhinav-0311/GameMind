# Frostpeak runtime preview inspection — FRESH-05

## Outcome

The saved preview is empty with Low confidence, no citations and explicit missing
integration warnings. That is not evidence of broken Unity code. The saved request
requires quest `runtime: null` and forbids invented engine IDs. The three retrieved
excerpts routed to the preview describe game lore, quest mechanics and world-state
flags, not a concrete client integration. Retrieval routing is not entailment.

The confirmed product-policy mismatch is that design approval requires all nine
blueprint sections to be nonempty and cited, including the runtime preview. An
honest deferred/unsupported preview therefore blocks dashboard design approval.
Changing that policy has implications beyond filling one generated field; no
production code or saved QA data was changed in this inspection.

## Evidence and boundaries

- Saved QA run `4c05934b-40d6-4a0e-8ac9-0df311a09129`, artifact
  `cea14acb-54e2-4898-bdf0-3c4585b48344`: preview content `{}`, citations `[]`,
  confidence `Low`, warnings asking for human integration input.
- `backend/app/design_agent/nvidia_provider.py`, `generate`: the section guide
  describes `integration_notes` as a cited platform/client plan, not proof of
  deployed bindings. Other unsupported sections may remain empty with warnings.
- `backend/app/design_agent/contracts.py`, `BlueprintContent`: the preview remains
  a required section, but its content is an unrestricted dictionary. Quest runtime
  bindings are separate from this section; `runtime: null` does not itself require
  the entire preview to be empty. A genuinely supported integration plan could
  belong here without invented engine IDs.
- `backend/app/design_agent/grounding.py`, `assess_artifact_quality`: every section
  participates in grounding and completeness. An empty uncited preview fails both
  and integration readiness. `complete_design_critique` adds a High empty-section
  finding, and `validate_design_approval` recomputes the gates.
- `backend/app/design_agent/service.py`, `runtime_export`: returns the finalized
  preview's content after `_final_blueprint` requires an immutable final artifact.
  This export is not the materialized, readiness-gated runtime bundle.
- `backend/app/services/materializer_service.py`, `get_runtime_bundle`: separately
  requires approved/materialized/current usable content and project-scoped records.
  Quest materialization skips `runtime: null` rather than inventing bindings.
- `backend/app/design_agent/workflow.py`, `_finalize`: successful design approval
  produces an approved blueprint and immutable final snapshot. It does not itself
  materialize runtime records.
- `backend/app/services/blueprint_service.py`, `_generate_unity_preview`: the local
  extractor assembles a summary of extracted sections. Its mock-shaped preview is
  not proof that a hosted model produced useful client integration or that a game
  client can consume it.

These conclusions concern the saved retrieved evidence, not a claim that every
document in the project has been exhaustively searched for integration details.
No browser walkthrough or game-client execution was performed in this step.

## Verification

- Re-read the complete saved artifact, critique and frozen evidence in a PostgreSQL
  read-only transaction, then rolled back. Verified the preview's exact empty,
  uncited, Low-confidence state and all saved quest runtime bindings remaining null.
- Current local assessment blocks the actual draft on Grounding, Completeness,
  Integration readiness and Request coverage. Dialogue and restart defects remain
  in that stored draft; prior fixes detect them but did not rewrite it.
- Isolated the preview in the existing structurally complete in-memory test shell:
  it alone appears in `incomplete_sections` and `unsupported_sections`, causing
  Grounding, Completeness and Integration readiness blockers. This confirms the
  approval-policy coupling independently of the dialogue/restart defects.
- A synthetic ready critic still receives a High preview-empty finding. Confirming
  all existing assumptions does not bypass current approval checks.
- Existing focused empty-section/critique regressions: **7 passed, 22 deselected
  in 0.71 s**. No new tests were added. These are not a full-suite result or an
  additional total to combine with the previous 219-test run.
- Tests disabled bytecode, plugins, shared `conftest.py` and pytest cache, blocked
  socket/PostgreSQL connections, and allowed only mock/in-process HTTP transport.
- Saved artifact SHA-256 remained
  `4b33c1baab65696dac5513db588f0fd9b7c7d67268c08d526be5b1383705cd32`;
  saved critique SHA-256 remained
  `199b12b7fe40e9c7b21d0422ca2160b223f432c47b88196727322b4a807f37b8`.
  Environment hashes also matched the baseline.

ECC AI Regression Testing guided reuse of existing empty-section checks rather
than adding another guard or increasing the test count without a new code defect.
No NVIDIA calls, source-code edits, environment changes, installs, database writes,
runtime approval/materialization, commit or push occurred. Only this note was added.

## Recommended decision before implementation

Separate **reviewed design approval** from **runtime readiness**. Permit the runtime
preview to be explicitly deferred for a design-only review, while retaining visible
missing integration input and blocking any claim that its export is client-ready.
Do not silently exempt every missing section, treat warnings as approval authority,
or fabricate a cited preview from merely similar retrieval results.

This requires an agreed explicit deferral/approval contract, not an empty-object
exception. API approval, independent/system findings, finalization, dashboard status,
exports and runtime release must agree. Historical reviews and saved approvals must
not be silently reinterpreted. Existing dialogue/restart/grounding blockers in
required design sections must remain effective.

Before adopting it, verify: undeclared empty preview still blocks; declared deferral
does not hide other defects; stale reviews cannot unlock approval; design-approved
but unbound quests cannot become runtime records; runtime exports clearly identify
their design-only status; real runtime bundles retain their release gates.

Do not implement Unity now. Fresh model generation and critic semantic acceptance
remain separate open work and require new bounded hosted consent.
