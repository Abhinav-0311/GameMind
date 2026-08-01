# Phase 5 Semantic Quality Validation

Date: 2026-08-01
Case study: CyberRakshak

## Objective

Phase 5 improves the evidence and revision quality inside the existing Design
Agent workflow. It does not add nodes, replace Chroma, redesign the console, or
change the durable review architecture.

## Root causes corrected

1. One broad semantic query previously supplied the same top chunks to every
   blueprint section.
2. The local mock generator copied the first evidence excerpts and citations
   across unrelated sections.
3. A mock revision could add only a `human_revision` note without changing the
   structured design output.

## Implementation

- The planner deterministically creates one focused query for each of the nine
  blueprint sections.
- Chroma executes those queries in one batched request scoped to the selected
  project and document IDs.
- The frozen snapshot deduplicates chunks while retaining `matched_sections`
  and per-section similarity values.
- GameMind's existing deterministic BlueprintService parser is reused by the
  local Design Agent provider.
- A grounding boundary removes missing and cross-section citations, recalculates
  confidence, and records warnings when evidence is absent.
- A revision boundary requires a material change to the targeted structured
  section and rejects changes to unrelated sections.
- The local fallback can apply an explicit level correction only when the level
  title is present in the frozen evidence.

## CyberRakshak evidence

The real indexed `cyberrakshak_gdd.md` was queried through the Phase 5 retrieval
path. One Chroma batch returned 14 unique chunks. The level section selected
chunks 5, 6, and 7, and the shared local extractor produced:

- 10 ordered story levels;
- Level 9: The Reveal;
- Level 10: Hunt Jay;
- Adi, Jay, and PATCH;
- populated core loop, player approaches, failure feedback, progression,
  platform/control, scoring/economy, and design-constraint categories.

The historical scorecard remains immutable at 63.15% and is retained as the
before-state. The deterministic reject-revise-restart-approve acceptance
scenario records a 100% five-metric scorecard after the corrected path. The
comparison is intentionally not produced by editing the historical evaluation.

## Regression coverage

`test_design_agent_semantic_quality.py` verifies:

- all ten CyberRakshak levels are extracted;
- Hunt Jay remains the final level;
- cross-section citations are removed;
- no-op revisions are rejected;
- unrelated section drift is rejected;
- section retrieval uses one Chroma batch and retains provenance.

Existing workflow tests continue to verify one frozen evidence snapshot across
rejection, restart-safe checkpoint resume, immutable approval, exports, project
isolation, and explicit fallback traces.

## Verification

```text
docker exec gamemind_backend pytest -q --disable-warnings
213 passed, 1 deselected

docker exec gamemind_backend pytest -q \
  test_design_agent_workflow.py \
  test_design_agent_evaluation.py \
  test_design_agent_semantic_quality.py \
  test_design_agent_llm_provider.py
19 passed

npm.cmd run lint
passed

npm.cmd run build
passed
```

The deselected test remains the opt-in load benchmark documented in Phase 4.
It is not part of the semantic-quality acceptance gate.

## Result

Phase 5 closes the known semantic architecture gaps without adding framework
complexity. Future quality work should measure additional real GDDs and improve
weak parsers only when a recorded scorecard identifies a concrete failure.
