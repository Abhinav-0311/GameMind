# Guarded local JSON closure recovery — 2026-10-04

## Outcome

Implemented and verified locally. **362 backend tests passed, 1 load test deselected, in 77.55 seconds.** No hosted calls were made in this implementation slice. Live NVIDIA usefulness/reliability remains unverified after the fix.

## Evidence and uncertainty

The prior authorized GPT-OSS 20B test used exactly two NVIDIA requests: initial generation and one model repair. Both returned `finish_reason: stop` but failed JSON parsing at the end of the candidate. Total test time was 14.827 seconds. Saved artifact/evidence hashes and model configuration were unchanged. The failed model text was deliberately not retained, so missing closing delimiters is a hypothesis, not a confirmed diagnosis of those exact responses.

Synthetic nested NPC responses with missing closing delimiters reproduce that signature. Local tests also confirmed a parser diagnostic issue: `_extract_json` could crop an incomplete object at its last `}`, dropping an already-closed trailing array and reporting a different candidate. Pure-object EOF errors now preserve their complete candidate and position. Existing complete, fenced and prefaced JSON behavior remains intact.

## Recovery boundaries

Recovery is restricted to the exact `NPCDialogueRevisionOutput` contract, not planning, critique, generic JSON, broad generation or other revision contracts. It requires:

- A normal `stop` finish reason and no truncation retry in that completion operation.
- An EOF `Expecting ',' delimiter` error in the full candidate.
- A bare JSON object or a fully closed JSON code fence; no prose or unfinished fence recovery.
- A complete final object/array token, balanced delimiter types, no incomplete string or dangling escape, bounded nesting, and at most four missing closing delimiters.
- Duplicate-key rejection and successful validation against the closed NPC dialogue schema after appending only the required closing delimiters.

No quotes, values, commas, keys, citations, dialogue, assumptions or engine bindings are invented or rewritten. Unsupported shapes, missing required fields, unknown fields, ambiguous duplicate keys and incomplete content remain invalid. Normal provider retry/model-repair budgets are unchanged.

Accepted recovery is not proof of design completeness: an intended additional line could still be absent from a schema-valid draft. The response retains its original syntax diagnostic plus the recovery kind/count. Metadata distinguishes `local_recovery`, `recovery_requires_review`, hosted `repair_attempts` and request counts. No model text, reasoning, credentials or source text is added to diagnostics.

The normal NPC adapter adds a visible recovered-draft section warning and NPC assumption. Existing grounding, critique, quality scoring, consent, revision limits and human approval still apply. Recovery neither approves nor materializes content.

## Verification

- Regression-first synthetic recovery test failed before the fix.
- Focused recovery/provider/grounding suite: 83 passed in 4.68 seconds.
- Recovery plus normal durable review API tests: 32 passed in 6.04 seconds. A mocked missing-delimiter response persists as a reviewed revision, reruns critique, reuses frozen evidence, preserves unrelated sections, exposes recovery metadata through the trace API, and remains blocked from approval.
- Final full backend suite: 362 passed, 1 deselected in 77.55 seconds; no hosted inference.
- Python syntax for the four changed implementation/regression files and `git diff --check` passed.
- Ruff, mypy and pyright are unavailable in the existing backend container; none were installed. Coverage, frontend build/browser, load benchmark and actual game-event execution were not verified in this slice.

Implementation: `backend/app/design_agent/llm_provider.py`, `backend/app/design_agent/nvidia_provider.py`. Regressions: `backend/test_json_closer_recovery.py`, expanded `backend/test_design_agent_workflow.py`.

## Next acceptance gate

Obtain new explicit authorization for a bounded, read-only NVIDIA acceptance call using the selected QA GDD excerpts. Inspect the returned structural diagnostics and actual event/line semantics; neither the synthetic fixtures nor the passing suite establish that the real failure is fixed. Do not resume the exhausted saved QA run, change `.env` or persistent model routing, auto-approve a recovered draft, or move to Unity. Quest progression and independent-critic false positives remain separate acceptance work.
