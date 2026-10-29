# Chunk 6 — Live CyberRakshak acceptance

Initial date: 2026-10-03. Updated: 2026-10-04. Current result: **evidence preparation and explicit partial revisions implemented; two genuine hosted NPC revisions completed, but content acceptance remains blocked**. The original failures and earlier verification results below are historical, not the current run state.

## Scope and isolation

The user authorized live NVIDIA testing after Chunk 5. Created only the isolated workspace `qa-cyberrakshak-2026-10-03-c2600869`. Uploaded the bundled `docs/demo/cyberrakshak_gdd.md` as a GDD; ingestion produced 17 chunks in 1,047 ms. No technical/runtime companion was supplied, so this test would distinguish GDD facts from creative proposals rather than silently supplying missing design decisions. No existing workspace, source, artifact, account, key, or `.env` was changed. No approval, materialization, commit, push, or Unity work occurred.

Run ID: `56218f49-d469-4057-aad6-a5c891031dee`.

## Measured results

| Check | Actual result |
| --- | --- |
| Hosted consent absent | HTTP 409, before a run/model call was created |
| Planner | NVIDIA `nvidia/nemotron-3.5-lightning-30b-a3b` completed in 162,813 ms |
| Planner reliability | 3 transport attempts, 1 retry, 1 truncation retry; reasoning discarded |
| Retrieval | 12 unique frozen chunks, 3 matches for each of 9 sections; 527 ms |
| Blueprint generation | HTTP 410 from `nvidia/nemotron-3-super-120b-a12b`; node failed in 109 ms |
| Fallback | Disabled; no mock output substituted |
| Workflow outcome | API HTTP 503; persisted run status `failed` at `generate_blueprint` |
| Artifact/critique/revision | None produced; usefulness and revision quality cannot be judged |
| Approved exports | Technical brief and runtime export blocked with HTTP 409 |

The existing artifact-route configuration uses `NVIDIA_NANO_API_KEY`, although a distinct `NVIDIA_SUPER_API_KEY` also exists. Both credential slots were checked without exposing values: the live model catalog returned HTTP 200 but did not list the configured Super model. A minimal synthetic Super request using the distinct Super key, without `guided_json`, also returned HTTP 410. Therefore changing only key routing or the JSON schema is not an evidence-backed fix for this failure. Neither missing credentials nor creative-quality problems caused this observed run failure.

NVIDIA's public [Super model page](https://build.nvidia.com/nvidia/nemotron-3-super-120b-a12b/playground) remains discoverable. That page does not establish current hosted API availability. The live catalog and inference responses are the operational evidence; do not claim this proves permanent retirement or universal unavailability.

## Verification gates

- Backend: `docker compose exec -T backend pytest -q -rA --durations=15` — **271 passed, 1 deselected in 80.54 seconds**. The deselected case is the opt-in load benchmark. Verified the dedicated `gamemind_test` database and mock provider before execution; no other active test session was found.
- Dashboard fixture regression: **62 passed**, with all backend mutations and hosted calls intercepted. Minimum tested semantic contrast: **5.11:1**.
- Live Chromium walkthrough: actual backend, QA workspace only, desktop light at 1440 px and mobile dark at 375 px. Failed-run label and HTTP 410 trace visible, approval unavailable, all 17 source chunks reachable, no browser runtime errors, no cross-workspace requests, and no browser writes. These are two targeted live cases, not a full authenticated production walkthrough.
- Frontend production build had passed immediately before this batch with corrected CSS; this batch adds only the opt-in acceptance runner and documentation, not frontend application code. Lint, TypeScript and runner syntax were rechecked.

Evidence directory: `<QA_DIR>/chunk6-cyberrakshak-2026-10-03`.
It retains metadata, source chunks, consent rejection, failed response, run/trace, blocked-export responses, live-browser results and screenshots. The QA workspace and failed run remain available for inspection; they were not deleted.

## Repeatable harness

