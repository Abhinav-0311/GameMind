# NVIDIA structured-output diagnostics and tiny dialogue probe

Date: 2026-10-04. Result: **safe diagnostics verified; one source-focused NPC/line/trigger response obtained and manually inspected**. This is a standalone diagnostic result, not a saved workflow revision, approval, full-blueprint pass or production model switch.

## Changes

- `backend/app/design_agent/llm_provider.py`: exceptions now carry structural diagnostics. JSON failures report a whitelisted parser reason and candidate-relative line/column/offset; schema failures report standard error codes and bounded known field paths. Unknown input field names and custom error types are redacted. Lists are limited to 20 schema errors / 12 path components. Completion records include visible character count, token usage, safe finish reason, request count and whether reasoning was discarded. They contain no response text, prompts, credentials, private reasoning, Pydantic input/context or custom validator messages.
- Initial versus repaired validation results are retained, including the initial error if the repair transport fails. Truncation failures retain both bounded completion summaries. Validation exceptions suppress content-bearing exception chains. Successful metadata uses the actual final finish reason rather than assuming `stop`.
- `workflow.py::_fail_execution` persists provider diagnostics and candidate model identity for future failed traces; `nvidia_provider.py` retains diagnostics when the existing explicit fallback is used. Historical traces were not rewritten and fallback remains disabled for these live probes.
- `contracts.py::DialogueTriggerMapping.manual_test` now describes the exact expected-line requirement in the schema. No database migration or frontend changes.
- `backend/tools/probe_dialogue_json.py` is an explicit-consent, QA-scoped read-only tool. It loads only the selected run's frozen snapshot, makes one HTTP call per probe, has no repair/transport/truncation retries or mock fallback, stops on failure, and restores its process-local model override. Maximum three probes per invocation. It never invokes workflow mutation/review/materialization.

## Actual progression and measured results

All calls used NVIDIA-hosted `openai/gpt-oss-20b`, low reasoning, a 1,200-token cap and the distinct Super credential slot in the standalone process. The normal backend's configured model route and `.env` were not changed. No key values were printed.

| Probe | Actual result |
| --- | --- |
| Initial tiny response | JSON/schema accepted, subsequent grounding/pairing validation failed; 5,994 ms. Detailed pairing classification was not yet present, so the exact failing check is not claimed. |
| Diagnostic tiny response | JSON/schema accepted, `finish_reason=stop`, 889 characters, 281 output tokens; exact blocker `manual_test_missing_expected_line`; 8,591 ms. |
| Three repetitions after clarifying expected-line requirement | Three structurally valid drafts, one request each, no retry/repair: 2,326 / 4,431 / 7,167 ms. Their dialogue was generic and their tests copied template wording; these were format passes, not usefulness acceptance. |
| One source-focused verification | Valid draft, `finish_reason=stop`, 769 characters, 236 output tokens, 10,745 ms; no repair/retry. Exact source sentence, matching link situation and concrete repeat/reset test. |

Six actual hosted calls occurred. These small samples are not average RAG latency or a reliability benchmark. Private reasoning was discarded and not retained.

Inspection confirmed that the original generic NPC compaction window omitted the GDD's link-warning sentence even though it exists in the frozen snapshot. The **probe only** now selects the exact quoted link-warning passage with literal start/end offsets. It does not mutate that snapshot or claim to fix all situation-specific evidence coverage in the normal broad blueprint workflow. Shrinking the task and providing the relevant passage helped; increasing blind retries or changing keys was not justified by these results.

## Useful inspected output

NPC: PATCH. Source chunk: `117f1fd8-cba2-4971-b15c-c2e57c6f40cc`.

Spoken line, quoted from the existing GDD:

> That link is trying too hard. Check the URL before you trust it.

Proposed trigger: player selects an untrusted link. The returned situation concerned a suspicious URL, not a file or firewall. Repeat policy: once per encounter, suppress repeated selections of the same link, reset when the encounter restarts.

Returned manual check:

> Select the link. Expect the spoken line: That link is trying too hard. Check the URL before you trust it. Select the same link again and verify that no warning is spoken. Restart the encounter and select the link again to confirm the warning is spoken anew.

Manual comparison found the line relevant to the event and the repeat/reset test concrete. The line itself is source-quoted, **not newly invented dialogue**. Trigger implementation and reset timing remain proposals requiring a designer's explicit decision. The server adds that assumption; neither citation membership nor format validation certifies engine behavior. No real game event was executed.

## Verification and preservation

