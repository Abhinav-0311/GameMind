# Phase 4 CyberRakshak Quality Validation

Date: 2026-07-29
Scope: flagship Design Agent MVP quality proof

## What this phase proves

Phase 4 separates two questions:

1. Can GameMind execute and persist the governed workflow correctly?
2. Is the resulting game-design output supported, useful, and correctly revised?

The first question is system-tested. The second uses explicit CyberRakshak
human judgments stored as an immutable scorecard beside the completed run.

## Deterministic acceptance scenario

`test_cyberrakshak_reject_restart_approve_and_scorecard` runs the real LangGraph
workflow with a scripted provider and curated facts from the CyberRakshak GDD.

The scenario:

1. Generates an incomplete level section containing Levels 1 and 9.
2. Critiques the missing Level 10, Hunt Jay.
3. Pauses for human review.
4. Rejects the draft with a concrete correction.
5. Reuses the same frozen evidence snapshot.
6. Revises the section to all ten named levels.
7. Critiques the revision again.
8. Recreates the service to simulate a process restart.
9. Approves and finalizes one immutable artifact.
10. Persists and reloads a passing five-metric scorecard.

Assertions include one retrieval execution, durable checkpoint resume, revision
count, immutable finalization, exact rubric coverage, duplicate-evaluation
rejection, and project-boundary enforcement.

## Honest historical baseline

Run: `3edd0429-3ea7-4eaa-b0ca-bd65ecbb53db`
Workspace: `cyberrakshak`
Evaluation: `0dc55b1e-a3e8-42d5-adfc-44bc1230016f`

This earlier completed run persisted approval correctly but did not repair its
level coverage. Its objective and revision referred to nine levels even though
the GDD defines ten, and the final structured level list remained empty.

| Metric | Result | Target | Outcome |
| --- | ---: | ---: | --- |
| Citation relevance | 11/27 (40.74%) | >= 80% | Fail |
| Unsupported-claim rate | 1/4 (25%) | <= 10% | Fail |
| Critique usefulness | 4/4 (100%) | >= 75% | Pass |
| Revision correctness | 0/1 (0%) | 100% | Fail |
| Approval persistence | 1/1 (100%) | 100% | Pass |

Overall score: 63.15%. Result: needs improvement.

This failure is retained intentionally. It demonstrates that completing the
graph is not treated as evidence of semantic quality.

## Verification

```text
docker exec gamemind_backend pytest -q --disable-warnings
209 passed, 1 deselected

docker exec gamemind_backend pytest -q test_design_agent_evaluation.py
2 passed

npm.cmd run lint
passed

npm.cmd run build
passed
```

The deselected test is the opt-in multithreaded load benchmark marked `load`.
An explicit `pytest -m load` run stopped producing progress for more than five
minutes and was terminated. The benchmark shares one global FastAPI
`TestClient` across 10, 25, and 50 worker threads, so its harness must be
stabilized before it can be treated as a reliable performance gate. This does
not affect the passing functional suite, but it remains an open test-quality
issue.

Playwright verified `/design-agent` in the CyberRakshak workspace at desktop
and 390px mobile widths:

- the stored scorecard loads after reload;
- all five metrics and their provenance are visible;
- no browser console errors were emitted;
- no horizontal overflow was present.

Screenshots:

- `docs/validation/phase-4-scorecard-desktop.png`
- `docs/validation/phase-4-scorecard-mobile.png`

## Interpretation

The deterministic test is the reproducible product acceptance proof. The live
historical scorecard is the semantic baseline that exposes why the evaluator
exists. The next quality improvement should target retrieval precision and
structured revision behavior, not add more workflow nodes or dashboard panels.
