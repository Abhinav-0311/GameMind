# CyberRakshak Local Acceptance Walkthrough

Date: 2026-07-21

## Scope

This walkthrough exercised the local GameMind stack against the CyberRakshak
sources in a fresh workspace. It is an evidence record, not a claim that the
generated design is automatically correct.

## Clean Acceptance Result

Workspace: `cyberrakshak-acceptance-20260721-142146`

1. Uploaded `cyberrakshak_gdd.md` as the primary GDD (17 chunks).
2. Uploaded `cyberrakshak_technical_brief.md` as a technical brief (5 chunks).
3. Uploaded `cyberrakshak_runtime_extension.md` as a runtime/quest companion (5 chunks).
4. The GDD review identified three missing decisions: MVP delivery scope, online
   feature boundary, and accessibility.
5. The technical brief was attached as explicit evidence for all three decisions.
6. Generated a blueprint from the runtime extension with the GDD and technical
   brief as supporting sources.
7. Approved and materialized the blueprint.
8. Verified the runtime bundle contains `jay`, `patch`, and `adi`, plus these
   three quests:
   - Training Sandbox Orientation
   - Password Vault Evidence
   - Phishing Office Warning

The Markdown technical-brief export and JSON runtime export endpoints both
returned HTTP 200 during the walkthrough.

## Product Findings

### Useful

- The review correctly identified decisions that the original GDD leaves open.
- Supporting sources preserve the distinction between extracted GDD facts and
  proposed implementation choices.
- The complete three-source workflow materialized the intended NPCs and quests
  without warning output.
- Project-scoped data kept this validation workspace separate from earlier demo
  content.

### Needs Improvement

1. A raw-GDD-only blueprint over-collects overlapping source lines in some
   runtime fields. The current rule-based extractor is intentionally grounded,
   but it still needs stronger section-aware deduplication before its prose is
   treated as production-ready design output.
2. The local index now uses deterministic offline lexical vectors so document
   upload is immediate and never downloads a model in the user's request. This
   is useful for terminology and grounded keyword retrieval, but it is not a
   substitute for a configurable semantic embedding provider in a later
   production phase.
3. Only the game creator can judge whether the generated design matches the
   intended CyberRakshak vision. The required manual review is therefore to
   compare every blueprint section and record any inaccurate, missing,
   repetitive, or irrelevant output before treating it as approved input.

## Reproduce

1. Start the local services with `docker compose up -d --build`.
2. Create a fresh workspace in the dashboard.
3. Upload the three CyberRakshak sources from `docs/demo` with their correct
   source types.
4. Review the GDD findings and attach the technical brief to the three decision
   records before resolving them.
5. Generate a blueprint using the runtime extension as the primary source and
   the GDD plus technical brief as supporting sources.
6. Confirm Jay, PATCH, Adi, and the three named quests before approval and
   materialization.