- Full backend: **303 passed, 1 deselected in 71.24 seconds**. Dedicated guarded `gamemind_test` database and mock/fake inference. The opt-in load benchmark was not run.
- 10 new diagnostic regressions cover syntax versus schema, position/field diagnostics, secret/input redaction, bounded errors, repair success/failure/transport failure, workflow trace persistence, unknown finish reasons and truncation metadata.
- 3 new probe-safety cases cover missing consent, refusing non-QA scope before database access, and no hidden truncation retry. Initial missing-diagnostics tests failed before implementation; the final suite passed.
- Changed Python files parsed successfully; `git diff --check` passed. Optional Python linters/type checkers remain unavailable; no installation, new coverage percentage, frontend build or browser result is claimed for this backend-only slice.
- Read-only database checks after all probes confirmed: QA status `awaiting_review`, revision count 2, versions `[1, 2, 3]`, one frozen snapshot, zero approved blueprints, runtime NPC profiles or quests. Existing v3 is still wrong and unapproved. No source uploads, existing game-data edits, `.env` changes, model-route persistence, approvals, commits, pushes or Unity work occurred.

## Repeatable checks

From `E:\College\Project\Bot`:

```powershell
docker compose exec -T backend pytest -q test_structured_output_diagnostics.py test_dialogue_json_probe.py
docker compose exec -T backend pytest -q --durations=5

# Explicitly transmits the selected QA source passage to NVIDIA.
# One request, no application writes; default repeat count is one.
docker compose exec -T backend python -m tools.probe_dialogue_json --hosted-consent --project-id qa-cyberrakshak-2026-10-03-c2600869 --run-id 56218f49-d469-4057-aad6-a5c891031dee
```

Next: repeat the source-focused case before expanding to three independently evidenced situations. Inspect each actual line/event/test pairing. Then address normal-flow section/situation coverage, quest progression and critic false positives in separate slices. Do not change persistent model routing or proceed to Unity on this tiny-probe success alone.

## Next approved slice — grounded repetition and three situations

The next user instruction authorized repeating the grounded test and then expanding the standalone QA probe. No production provider, retrieval or dashboard code changed in this slice. The probe now supports `--pack`: a closed response with named `link`, `file` and `firewall` fields. Its source selector preserves one exact NPC-routed quoted passage for each requested case and refuses a missing passage rather than inventing one. Each case's returned line must equal its corresponding source passage; selected citations must close exactly. Swapped source lines are rejected even if all three are valid quotes.

Measured with the same process-local NVIDIA-hosted GPT-OSS route, no fallback/repair/retry:

| Check | Actual result |
| --- | --- |
| Source-focused one-line repeats | **3/3 valid**: 1,993 / 2,691 / 4,744 ms; source-quoted line, matching link action, concrete suppression/reset checks |
| Three-case pack | **1/1 valid**, 13,462 ms; 1,427 visible characters / 434 output tokens; one request, `finish_reason=stop` |
| Full backend regression | **309 passed, 1 deselected in 70.68 seconds** |
| Focused probe/pairing/diagnostic regression | 30 passed in 3.43 seconds |

The pack used a 2,400-token cap; the one-line repeats used 1,200. These are four further standalone calls, not a load/reliability benchmark. No planner or independent model critique was run for this pack; the actual result was manually compared with the selected source passages.

### Actual pack and integration checks

| Proposed event | Exact source-quoted line | Returned manual check |
| --- | --- | --- |
| Click untrusted URL | That link is trying too hard. Check the URL before you trust it. | Click the URL; expect this line. Repeat the click to verify suppression. Restart the encounter and repeat to verify reset. |
| Open suspicious executable | A file called homework_final_REAL_REAL.exe is already confessing. | Attempt to open the named executable; expect this line. Repeat the action to verify suppression. Restart the encounter and repeat to verify reset. |
| Approach firewall barrier | Firewall ahead. Literal this time. Someone had fun with the simulation. | Approach the barrier; expect this line. Repeat the approach to verify suppression. Restart the encounter and repeat to verify reset. |

These actions and lines now match; the previous file/link/firewall swap was not reproduced. The result's `situation` values were bare category labels and its `repeat_policy` values were only `one-shot`; the trigger and manual-test fields provide the concrete event/reset interpretation. That is sufficient for a small design review, not a fully specified engine contract. Decide whether suppression is per object or per encounter and which explicit event resets it before implementation. The generated parent citation list repeated the same source ID three times; the existing grounding validator canonicalizes it to one citation. All three quotes belong to chunk `117f1fd8-cba2-4971-b15c-c2e57c6f40cc`.

To integrate later, after an explicit design decision and normal-flow approval: bind each proposed event to its matching client action, present the corresponding spoken line, maintain the agreed suppression state, and execute the returned first/repeat/reset checks separately for every event. Do not treat the probe output as an approved runtime bundle or add guessed engine IDs. Existing server-derived integration notes can represent these structured pairings once they are generated in the actual review flow.

### Boundaries and remaining work

Six new offline cases cover exact source offsets/nonmutation, missing and unrelated-section passages, named-pack validation, swapped source lines, and unselected citations. Python syntax and `git diff --check` passed. No frontend/browser/build, optional Python-linter, coverage or real game-event execution result is claimed in this slice.

