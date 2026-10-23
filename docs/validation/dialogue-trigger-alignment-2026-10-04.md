# Dialogue trigger alignment — 2026-10-04

Result: **structured pairings and validation safeguards implemented; real hosted output acceptance remains unverified**. The existing CyberRakshak QA run remains at version 3 / revision count 2, awaiting review and unapproved. No saved content was silently repaired and its revision limit was not bypassed.

## Confirmed problem and focused changes

The actual v3 PATCH draft assigned its suspicious-file joke to a link click, its firewall warning to opening a file, and a general recap to a firewall encounter. These mappings were embedded in free-text `implementation_notes`, not an inspectable contract. Tests previously verified that hooks existed, not which event/line pair would be implemented.

- `backend/app/design_agent/contracts.py::DialogueTriggerMapping` adds an optional, backward-readable `NPCDesignCandidate.dialogue_triggers` list. Each proposed pairing has a nonblank `trigger`, `situation`, `text`, `repeat_policy` and `manual_test`. Up to three mappings; unknown fields such as `verified_by_model` are rejected. This is not a runtime event binding or a database migration.
- `grounding.py::_validate_dialogue_triggers` rejects duplicate trigger IDs, orphan lines, incomplete hook coverage and manual tests missing the expected spoken line. Quoted source dialogue does not prove that an invented trigger or repeat policy came from the GDD: those choices are marked as implementation proposals requiring designer review. The helper does **not** claim to decide semantic fit automatically.
- Legacy first-contact dialogue remains readable. A legacy `Trigger mapping` prose block is explicitly warned/flagged and cannot satisfy actionable approval without structured replacement. The saved malformed mappings are not automatically guessed or rewritten.
- `_add_integration_steps` generates readable event/line/repeat/manual-check notes from the structured mapping, so the existing dashboard can show integration guidance without a UI redesign. Old generated mapping notes and the conflicting first-contact instruction are rebuilt rather than accumulating after revisions. Revalidation is idempotent.
- `nvidia_provider.py::generate/revise` asks for meaning-based pairings, not positional assignment of two lists, and requires each manual check to expect its exact line. The prompt includes the observed file/link/firewall counterexamples, retains proposal assumptions, and asks for empty mapping prose because the server derives it.

The intended source-derived examples are: URL warning for an untrusted link, executable-file joke for a suspicious file, firewall warning for a firewall encounter. Proposed event names, reset rules and timing still need a design decision; this change does not silently certify or activate them.

## Verification

- `backend/test_dialogue_trigger_alignment.py`: **11 passed in 3.39 seconds**. Includes valid pairings, orphan/duplicate/missing mappings, vague tests, blank/unknown fields, source quote versus trigger provenance, legacy prose blocking, prompt contract, stale-note rebuilding and idempotence. A swapped-but-structurally-valid mapping regression explicitly stays review-blocked instead of claiming automated semantic certification.
- Final backend suite: **290 passed, 1 deselected in 70.04 seconds**. The deselected opt-in load benchmark was not run. An intermediate suite exposed the new idempotence regression; it was diagnosed as integration-note ordering, fixed, and the final full suite passed.
- Changed Python sources and the new test parsed successfully. `git diff --check` passed. Optional Ruff/mypy were not installed; no type/lint/coverage percentage is claimed.
- No frontend source changed in this slice, and no new browser or frontend-build result is claimed. The prior 64 browser-fixture / production-build results belong to the earlier slice.

Run from `E:\College\Project\Bot`:

```powershell
docker compose exec -T backend pytest -q test_dialogue_trigger_alignment.py
docker compose exec -T backend pytest -q --durations=5
git -c safe.directory=E:/College/Project/Bot -c core.autocrlf=false diff --check
```

Tests use the guarded `gamemind_test` database and mock inference. Docker Desktop was stopped at the beginning of this slice; the existing installation was started hidden, and the existing containers resumed without installation, rebuild, volume removal or configuration edits.

## Bounded real NVIDIA probes — failures retained

The QA run had already consumed its two successful revisions. Two standalone provider probes read only its frozen snapshot and v3 artifact, with SQL transactions explicitly read-only. They did not use the workflow to create a revision, critique, review event, blueprint, NPC or quest. No approval/export or new ingestion was attempted.

Temporary process-local routing used NVIDIA-hosted `openai/gpt-oss-20b`, the distinct Super credential slot, low reasoning, a 3,072-token cap, and no mock fallback. No key values were printed. Neither `.env` nor the normal API server's model configuration changed.

1. First probe: one request, repair disabled, no retry. Returned malformed JSON (parser reported a missing comma); `NvidiaStructuredOutputError` rejected it. No usable corrected pack was obtained.
2. One bounded correction attempt after reducing duplicate notes and requiring proper JSON escaping: at most two requests including structured-output repair, no transport retries. Returned `NvidiaStructuredOutputError: NVIDIA structured-output repair failed its validation budget.` No usable corrected pack was obtained. Further hosted retries stopped.

These are real failed probes, not mock success, semantic acceptance, a successful saved revision, or latency benchmarks. Failed response bodies were not retained, so the second failure cannot be narrowed confidently to JSON syntax versus schema compliance. The regression fixtures prove contract/guard behavior, not the quality of an unseen model response.

## Remaining blockers and next step

1. Inspect bounded structured-output diagnostics safely, then test a compact paired-dialogue response with exact schema compliance before further full artifact calls. Avoid increasing unbounded retries or switching persistent models on assumption.
2. Obtain one real corrected pack and manually verify **each** situation, expected line, repeat/reset rule and manual test against the source. The current saved v3 pack is still wrong and unapproved.
3. Clarify how explicit human design decisions confirm proposed mappings/assumptions in the normal review flow. This slice adds no auto-approval or assumption-clearing bypass.
4. Correct quest progression and critic false positives in separate focused slices. Unity remains last; Chunk 6 is not complete.

Existing unrelated worktree changes were preserved. No packages, keys, `.env`, existing game sources, commits or pushes were changed.

## Subsequent diagnostic result

The next approved slice added safe JSON/schema/truncation diagnostics and a read-only tiny probe. It obtained a source-quoted PATCH link warning with a matching trigger and concrete manual check, without saving or approving a revision. The original v3 remains unchanged. See [NVIDIA tiny dialogue validation](nvidia-tiny-dialogue-2026-10-04.md) for actual measurements and limitations; the earlier failed full-NPC probes above remain historical evidence.