`frontend/tests/cyberrakshak-acceptance.mjs` uses the real API, requires an explicit output directory, scopes actions to a new QA workspace, and never automatically approves or materializes content. Execute from `frontend`.

```powershell
# A fresh start sends the bundled GDD to the configured hosted provider.
# Set a NEW output directory; start refuses to overwrite an existing directory.
$env:CYBER_ACCEPTANCE_DIR = '<QA_DIR>/new-acceptance-evidence'
$env:CYBER_ACCEPTANCE_HOSTED_CONSENT = 'yes'
node tests/cyberrakshak-acceptance.mjs start

# Existing evidence directory: read-only API capture or read-only browser inspection.
node tests/cyberrakshak-acceptance.mjs capture
node tests/cyberrakshak-acceptance.mjs preview
```

The current `preview` checks failed runs or blocked review-paused drafts, at 1440/768/375 px; it is not an approved-content acceptance test. It reads the latest failure from the actual trace instead of hardcoding HTTP 410. Browser requests are restricted to read-only methods and the isolated QA workspace. `CYBER_ACCEPTANCE_LABEL` gives captures distinct filenames so follow-ups do not replace the initial evidence. `revise <reason-file> <section-id>...` requires explicit targets and may call NVIDIA, but is usable only after a reviewable draft exists. The HTTP runner still uses the main server's configured model; the replacement experiments below ran in an isolated backend process with temporary overrides, not through a reconfigured server. A revision retains the same frozen evidence through the normal backend workflow.

## Next step and acceptance criteria

Get user approval to select/test a currently available artifact model. Keep Lightning as planner unless its measured latency justifies a separate routing decision. Validate the replacement with a small structured request before repeating the full pipeline; make routing changes process-local first, and do not edit `.env` implicitly. Do not increase retries or substitute mock output to hide HTTP 410.

After a genuine hosted draft exists: manually inspect PATCH voice and situational triggers, character intent, early-level quest order, objectives/rewards/failure/dependency semantics, section and record citations, unsupported proposals, and concrete integration steps. Request one focused revision, verify an actual targeted improvement with unchanged unrelated sections and one frozen snapshot, and re-critique. Only useful and explicitly reviewed output may proceed to approval/export. If runtime targets or numeric rewards remain unspecified, leave the bundle blocked; do not fabricate them to pass the gate.

Chunk 6 remains incomplete. See the follow-up below for actual hosted content inspection and critique. Successful revision improvement and approved live runtime export are still **unverified**. Unity stays last.

Nonblocking UI follow-up observed in the live failure screenshot: the content panel still labels itself "Summary" and says "This artifact does not contain the selected section" when there is no artifact at all. The approval status and trace correctly report failure, but a dedicated "No draft was generated" state would explain the situation more directly. This was recorded, not implemented in this batch; restoring a usable artifact-model route is the priority.

## Replacement-model follow-up

The user's next instruction authorized temporary replacement-model testing. Neither `.env` nor the running API server's provider configuration was changed. Artifact calls in the isolated acceptance process used the distinct `NVIDIA_SUPER_API_KEY`; key values were not printed. The successful Lightning planner and the same frozen evidence snapshot were retained. Checkpoint inspection confirmed the next node was `generate_blueprint` before each retry; neither planning nor retrieval was repeated. The original failed attempt remains in the trace.