Read-only post-probe checks confirmed the saved QA run is still `awaiting_review`, revisions 2, artifact versions `[1, 2, 3]`, one snapshot, and zero approved blueprints/runtime NPCs/runtime quests. Original v3 is still unchanged and unacceptable; these useful standalone outputs did not bypass its exhausted revision limit. `.env`, keys, normal API model routing, existing game sources, Unity, commits and pushes were untouched.

Repeatable command (explicitly sends the selected QA passages to NVIDIA; one call, no application writes):

```powershell
docker compose exec -T backend python -m tools.probe_dialogue_json --hosted-consent --project-id qa-cyberrakshak-2026-10-03-c2600869 --run-id 56218f49-d469-4057-aad6-a5c891031dee --pack
```

**Next:** bring situation-focused evidence selection and small response contracts into the normal governed NPC revision flow, without hardcoding CyberRakshak quotes or forcing source-copying for creative dialogue. Preserve assumptions for proposed variations and timing. Then test a fresh consented workflow; the existing run's revision limit must not be bypassed. Quest progression and critic false positives remain separate blockers, and Unity stays last.

## Follow-up: production revision adapter integration

The existing dashboard review API now reaches a compact dialogue-patch contract for NPC-only, dialogue-focused revisions with existing named profiles and NPC-matched evidence. This is an internal optimization, not a separate dashboard option. Profile/roster edits, multi-section revisions, missing profiles and missing evidence keep the existing section contract. The conservative reason classifier may choose the larger contract unnecessarily; it must not restrict authorized profile/roster changes.

The model returns at most two named NPC patches with at most three situation/line/repeat-policy pairs each. It does not repeat each spoken line in hooks, manual tests or integration notes. The server derives hooks and manual checks, preserves the established profiles and unpatched NPCs, validates character/citation/trigger references, and merges only the selected NPC section. Existing grounding then rebuilds integration notes and retains proposed timings and creative variations as assumptions. Source-copying is not required for creative dialogue; quoted dialogue is preferred only when appropriate. These checks do not certify semantic fit or execute game events.

Evidence compaction uses the human revision's situation terms to rank NPC-matched chunks and complete literal source windows, within the existing item/character limits. The terms guide selection; they never become cited evidence. Production selection and response schemas have no PATCH-specific names or CyberRakshak quotes.

Verification on 2026-10-04:

- Regression-first: the new small-response test failed against the old full-section contract before implementation.
- Focused adapter/provider checks: 41 passed at the first integration checkpoint.
- Normal review API + adapter + probe-safety checks: 25 passed at the second checkpoint. The API test uses a fake hosted transport in the dedicated test database: the revision persists, frozen evidence is reused, independent critique reruns, unrelated sections remain identical, and approval is blocked. It is not live NVIDIA or browser proof.
- Final full backend suite: **331 passed, 1 deselected in 74.42 seconds**. The opt-in load benchmark was not run. A Chroma telemetry compatibility error was logged in a passing test; no telemetry fix is claimed.
- Python syntax for the four adapter/contract/probe/regression files and `git diff --check` passed.
- Local read-only inspection of the actual QA snapshot retained all three complete source warning lines at the configured 600-character-per-item limit. All excerpt offsets match literal source substrings. The original QA run remains awaiting review, revision count/max 2/2, artifact versions `[1, 2, 3]`, snapshot `14cec014-9770-4ed8-b41e-a14885c343fe`. No application writes or hosted calls occurred during that inspection.

The attempted one-call production-adapter NVIDIA probe was **blocked before execution by the safety review**, which requires explicit human authorization to send this saved GDD payload to NVIDIA. No workaround or indirect external call was made. Therefore this slice has no new live generation, latency, model critique, browser or engine-integration result. The probe supports `--governed-revision` for the authorized follow-up; it calls the actual production adapter in a standalone read-only transaction rather than resuming or modifying the exhausted saved run. Its model override remains process-local, with no fallback/repair/hidden retry.

**Next:** obtain explicit approval for sending the selected CyberRakshak QA GDD excerpts to NVIDIA for one read-only adapter test. If that passes, separately verify a fresh consented normal workflow after choosing an available normal model route; the current `.env` route was not changed or retested. Do not bypass the old run's revision limit, approve proposals automatically, or move to Unity. Quest progression and critic false positives still need their own acceptance work.

Later follow-up: explicitly authorized production-adapter generation failed JSON validation; a separately authorized initial-plus-repair test also failed, with saved data unchanged. The subsequent guarded local recovery and its verification are documented in [structured-closure-recovery-2026-10-04.md](structured-closure-recovery-2026-10-04.md). That local fix has not yet been retested against NVIDIA and must not be reported as a successful live acceptance.