- `nvidia/nemotron-3-ultra-550b-a55b` was present in the live catalog and returned HTTP 200 for a tiny synthetic JSON probe in 1.39 seconds. The actual full blueprint then failed the existing reliability budget in **272,025 ms**, without producing an artifact. Probe success is not full-pipeline acceptance. See NVIDIA's [Ultra model page](https://build.nvidia.com/nvidia/nemotron-3-ultra-550b-a55b/modelcard).
- `openai/gpt-oss-20b` was also present in the live catalog and returned HTTP 200 for the same synthetic JSON check in **5.35 seconds**. Its full workflow is evaluated separately below. This is an OpenAI model hosted by NVIDIA, not an NVIDIA-developed Nemotron model; see the [official hosted model card](https://build.nvidia.com/openai/gpt-oss-20b/modelcard).

The full retries used process-local artifact budgets of 8,192 tokens for generation/revision and 2,048 for critique, with guided JSON disabled and mock fallback disabled. The QA run's metadata records the temporary override; individual execution trace entries retain historical failure timings.

### Confirmed evidence-payload limitation

The frozen snapshot contains 12 chunks, but `_compact_evidence` in `backend/app/design_agent/nvidia_provider.py` sends only the ten highest-ranked chunks and the first 600 characters of each. For this run, it omitted chunk index 6 (`b52a293d-a077-4a62-8ce6-8349afde1e60`), which contains early story-level details, and chunk index 3. Several retained excerpts cut off mid-sentence. The quest-routed excerpts sent to the model were indexes 1, 13 and 14: broad premise, evaluation and scope, not the early Training Sandbox/Password Vault design detail requested by the objective. The source is present in ingestion but is not reliably available to the artifact prompt in this run.

This establishes a coverage limitation, not proof that every generated field is wrong. A larger or different model cannot recover omitted source facts reliably. The focused follow-up should preserve section-specific coverage and complete excerpts, then explicitly distinguish source-supported quest mechanics from creative proposals. Do not fabricate quest rewards or engine target IDs to make the scorecard pass.

### Actual GPT-OSS draft and critique

The first full GPT-OSS attempt, using the existing transport settings with an 8,192-token generation budget, timed out in **272,074 ms**. A controlled follow-up supplied the officially documented `reasoning_effort=low`, capped outgoing requests at **4,096 tokens**, and disabled transport retries for the acceptance process only. NVIDIA documents these options in its [GPT-OSS inference reference](https://docs.api.nvidia.com/nim/reference/openai-gpt-oss-20b-infer). The ordinary application transport does not yet expose a model-specific reasoning-effort setting.

This controlled follow-up completed generation in **89,727 ms** and a separate hosted critique in **26,374 ms**, with one request each, no repair, no truncation retry, no mock fallback, and discarded private reasoning. It paused at human review with artifact `17aaa8bd-e447-4cee-bdef-bfa6b95e9503`, version 1. This proves one successful real generation/critique pair, not a reliable latency benchmark or a working persisted replacement configuration. Generation was close to the 90-second timeout.

Manual comparison against the full bundled GDD and exact model-visible excerpts found:

| Finding | Evidence and user impact | Focused follow-up |
| --- | --- | --- |
| PATCH output missing | `npc_archetypes.content.npcs` is empty. A generated Jay record was removed for wrong section-routed citations; PATCH was not delivered. The user's priority character requirement is unmet. | Require the requested character in a focused, evidence-matched NPC output; treat a missing requested NPC as incomplete. |
| Incorrect early progression | Password Vault's reward is `Unlock The Reveal level`; `recommended_progression` lists Training Sandbox, Password Vault, The Reveal. The GDD places the reveal at Level 9 after intermediate missions. | Explicitly preserve narrative level order and validate generated unlock edges; do not infer a full progression from a three-item summary. |
| Unsupported quest particulars | Training Sandbox proposes `Collect 3 data packets`; Password Vault invents encrypted-file and firewall particulars and the internal dependency `q1`. The cited quest chunk describes broad premise/platforms, not these level-specific designs. | Retrieve the actual mission passages; represent unsourced quantities/prerequisites as explicit proposals, not source-grounded mechanics. Keep runtime bindings null. |
| Weak dialogue/integration value | Quest lines include `Let's get you moving, Adi` and `That password looks weak, try a stronger one`. They lack PATCH's distinctive warning humour and clear situational trigger mapping. Notes such as `Track puzzle completion` do not provide concrete acceptance checks. | Generate a small triggered dialogue pack with narrative approval markers and event-by-event integration/test guidance. |
| Critique false positives | The critic says Bold action and Speed run lack support, although supplied chunk 1 explicitly names bold action and speed; it questions Unity version/build targets despite explicit chunks 0/12. It also says no source supports Jay's existence even though the supplied evidence names him. | Make critique findings cite exact supporting/counterexample excerpts, distinguish absent section citations from absent source facts, and add regression cases for these false positives. |
| Scorecard overstates narrow success | Completeness and contradiction checks are both 100%, despite an empty NPC array and wrong unlock progression. The implementation only measures existing records' required arrays and duplicate names/IDs. Grounding and integration correctly fail, so overall approval remains blocked. | Score requested-output coverage separately and label duplicate checks narrowly; add specific progression checks without claiming comprehensive semantic validation. |

The scorecard was **69.45%**, grounding **77.78%**, integration readiness **0%**; verdict `needs_revision`. These are structural signals, not a score of creative usefulness. The artifact remained unapproved. Both technical-brief and runtime exports returned HTTP 409.

### Focused revision and trust boundary

Requested one PATCH-focused revision with the same process-local low-reasoning settings, explicit humorous warning situations, trigger mapping and manual checks. The hosted `revise` node timed out in **90,197 ms**. No version 2 or revised critique was produced. Before/after artifact captures are identical. The final QA workspace has **one artifact, one frozen snapshot, zero approved blueprints, zero runtime quests and zero runtime NPCs**. Its run is `failed` at `revise` with revision count 0, not completed.

A separate read-only reproduction exposed another focused-revision limitation: `review_targets("Revise only npc_archetypes. Preserve every other section exactly; this revision does not authorize quest or story changes.")` returns `['npc_archetypes', 'quest_hooks', 'narrative_direction']`. `backend/app/design_agent/grounding.py::review_targets` uses keyword matching and does not understand negation. It can widen the allowed target set even when the reviewer explicitly excludes sections. This attempt timed out before a changed artifact was saved, so no unintended section mutation was observed. Use explicit structured target IDs rather than interpreting authorization from prose.

Evidence captures: `gpt-oss-low-run.json` / `gpt-oss-low-trace.json` retain the review-paused hosted draft and critique; `post-revision-*` retain the failed revision, unchanged artifact and blocked exports. Failed execution rows lack `model_name`; their candidate identity is established by the recorded acceptance command/temporary override, not by those null trace fields.

After the failed revision, read-only live Chromium checks passed at **1440 px light, 768 px light and 375 px dark**: the current timeout was visible, the saved quest section remained readable, approval and runtime-download controls were unavailable, all 17 source chunks were reachable, and no browser runtime errors, cross-workspace requests or writes occurred. This checks the failure/recovery presentation, not successful revision or approved-content UX. No full accessibility, performance or authenticated-production acceptance claim is made for this targeted follow-up.

### Ranked next implementation slice

1. Fix section-specific evidence selection/compaction and add a fixture proving early-level and PATCH passages survive prompt preparation. Never change source text to match model output.
2. Make revision targets structured and explicit; test that negated mentions cannot widen scope. Return a small targeted section result and preserve unrelated sections server-side instead of asking for all nine sections on every revision.
3. Add model-specific request options and bounded retry/resume observability. Benchmark the candidate on useful structured artifacts before selecting it persistently; do not switch `.env` based on a single borderline success.
4. Re-run generation/revision against CyberRakshak with requested-character coverage, correct unlock order, citation support, useful dialogue and concrete integration checks. Check the critic's factual findings independently. Keep approval/export blocked until actual design and runtime decisions are supplied.

No backend/frontend application code, `.env`, existing workspace, or Unity project was changed in that replacement-model follow-up. Only acceptance-harness verification and this report were updated. No commit or push was made. The earlier 271-test backend result belongs to the preceding acceptance batch; it was not rerun in that follow-up.

## Approved implementation slice — 2026-10-04

The next user instruction authorized the first two ranked fixes: evidence preparation and smaller explicitly scoped revisions. Application files and regression tests changed in this slice. Existing unrelated worktree edits were preserved. No packages, keys, `.env`, existing game workspace/source, Unity project, commit or push were changed.

### Implementation and contract changes

- `contracts.py` uses focused NPC-voice and mission/progression retrieval queries. `nvidia_provider.py::_compact_evidence` reserves section-ranked coverage before filling the item budget and selects a complete sentence/paragraph window rather than cutting a prefix mid-sentence. Excerpts are literal source substrings with start/end offsets; no source text is synthesized. Oversized indivisible passages can be omitted and section gaps are reported; this is not a guarantee of exhaustive semantic coverage.
- Defaults are now 27 evidence items and 1,200 characters per item. Explicit environment limits remain authoritative: this running backend still uses **10 / 600**, unchanged. Fresh read-only retrieval against the existing QA GDD returned 12 chunks and packed 10; the PATCH voice passage was NPC-routed and retained, and the Training Sandbox/Password Vault passage was quest-routed and retained. Every packed excerpt matched its exact source offsets. Chroma emitted HNSW/telemetry errors and used the existing scoped lexical fallback for at least one section; vector-index health remains unresolved.
- Public rejection requests now require `target_sections`, a nonempty list of known section IDs. Missing or unknown scope returns HTTP 422; approval does not accept revision targets. API, durable review payloads, provider interfaces and workflow state carry the same explicit scope. Old persisted checkpoint reasons have conservative compatibility parsing; new public requests do not infer authorization from prose.
- Hosted revisions send only selected sections, their routed evidence, and a closed partial response schema. The backend merges only those sections and restores unrelated historical sections exactly after normalization. No-op/unrelated-drift checks remain. Evidence remains frozen throughout review/revision.
- The existing revision form has one labelled native section selector, defaulted to the currently viewed section, and explains that other sections stay unchanged. Scope/reason controls disable while submitting; existing error and loading states remain. The compact control avoids an extra screen or competing actions.
- Bare snake_case trigger IDs are removed from `dialogue_hooks` with a visible warning and cannot satisfy the actionable dialogue approval gate. This catches the observed failure, not all possible semantic or dialogue-quality failures.

Example of the updated API payload (also applies to queued review):

```json
{
  "decision": "reject",
  "reason": "Improve PATCH's spoken warnings; do not change quests or story.",
  "target_sections": ["npc_archetypes"]
}
```

The HTTP acceptance command is now `node tests/cyberrakshak-acceptance.mjs revise <reason-file> npc_archetypes`. This can transmit evidence to the configured hosted model and mutate the isolated QA run; it is not a read-only command. The saved run has consumed its two successful revisions, so do not replay it as an unlimited loop.

### Real hosted revision results

Retried the failed revision node using the same frozen snapshot in an isolated backend process. This did not rerun planning, retrieve new evidence into the run, or persist a replacement model configuration. Temporary artifact routing used NVIDIA-hosted `openai/gpt-oss-20b`, the distinct Super credential slot, low reasoning, a 2,048-token outgoing cap, no transport retries and no mock fallback. The normal API server still has its existing model configuration; this is not proof its configured Super route works.

| Check | Actual result |
| --- | --- |
| First partial NPC revision | 26,518 ms; one request, no repair/truncation retry; artifact version 2 |
| Independent critique of v2 | 26,329 ms; one request |
| v2 usefulness inspection | PATCH now existed, but all three hooks were trigger identifiers, not spoken dialogue |
| Corrected spoken-line revision | 19,039 ms; one request, no repair/truncation retry; artifact version 3 |
| Independent critique of v3 | 17,187 ms; one request |
| Revision payload | Only `npc_archetypes`; 3 routed chunks / 1,703 source characters |
| Preservation | All eight unrelated sections in v3 equal v1 exactly; versions 1, 2 and 3 retained |
| Evidence | One snapshot, ID `14cec014-9770-4ed8-b41e-a14885c343fe`, still 12 items |
| Runtime writes | Zero approved blueprints, runtime NPC profiles or runtime quests in the QA workspace |
| Final state | `awaiting_review`, revision count 2; scorecard 72.22%, verdict `needs_revision` |
| Exports | Technical brief and runtime both HTTP 409; no approval/materialization attempted |

Version 3 contains actual source-derived PATCH lines, including the suspicious-file joke and a shortened firewall warning. However, its implementation notes map the **file joke to a suspicious-link click**, the **firewall line to opening a file**, and a general recap to the firewall encounter. Repeat suppression and manual checks are present, but testing those mappings would reproduce the wrong situational dialogue. Do not call this pack integration-ready.

Quest progression and invented particulars remain unchanged by design: correcting them was outside the explicit NPC scope. The critic still makes unsupported assertions, such as requiring every creative line to exist verbatim in the source and claiming genre/platform facts lack source support. Partial/fabricated chunk references also appear in its recommendations. Structural completeness/duplicate metrics do not detect these semantic problems. Approval/export remains blocked by source support and unresolved quest proposals; the score is not a usefulness grade.

### Current verification

- Backend: `docker compose exec -T backend pytest -q --durations=5` — **279 passed, 1 deselected in 66.85 seconds**. Dedicated test database/mock provider; deselected opt-in load benchmark was not run.
- New focused regression file has 8 tests covering evidence windows/coverage, exact GDD passages with scoped lexical fallback, explicit scope validation, negative prose mentions, partial schema/payload isolation, section drift and trigger IDs masquerading as dialogue. Existing API/queue/provider tests cover target propagation.
- Frontend lint, TypeScript and production Webpack build passed. Dashboard fixture suite: **64 passed**, including desktop/mobile revision-scope submission and keyboard focus checks; minimum tested semantic contrast **5.11:1**. Real backend mutations/hosted calls were intercepted in fixtures.
- Live saved v3 browser checks passed at **1440 px light, 768 px light, 375 px dark**. NPC and quest records were visible, approval disabled, runtime download absent, all 17 source chunks reachable, no JS errors/cross-workspace requests/browser writes. This is targeted local-browser proof, not full authenticated-production, performance or accessibility acceptance.
- `git diff --check` passed. No full end-to-end fresh-generation quality pass or approved runtime export is claimed.

Saved evidence: `focused-revision-2026-10-04-*`, `spoken-revision-2026-10-04-*`, `live-browser-draft-v3.json`, and `live-draft-v3-{theme}-{width}.png` in the existing evidence directory. Original timeout captures remain intact.

### Remaining ranked work

1. Validate dialogue-line/trigger semantic alignment with a small situation-specific fixture; independently check each proposed event and manual test against the source. Fix the wrong mappings before approval.
2. Regenerate/revise quests using the newly retained early-level passages; enforce narrative order and distinguish supported mechanics from proposals. Do not invent numeric rewards or runtime bindings.
3. Ground critic findings in exact supplied excerpts/counterexamples and reject nonexistent references; add requested-character and progression coverage checks without overstating semantic guarantees.
4. Add deliberate model-specific request configuration and bounded observability, then measure a fresh full workflow before changing persistent routing. Resolve Chroma index/fallback warnings separately.

**Chunk 6 is still incomplete.** Evidence preparation and explicit partial-revision mechanics are verified; overall artifact usefulness, production model-route reliability and approved runtime acceptance are not.

### Dialogue-alignment follow-up

The next approved slice added structured event/line mappings, exact reference/manual-check guards and derived integration notes. Both bounded standalone hosted probes failed structured-output validation; no corrected artifact was saved or approved. The existing v3 mappings remain unacceptable. See [Dialogue trigger alignment validation](dialogue-trigger-alignment-2026-10-04.md) for the scoped changes, regression results, limitations and remaining steps.
