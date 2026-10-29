# Live DEV approval/export acceptance — 2026-10-27

## Verdict: FAIL — approval blocked at human review

**The requested MVP proof did not pass.** The real browser created one fresh isolated Frostpeak workspace, resolved Windows PC as human direction, obtained hosted-transfer consent and completed real Flash-Lite planning, generation and critique. The critic returned `needs_revision` for mismatched quest labels/IDs. The dashboard disabled **Approval blocked**, so approval could not be submitted through the permitted UI path.

Stopped at that gate: **no proposal confirmations, approval POST, rejection, revision, retry, finding adjudication, export or runtime materialization**. There is no final artifact or approved blueprint. Hash equality with an immutable final and completed-state UI behavior remain unverified. This is neither an approval-500 reproduction nor evidence that `f79e059` failed its conflicting-review guard: this run has never been rejected and has no review event.

PASS required successful approval, export, reviewed/final hash equality and immutability. None of those four gates completed. Correctly refusing unsafe approval is safety evidence, not MVP acceptance.

## Method, code and environment

- Executed commit: **`f79e059281ffd302358b18e15e94cbbc864dc330`**. No tracked changes existed before this check; pre-existing untracked `docs/audit/` was left untouched.
- Real headless Playwright Chromium **149.0.7827.55**, viewport **1440 × 1000**, against live frontend `http://localhost:3000` and backend `http://localhost:8000`. No `page.route`, fixture fulfillment, intercepted responses or `dashboard-states.mjs`.
- All six workflow mutations were driven through rendered browser controls. Later API reads and a PostgreSQL **READ ONLY** transaction verified only this new workspace/run.
- Used existing cached `gamemind-revise-tests:local`, containing `google-genai==2.33.0`, with current backend source bind-mounted at `/app`. No image build, download or package installation. Restart policy **`no`**; production provider retry policy unchanged.
- Effective process values: `LLM_PROFILE=dev`, `GEMINI_DEV_MODEL=gemini-3.5-flash-lite`, `GEMINI_TIMEOUT_SECONDS=180`, `DESIGN_AGENT_FALLBACK_TO_MOCK=true`, `DESIGN_AGENT_FALLBACK_DISABLED_NODES=["revise"]`, `PYTHONPATH=/app`, `DESIGN_AGENT_EXECUTION_MODE=inline`, per-run request cap **12**. No worker profile was started.
- Container and host source hashes matched: service `63efba5d7866f7212dc19a834857a0645094ee96a86d3d70a17abbeb205120c1`; workflow `d6886f9587b5141cdea4fb563dd597ef3ea4d137fa5db7da025ff98510b3b27e`.
- Health and readiness: **200**, provider `gemini`; no restarts or fatal startup traceback. Known non-fatal Chroma/PostHog telemetry logging was ignored, not repaired.
- `.env` SHA256 before/after: `60ECE87260E426092840CCB4EC1365746433539555B55021BCD09770E8A6F112`. No code or environment-file edits.
- The Playwright extension bridge was unavailable, so the installed direct Playwright runtime drove real Chromium. The sandbox initially blocked browser child-process/localhost access; the real browser and frontend ran outside that restriction. No application or provider request was retried because of those setup checks.

The browser-QA skill guided the real interaction/network/error capture. This was a desktop critical-path check, not a mobile, dark-mode, performance-metrics or accessibility certification.

## QA evidence and identities

**QA folder:** `<QA_DIR>/live-approval-export-20261027-01`.

All screenshot names below refer to this exact folder, outside the repo. Supporting files: `browser-evidence.json`, `start-response.json`, `final-run.json`, `trace.json`, `evidence.json`, `database-verification.json`, `verification.json`, `backend.log`, `shutdown.log`, and before/startup/generation/after usage JSON files. `generation.log` also contains old container history; accounting uses the current-startup-only `backend.log` and current Pacific-day ledger snapshots.

| Item | ID |
| --- | --- |
| Workspace | `final-mvp-frostpeak-dev-20261027-01` |
| Display name | Final MVP Frostpeak Dev 20261027 01 |
| Frostpeak document, revision 1 | `c3a4dec7-b4e3-43e4-8572-afb10aec5486` |
| Resolved platform decision | `25d0c5c6-b0ff-469e-a4fe-11fd51168afe` |
| Run | `4a1e7f1f-b6a2-410c-a746-d8e52daf2ba2` |
| Draft v1 | `729caf30-1a03-49fb-82b7-0dab811ac4e6` |
| Frozen evidence snapshot | `fe307d76-077a-480e-ae79-de4cb14186b5` |

No mutations targeted B3, B4b or the faulted earlier walkthrough run `57482747-1e91-4833-bcb0-62b77ce3fab5`. None was resumed, repaired, rejected or approved. The normal project picker lists existing workspaces, but they were not selected for this run.

## Step 1 — workspace, source, decision, consent and generation

Created a new workspace through **New project**, then **Sources → Load Frostpeak demo**. The synthetic sample produced four indexed chunks. Screenshots: `01-new-workspace.png`, `02-empty-sources.png`, `03-frostpeak-loaded.png`.

On Decisions, **Review GDD** synchronized four local questions. Closed its automatic hosted-start dialog with **Continue with local review** so the human platform decision could be completed first. Saved and marked exactly this decision resolved:

> The target platform is Windows PC. Set unity_runtime_preview.content.target_platform to the exact string "Windows PC"; this is human design direction, not a GDD fact.

The exact check is `unity_runtime_preview.content.target_platform == "Windows PC"`. It is absent from the GDD and was saved without pretending it had a supporting source document. The other three local questions remained open. Screenshot: `04-windows-pc-resolved.png`.

Run setup: runtime deferral **unchecked**, unspecified NPC memory **allowed**, `max_revisions=2`, fresh-dialogue option unchanged/off, optional repeat/reset policy blank. Screenshot: `05-run-setup.png`.

Objective:

> Create a source-grounded design blueprint for Project Frostpeak with both starting NPCs and both quest hooks. Preserve every objective, quantity and reward. Include useful distinct spoken dialogue and practical implementation notes. Clearly label proposals; do not invent source support.

Exact consent text:

> GOVERNED AI REVIEW
>
> Start a cited review?
>
> The selected source revision may be sent to the configured hosted provider to create a cited draft and independent critique. No provider request is made until you confirm.
>
> Cancel / Start governed review

Screenshot: `06-hosted-consent.png`. Confirmed once. Run creation returned **201** and reached `awaiting_review` in **65,486 ms**. Progress screenshots: `07-generation-in-progress.png`, `08-run-progress.png`.

### Actual node/provider accounting

| Node | Actual provider/model | Result/degraded | Latency ms | Input/output tokens | Real inference requests |
| --- | --- | --- | ---: | ---: | ---: |
| plan | Gemini / gemini-3.5-flash-lite | completed / false | 27,391 | 393 / 171 | 1 |
| retrieve_evidence | Local Chroma/lexical / chroma-local-lexical-v1 | completed / no model fallback | 292 | 0 / 0 | 0 |
| generate_blueprint | Gemini / gemini-3.5-flash-lite | completed / false | 22,128 | 3,420 / 2,271 | 1 |
| critique | Gemini / gemini-3.5-flash-lite | completed / false | 15,237 | 6,491 / 450 | 1 |
| human_review | Local workflow | waiting; no submitted decision | 0 recorded; wait time not measured as execution latency | 0 / 0 | 0 |
| finalize/export | Not reached | unverified | — | — | 0 |

All three inference POSTs returned Google HTTP **200**. Every node used its first completion: **zero retries/backoff, repairs, truncation resends, corrective re-asks or mock fallbacks**. Trace metadata and the transport log agree; this conclusion does not rely only on `degraded=false`. No model reasoning was retained. Reported tokens total **13,196**: 10,304 input plus 2,892 output. Cost was unavailable, not measured zero.

Actual wire-schema log sizes: plan **2,364 bytes**, generation **20,525**, critique **16,293**, all full schemas. No revise schema was requested. Screenshot: `15-real-provider-trace.png`.

## Step 2 — draft, critique and scorecard inspection

Screenshots: `09-review-blocked.png`, `10-summary-and-gate.png`, `11-npc-quest-numbering.png`, `12-quest-dialogue-and-objectives.png`, `13-windows-pc-runtime.png`.

Summary is the **exact Section 1 premise**, correctly cited to frozen chunk `8eee8ce4-dfd4-48f2-afca-a8d9dee5c2af`:

> Project Frostpeak is an immersive tactical role-playing game set in the frozen ruins of the Northern kingdom of Frostpeak. The player assumes the role of a legendary pathfinder aiding the Frostpeak Resistance in reclaiming their home and restoring the lineage of King Arven from the occupying forces of the Cinder Vanguard.

This is local exact-source extraction inside the hosted adapter, not Gemini-authored prose. The runtime tab contains **Windows PC**, and the critic explicitly recognizes it as human-directed. Runtime preview is populated, not deferred; this is not runtime release approval or engine-integration proof.

The saved scorecard fails on **Integration readiness**: grounding 1.0, completeness 1.0, consistency 1.0, integration readiness 0.0, with **20 unconfirmed proposals**. The displayed structural assessment is 75%, not a claim of 75% semantic quality. Memory has empty rules/citations with explicit unspecified/unassessed warnings.

Independent critique verdict: **`needs_revision`**. Its summary says the GDD and Windows PC direction are incorporated, then identifies mismatched quest naming/ID references. Two medium findings:

1. Eldrin completion `npc_1_completion_3`: situation **"Quest 1 completion acknowledgment"**, but `eligibility.quest_id="quest_2"`. Recommendation: **"Align the eligibility quest_id with the intended quest in the situation description."** Reference path: `/npc_archetypes/content/npcs/0/dialogue_triggers/2/eligibility/quest_id`.
2. Kaelen completion `npc_2_completion_3`: situation **"Quest 0 completion acknowledgment"**, but `eligibility.quest_id="quest_1"`. Recommendation: **"Align the eligibility quest_id with the intended quest name/id in the situation description."** Reference path: `/npc_archetypes/content/npcs/1/dialogue_triggers/2/eligibility/quest_id`.

Both are draft-structure observations with null source evidence references, not alleged missing source requirements. Coverage is `covered` for the other eight sections and `not_specified` for memory. No corrective re-ask occurred.

### What the numbering actually means

| NPC / stage | Situation label | Saved quest ID | Spoken content |
| --- | --- | --- | --- |
| Eldrin progress | Quest 0 progress inquiry | quest_1 | General caution while aiding the Resistance |
| Eldrin completion | Quest 1 completion acknowledgment | quest_2 | "Your retrieval of the sky-iron preserves our history." |
| Kaelen progress | Quest 1 progress inquiry | quest_2 | Resources demanded from cliffside veins |
| Kaelen completion | Quest 0 completion acknowledgment | quest_1 | "You survived the border post. Acknowledged." |

There is real zero-based/one-based naming confusion: the GDD has **Quest Hook 1 and Quest Hook 2**, not Quest 0. However, the two completion IDs match the spoken topics: mining belongs to quest_2; the border post belongs to quest_1. Blindly changing the IDs to follow the situation numbers would make those topics wrong. The critic catches a genuine presentation inconsistency but does not establish that the machine IDs are the erroneous fields. Its correction advice needs human interpretation, and it misses the two similarly numbered progress labels.

## Step 3 — approval gate: stopped, no submission

Observed control state:

```text
Approve label: Approval blocked
Approve disabled: true
Request revision disabled: false
Download technical brief buttons: 0
Degraded acknowledgement controls: 0
Saved revisions: 0/2
Consecutive failed corrections: 0/3
```

Screenshot: `14-disabled-approval-and-findings.png`. The disabled button is visibly muted. The independent-critique panel says **Changes recommended** and shows both findings.

No degraded acknowledgement appeared because no node fell back to mock. There is also no LIVE02 recorded-rejection blocker: API `approval_blocked_reason=null`, and PostgreSQL has zero review events. The block is the existing critique/quality gate, not the new conflict guard. `frontend/src/app/design-agent/page.tsx` derives `needsRevision` from the current finding review/critique and includes it in `approvalBlocked`; selecting proposal checkboxes cannot clear it.

Stopped under the user's no-revision/stop-at-blocking-failure restriction. **No proposals were confirmed and no approval POST was sent.** Forcing a disabled control or submitting the API directly would not be a browser-only positive proof. There is no approval HTTP refusal/500/traceback to report because approval never executed. Application console/page errors were **zero**; the run's `last_error` is null.

## Steps 4–5 — export and completed-state controls: not reached

No approved brief exists or was downloaded. No screenshot of an exported brief can truthfully be provided; the screenshots show the blocked draft instead.

Approve/reject/revise-after-completion and reload-of-completed-state checks were **not performed** because the run did not complete. No rejection/revision was submitted, no manual model retry was made, and the finding-review mechanism was not used to dismiss or bypass these findings.

## Step 6 — read-only API/database verification

The new run, trace and frozen-evidence API reads returned **200**. A separate transaction explicitly set `SET TRANSACTION READ ONLY`; `SHOW transaction_read_only` returned `on`. Queries were limited to the new run/workspace and then rolled back.

Saved state:

- Run: `awaiting_review`, current node `human_review`, revisions **0/2**, `last_error=null`.
- One artifact: v1 draft `729caf30-1a03-49fb-82b7-0dab811ac4e6`, **immutable=false**.
- **Zero review events, zero final artifacts, zero GameBlueprint rows** in this fresh workspace.

Canonical SHA256 uses Python `json.dumps(content, sort_keys=True, separators=(',', ':'), ensure_ascii=False)` encoded as UTF-8:

```text
API draft:                 ad1b7cee32ed49ca804b217362703569ef49a499da02df0cbac9af7d5d516d34
Database draft:            ad1b7cee32ed49ca804b217362703569ef49a499da02df0cbac9af7d5d516d34
Critique provenance draft: ad1b7cee32ed49ca804b217362703569ef49a499da02df0cbac9af7d5d516d34
Final artifact hash:       unavailable — no final exists
Reviewed/final equality:   not evaluated
```

The draft API/database/provenance equality is verified. It is **not** finalization evidence, and there is no final-content mismatch diff to produce. `verification.json` asserts these results from the saved API/database/browser evidence, including zero `/review` POSTs, with networking disabled.

## Step 7 — plain content assessment against the GDD

**No exported brief was produced. Its structure, version statement, citations/provenance formatting and practical usefulness are unverified.** The following assessment is of the actual saved draft, not an invented preview of a final brief.

### Good

- Correct exact premise, names, Ember Siege of **842**, Vulcana/Warlord Ignis background, source visual palette and Geothermal Vents/East Gate layout.
- Both quest source objectives and rewards remain exact: reclaim/clear guards/raise flag for **100 gold and 250 XP**; mine **5** ore chunks for **150 gold and sky-iron gear**.
- Windows PC satisfies the saved human decision and is not criticized as unsupported simply because the GDD is silent.
- Eldrin sounds formal/lore-oriented; Kaelen is terse and transactional. Their greetings are usable first-pass spoken lines, and the completion text recognizes the right mining/border-post topic for its stored quest ID.
- Unsupported NPC memory is left empty and explicitly unassessed instead of inventing persistence behavior.
- New failure/restart choices and state bookkeeping carry proposal labels; generated integration/manual-test notes say they are not executed bindings or playtests.

### Wrong, weak or unsupported

- **Quest dialogue is still objective text.** Quest 1 says "Reclaim the Ash Pass border post. Clear the guards and raise the Northern flag." Quest 2 says "Mine 5 chunks of raw sky-iron ore from the cliffside veins." The latter is verbatim objective text; the former is a near-copy. Neither is a well-characterized quest-giver conversation. The critic did not flag this.
- **Quest 0 leaks into human-facing situations/manual tests.** The zero-based situation labels disagree with the one-based quest names/IDs. The critic catches two completion cases but misses the progress labels; its ID-focused recommendation could move otherwise correctly themed speech onto the wrong quest.
- NPC assumption labels associate Eldrin with Hook 1 and Kaelen with Hook 2, but their completion speech acknowledges the other hook. Additional cross-quest dialogue is not inherently forbidden, but the draft does not explain that relationship clearly.
- Kaelen is an occupying Cinder Vanguard commander yet acknowledges surviving the Resistance's border-post assault. The GDD permits consequential faction choice, so this is not automatically impossible; the missing faction-state/consequence explanation makes it unsuitable as a ready-to-integrate narrative contract.
- Guard defeat, cliff falls, reload/respawn at checkpoints, and exact restart operations are **design proposals**, not documented GDD failure/restart rules. "No reset" repeat policies are also new choices, not sourced rules. A developer must decide their actual replay/reset meaning and implementation.
- Windows PC is human-authorized direction, not a GDD fact. Its runtime preview cites all four chunks and has no warning; that does not make the platform source-backed. The separate decision/critic context is necessary to interpret provenance honestly.
- No extra numeric reward, timer or quantity requirement was identified in the inspected draft beyond the source values above. The spurious **Quest 0** label is a numbering defect, not an authorized new quest. Mechanical flags/IDs and proposed test states are not independently verified gameplay facts.
- The 100% structural grounding/completeness/consistency metrics do not detect these semantic inconsistencies. The systems list largely organizes source mechanics rather than providing a complete combat, economy or progression design. State-contract prose is not engine integration.

For an indie developer, this is a useful cited outline with draft NPC lines and preserved quest facts. It is **not a finished usable implementation brief**, and the approval/export product path remains unproven. The guard refuses approval rather than concealing the need for correction; the underlying naming/dialogue weaknesses still exist.

## UX findings

| ID | Rating | Observed issue | Screenshot |
| --- | --- | --- | --- |
| AE01 | **blocker** | Generated quest labels and critique verdict prevent this no-revision run from reaching approval/export. This is a content/review-readiness blocker, not an API crash. | `11-npc-quest-numbering.png`, `14-disabled-approval-and-findings.png` |
| AE02 | **annoying** | Critic misses copied quest objective/dialogue and two progress-label mismatches. Its recommendation emphasizes changing IDs even where stored IDs match the spoken topics. Reviewer interpretation is still required. | `11-npc-quest-numbering.png`, `12-quest-dialogue-and-objectives.png` |
| AE03 | **annoying** | Twenty proposal checkboxes remain visible even though the critique independently blocks approval; they cannot resolve the actual gate. A reviewer has substantial reading/selection work without a path to export in this run. | `09-review-blocked.png` |
| AE04 | **annoying** | The hosted-start modal remains the wait surface during a 65.5-second inline request; node-level progress is only inspectable after the run response. | `07-generation-in-progress.png`, `08-run-progress.png` |
| AE05 | **annoying** | Local Review GDD automatically opens hosted consent before local decisions are finished; it must be dismissed to resolve the platform choice first. | Observed during local review; `04-windows-pc-resolved.png` shows the subsequent resolved state, not the dismissed modal. |
| AE06 | **cosmetic** | Long raw trigger/state/manual-test data and IDs dominate the draft, while the narrow status column stretches the page. At the blocked button the Runtime content has scrolled far out of view, leaving a large empty main column. | `11-npc-quest-numbering.png`, `14-disabled-approval-and-findings.png` |

What worked: project isolation, sample ingestion, resolved decision UI, correct hosted consent, actual Gemini execution without fallback, exact cited Summary, Windows PC preview, accessible section tabs, preserved source quantities/rewards, visible independent findings, muted disabled approval, and the provider/request trace. No uncaught application page error or browser console error was captured.

## Numbered demo script — only what actually worked

1. Create **Final MVP Frostpeak Dev 20261027 01** and show its initially empty Sources page.
2. Load the synthetic Frostpeak sample and show its four indexed chunks.
3. Run local GDD review, continue locally, and resolve the explicit Windows PC human decision.
4. Open run setup with runtime preview enabled, memory allowed unspecified and two revisions available. Read the hosted-transfer warning before confirming.
5. Start the real Flash-Lite run once. This attempt takes about 65.5 seconds to reach review.
6. Show the exact cited Section 1 Summary, preserved quest objectives/rewards and Windows PC runtime field.
7. Show the NPC/quest tabs and the critic's two findings. Explain the zero-based situation labels and why its suggested ID changes need human interpretation.
8. Show **Approval blocked**, the still-available Request revision control, and the trace's three real Gemini nodes. End here: **this attempt did not approve or export**. Do not substitute another run's brief or present an API-only result as this browser run.

## Usage reconciliation and shutdown

Pacific quota date was **2026-10-27** throughout. Flash-Lite limits were RPM **5**, RPD **500**. Starting remaining budget **500** exceeded the required 20. Showcase `gemini-3.8-flash` remained unused at 0/20.

| Checkpoint | Flash-Lite requests | Remaining |
| --- | ---: | ---: |
| Before startup, CLI snapshot | 0 | 500 |
| After startup model-ID GET, CLI snapshot | 1 | 499 |
| After generation/critique, CLI snapshot | 4 | 496 |
| Final CLI snapshot before shutdown | 4 | 496 |

**Total delta: 4 Google requests = one startup model GET + three inference POSTs.** The run consumed **3/12** attempts. Per-node sequence reconstructs 1→2 for plan, 2→3 for generation and 3→4 for critique from ordered transport logs and each trace `request_attempts=1`; there were not separate CLI snapshots between every node. No approval, rejection, revision, export, retry or repair consumed quota.

Startup used the existing Compose service with a stdin-only override selecting the cached SDK image, `restart: "no"`, and the process environment listed above:

```powershell
$override | docker compose -f docker-compose.yml -f - up -d --no-build --pull never backend
# Frontend, from frontend/: NEXT_PUBLIC_API_URL=http://localhost:8000,
# LLM_PROFILE=dev, NEXT_TELEMETRY_DISABLED=1
npm run dev
# Usage CLI; reads only the reservation ledger
docker compose exec -T backend python gemini_usage.py
```

The first usage launcher used an unsupported `docker compose run --no-build` flag and exited before container execution, with zero Google requests. Corrected the launch command, not application code. Browser-driver waits also timed out for an exact wrapped label, the already-closed consent dialog and a section button locator; the observed textarea/tab roles were then used. These were locator/setup errors, not failed workflow/model steps or manual workflow retries.

Closed Chromium and exited its Node session. Stopped the frontend's `npm run dev` with Ctrl+C, then ran **`docker compose stop backend`**. Backend exited **0**, restart count **0**; `shutdown.log` records graceful cleanup-worker/application shutdown. Ports **3000 and 8000 had no remaining listeners**. Application PostgreSQL and Chroma were left running; no volumes or QA workspaces were deleted.

No code, `.env`, existing run, README or MVP status was changed. The only repository addition for this task is this report. No application-database tests, model probe, manual workflow retry, runtime approval, runtime bundle or Unity operation occurred. No push.

## Correction attempt on the same run

Attempt date: **2026-10-28 (Asia/Calcutta)**. Target run: **`4a1e7f1f-b6a2-410c-a746-d8e52daf2ba2`**.

**Verdict: FAIL — blocked during environment startup; no correction was submitted.** Approval, export, reviewed/final hash equality and final-artifact immutability were not reached or verified.

### Preconditions and exact failure

- Repository HEAD before this report update was `fdad260`, the preceding document-only acceptance commit. `git diff f79e059 HEAD -- backend frontend docker-compose.yml` returned no differences: application source still matches `f79e059281ffd302358b18e15e94cbbc864dc330`. No running backend could be confirmed.
- Docker was not running. `docker ps --format '{{.Names}} {{.Image}} {{.Status}}'` failed because the Docker Desktop Linux engine named pipe did not exist. `docker desktop status` reported: `Could not retrieve status. Is Docker Desktop running?` and suggested `docker desktop start`.
- Tried the normal startup **once**, using `docker desktop start`. It exited **1** with:

  ```text
  Failed to start Docker Desktop
  Docker Desktop terminated unexpectedly
  ```

- A subsequent read-only `docker ps` check again failed:

  ```text
  failed to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine;
  check if the path is correct and if the daemon is running:
  open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified.
  ```

Stopped at that real startup failure. No Docker repair, restart loop, image rebuild, alternate runtime, dependency installation or environment-file change was attempted.

### Requested flow and evidence limits

1. **Quota:** `backend/gemini_usage.py` could not be run in the required container environment because the engine was unavailable. Today's Pacific quota date, starting counts, remaining budget and final counts are **unverified**; the preceding attempt's historical counts are not reused as current evidence. The minimum remaining-budget precondition was not established.
2. **Run eligibility:** no live API or database access occurred. Current `awaiting_review`, revision `0/2`, review-event absence, draft hash and critique identity could not be reverified. Historical saved state is not proof of current eligibility.
3. **Browser correction:** not attempted. The supplied reason was not submitted, no target section was selected, and no finding-resolution control was used. There were **zero correction/review submissions**.
4. **Provider evidence:** no backend process or Gemini transport was started by this attempt, so there were **zero model requests made by this attempt**. There is no revision wire schema mode/byte size, Google response, local validation error, retry/backoff or per-node latency to report. This is not a measured before/after ledger comparison.
5. **Artifacts and review:** no new revision, critique, review event, proposal confirmation, approval, final artifact, blueprint or export was created by this attempt. No section diff, final hash comparison, immutability attempt or exported-brief assessment is possible. No application run was deliberately changed, including B3, B4b and the protected faulted walkthrough run.
6. **Screenshots:** none. No browser was launched; no screenshot or brief was fabricated. The earlier QA-folder screenshots remain historical evidence only.

### UX findings and assessment

| ID | Rating | Finding |
| --- | --- | --- |
| CA01 | **blocker (environment)** | Docker Desktop terminated during its single startup attempt, preventing the required live backend, quota check and browser correction. This is not evidence of a new dashboard or model defect. |

No new dashboard UX behavior or content quality was observed. The earlier quest-label inconsistency, copied objective dialogue and failed MVP proof remain unresolved; this attempt neither corrected nor retested them. There is no exported brief to assess.

### Demo script — only what actually worked

1. Show that the application source matches `f79e059` despite the later documentation-only commit.
2. Show the Docker engine/status failure and the single failed startup result.
3. Explain that the correction and all downstream actions were withheld because the live environment and quota preconditions could not be verified. **There is no successful product-flow demo from this attempt.**

### Cleanup and scope

Neither backend nor frontend was started by this attempt, and no browser session was opened, so there were no newly started application services to stop. Docker itself reported startup termination. No application data, source, `.env`, README or MVP file was modified; the only authorized repository change is this appended report. No push.

### Resumed with Docker running — 2026-10-28

**Verdict: FAIL — one real browser correction was submitted; Gemini returned HTTP 200, but its response failed local schema validation. No revised artifact, follow-up critique, approval or export was produced.** The earlier Docker-start failure above remains historical; it did not consume this correction attempt.

#### Preparation and eligibility

- Docker was now running with the existing application PostgreSQL and Chroma containers. Sandbox access to its named pipe was denied, so the same commands were run with the required host-tool permission; no application repair was made.
- Application source still matched **`f79e059281ffd302358b18e15e94cbbc864dc330`**: `git diff f79e059 HEAD -- backend frontend docker-compose.yml` was empty. HEAD before this addition was `fb7b0fd`, another document-only commit. The running backend used **`gamemind-revise-tests:local`**, image `sha256:77a2481d5d69bc58d1f4f2fa93a6ff032dbf6a9c653c93ea7545d095d9ba592a`, with **`<REPO_ROOT>/backend:/app`** source bind-mounted and restart policy **`no`**.
- Process-only settings: `LLM_PROFILE=dev`, `GEMINI_DEV_MODEL=gemini-3.5-flash-lite`, `GEMINI_TIMEOUT_SECONDS=180`, `DESIGN_AGENT_FALLBACK_TO_MOCK=true`, `PYTHONPATH=/app`. Effective revise fallback exclusion was `['revise']`; schema reduction nodes `['revise']`; literal-preservation threshold **6,000 bytes**; per-run cap **12**; job lease **300 seconds**. No `.env` change.
- Before starting the backend, `gemini_usage.py` reported Pacific date **2026-10-28**, Flash-Lite **0/500**, **500 remaining**, RPM **5**, not exhausted; Flash **0/20**, RPM **3**. The required remaining budget of 15 passed. The CLI itself did not contact Google.
- A PostgreSQL **READ ONLY** transaction confirmed the target run was **awaiting_review / human_review, revision 0/2, no review events**, one mutable v1 draft, and existing per-run usage **3/12**. No protected run was resumed, rejected or otherwise modified.
- Started the existing backend with the preceding stdin Compose override, cached image, `--no-build --pull never`; frontend with `NEXT_PUBLIC_API_URL=http://localhost:8000`, `LLM_PROFILE=dev`, `NEXT_TELEMETRY_DISABLED=1`, `npm run dev`. `/health` and `/ready` both returned **200**, database/Chroma healthy, effective `llm_provider=gemini`. The health response still says `ai_mode=local_demo` despite the effective hosted provider; this label is not evidence that the run is offline.
- Startup's model-verification GET returned **200**, moving Flash-Lite usage **0→1**. Known Chroma telemetry signature noise was non-fatal. No startup traceback, readiness failure or container restart occurred.

#### Browser action — exactly once

Used real installed Playwright/Chromium **149.0.7827.55**, headless, **1440×1000**, against `http://localhost:3000/design-agent` and the live backend. No intercepted routes, fixtures or `dashboard-states.mjs`.

Selected the existing **Final MVP Frostpeak Dev 20261027 01** workspace through the dashboard dropdown and opened its existing run. Read-only API verification returned **200**, current draft **`729caf30-1a03-49fb-82b7-0dab811ac4e6`**, critique **`b860c8ca-d8e6-492c-ad5b-d01a8b25b5f2`**. Its canonical v1 content hash still matched:

```text
ad1b7cee32ed49ca804b217362703569ef49a499da02df0cbac9af7d5d516d34
```

Opened **Request revision**. The form initially selected **Summary**, so explicitly unchecked it and checked **NPCs only**. Entered and verified this exact reason, then clicked **Send revision request ONCE**:

> The critic identifies a real numbering inconsistency, but the stored quest IDs match the spoken topics. Preserve Eldrin's completion eligibility as quest_2 because his line acknowledges sky-iron retrieval; change its situation to 'Quest 2 completion acknowledgment'. Preserve Kaelen's completion eligibility as quest_1 because his line acknowledges the border post; change its situation to 'Quest 1 completion acknowledgment'. Also correct Eldrin's progress label from Quest 0 to Quest 1 and Kaelen's progress label from Quest 1 to Quest 2, including corresponding manual-test wording. Do not swap quest IDs, change spoken lines, rewards, objectives or unrelated sections.

Retained browser request confirms `decision=reject`, `target_sections=['npc_archetypes']`, the exact current artifact ID and exact reason. No finding-resolution control was used; no second rejection, approval or retry request was made. Existing run consent remained in effect; no new consent dialog appeared for this correction.

#### Transport and failure

The single browser POST `/api/v1/design-agent/runs/4a1e7f1f-b6a2-410c-a746-d8e52daf2ba2/review` returned **502** after **4,352 ms**.

```text
2026-10-28T07:38:31.995563105Z Gemini schema node=revise mode=reduced bytes=11212
2026-10-28T07:38:35.675123536Z POST https://generativelanguage.googleapis.com/v1beta/interactions HTTP/1.1 200 OK
```

This is a locally rejected successful Google response, **not** a Google 400/503 or a timeout. The log retains wire mode and compact byte size, not the complete wire schema. Failed revise execution **`46635d67-32b0-4352-9a0f-977ae71c2b86`** records:

| Field | Actual result |
| --- | --- |
| Provider/model | Gemini / `gemini-3.5-flash-lite`; no mock revision substituted |
| Node latency | **3,848 ms** |
| Tokens | **4,004 input + 779 output = 4,783**; cost unavailable |
| Requests/retries/backoff | **1 request**, no retry or backoff |
| Finish / validation | `stop` / `failure_kind=schema`, `failure_code=structured_output_invalid` |
| Repair | `repair_skipped=governed_schema_failure`; no repair or truncation resend |
| Diagnostic error | `Gemini output has invalid governed design fields; regeneration is required.` |

Diagnostics report **81 validation errors**, but retain only the first **20** sanitized records. These include alternative union-arm failures; **81 is not a count of 81 independently established defects**. Actual returned values, their input types and union-arm names are not retained: `llm_provider.py` uses `errors(include_input=False, include_context=False, include_url=False)` and stores only rule codes and sanitized paths. Therefore **sanitized returned type is unavailable for every row below**; it would be dishonest to invent it. `<unknown_field>` is the actual retained redaction.

| Retained records | Sanitized path beneath `changes/0/<unknown_field>/` | Rule |
| --- | --- | --- |
| 1, 10, 12, 14, 17 | `artifact_path` | `literal_error`: allowed literal/path did not match that union arm |
| 2, 3, 5 | `replacement/0/<unknown_field>/dialogue_triggers/2/quest_index` | `less_than_equal`: upper-bound failure; the dialogue contract limits indices to 0–1 |
| 4 | `replacement/0/<unknown_field>/name` | `literal_error` |
| 6, 8, 9 | `replacement/1/<unknown_field>/dialogue_triggers/1/quest_index` | `less_than_equal` |
| 7 | `replacement/1/<unknown_field>/name` | `literal_error` |
| 11 | `replacement` | `literal_error` |
| 13 | `replacement` | `string_type`: that union arm expected a string |
| 15 | `replacement/0` | `string_type` |
| 16 | `replacement/1` | `string_type` |
| 18 | `replacement/0/stage` | `missing` |
| 19 | `replacement/0/quest_index` | `missing` |
| 20 | `replacement/0/situation` | `missing` |

The other **61** error records and the raw rejected model response cannot be recovered from these saved diagnostics. No extra model request was made to investigate them.

#### Exact UI result and persisted state

The visible error alert matched the API response:

> The revision failed; the previous draft and critique are unchanged. No revision was consumed; 2 successful revision slot(s) remain. Consecutive failed revisions: 1/3. Inspect the failed revision in the trace before trying again.

The dashboard also displayed **Saved revisions: 0/2**, **Consecutive failed corrections: 1/3**, and **Last correction error: Gemini output has invalid governed design fields; regeneration is required.** The NPC-only form and entered reason remained available. No retry was submitted.

Read-only API and PostgreSQL verification (`transaction_read_only=on`, then rollback) established:

- Status returned to **awaiting_review / human_review**. Saved revision count remains **0/2**, failed-correction count is now **1/3**. Per-run real-request counter rose **3→4/12**. Stored degraded remains **false**; that is **not** a successful correction claim. The trace explicitly records Gemini failure, not mock success.
- Exactly **one artifact**, the original mutable v1 draft, remains. Before/after API content and database content match; canonical draft hash remains **`ad1b7cee32ed49ca804b217362703569ef49a499da02df0cbac9af7d5d516d34`**. All sections, quest IDs, spoken lines, rewards and objectives are unchanged because no candidate was saved. The section-level diff is empty.
- Exactly **one critique** remains, with the same ID and unchanged before/after API content; its two medium findings and `needs_revision` verdict remain. No follow-up critique occurred. Its persisted canonical hash, calculated inside the read-only transaction, is **`efb166050c5ec7e25af4793598960eb312b1c66035de9906feb060125a201354`**.
- **Review events are NOT unchanged:** the legitimate browser correction recorded one **reject** event before attempting revision. Event **`df57aba8-2356-47af-954b-76ab6872030b`**, created **2026-10-28 07:38:31.833839 UTC**, reviewer **`local_developer`**, user ID null, contains the exact supplied reason. Before: **0 events**; after: **1 rejection**. This is normal current workflow behavior, not a second/manual rejection or an approval. It cannot truthfully be reported as an unchanged audit trail.
- Human-review execution 2 completed the rejection; revise execution 1 failed; human-review execution 3 is now waiting on the original draft. No existing checkpoint was repaired.
- The API returned, and the rendered dashboard visibly showed, the LIVE02 guard message:

  > This draft already has a recorded rejection. The correction failed and no revised draft was saved, so this draft cannot currently be approved. Request another correction or start a new isolated run.

Stopped here as instructed. No proposals were confirmed; no approval was attempted; no export, final artifact, reviewed/final hash comparison or immutable-final verification was possible. No runtime or Unity operation occurred.

#### QA evidence and screenshots

QA directory (outside the repository): **`<QA_DIR>/correction-same-run-20261028-01`**.

1. `01-before-correction.png` — original draft and review state.
2. `02-npcs-only-exact-reason.png` — only NPCs selected, supplied reason entered.
3. `03-correction-in-progress.png` — the single submitted correction.
4. `04-failed-correction-ui.png` — full error/review screen after failure.
5. `05-stopped-after-failure.png` — retained blocked state, no further submission.
6. `06-exact-error-alert.png` — exact error toast/alert.
7. `07-preserved-draft-counters.png` — original findings, saved revisions 0/2, failure count 1/3, retained NPC selection. Visually inspected this screenshot.

Additional evidence: `before-api.json`, `after-api.json`, `correction-response.json`, `browser-evidence.json`, `trace.json`, `database-verification.json`, `backend.log`, `usage-before.json`, `usage-after-startup.json`, `usage-after.json`. Initial usage snapshots transcribe the actual CLI outputs; final usage is captured CLI stdout. Offline assertions checked exact reason/target scope, one browser POST, identical draft/critique content and the one retained rejection event. No browser page exceptions were recorded.

#### Request accounting and cleanup

| Checkpoint | Flash-Lite today | Remaining | Flash today |
| --- | ---: | ---: | ---: |
| Before backend startup | 0 | 500 | 0 |
| After startup GET | 1 | 499 | 0 |
| After failed correction; final CLI | 2 | 498 | 0 |

**Total this attempt: 2 Google HTTP requests = one startup GET + one revise POST.** Per-node this attempt: plan **0**, retrieve **0**, generate **0**, revise **1**, follow-up critique **0**, finalize/export **0**. The original run's three earlier inference requests belong to the previous day/attempt and are not counted again. No retry, repair, correction re-ask or fallback-model request occurred.

Closed Chromium and exited the Node session. Stopped the frontend with Ctrl+C (expected interrupted-process exit), then `docker compose stop backend`. Backend exited **0**, restart count **0**, restart policy **no**; shutdown logs showed graceful worker/application termination. No remaining listeners on **3000/8000**. Existing PostgreSQL and Chroma were left running; no volume, project, run or QA folder was deleted.

#### UX findings, assessment and honest demo script

| ID | Rating | Finding |
| --- | --- | --- |
| CA02 | **blocker** | Even this explicit NPC-only numbering correction produced locally invalid model output. The user cannot reach approval/export through the requested path. Google availability and schema acceptance did not establish usable output. |
| CA03 | **annoying** | The revision form initially selected Summary although both visible critic findings concern NPCs. A reviewer must inspect and replace the default scope; otherwise the wrong section would be selected. |
| CA04 | **annoying** | The visible last error says regeneration is required, while the UI also offers further corrections and the API accurately reports two saved-revision slots/two consecutive-failure attempts remaining. The guidance does not identify which recovery is likely to work. No additional correction was tried. |

What worked: explicit scope selection, preservation of the original draft and critique, accurate saved/failure counters, visible 502/error trace, no mock revision, and the recorded-rejection approval guard. What did not work: the actual correction. The output still has the same real quest-label mismatches and copied quest-objective dialogue documented above; it is not newly improved content or a usable exported brief. No extra numeric inventions were assessed in a new revision because none exists. The original critic missed the progress-label and copied-dialogue issues; it was not rerun. **No brief exists from this attempt, so no exported-brief quality claim is made.**

Numbered demo script, limited to actions that actually worked:

1. Select the existing isolated Frostpeak workspace and inspect its saved v1 draft and critique.
2. Open Request revision, replace the default Summary selection with NPCs only, and enter the exact requested correction.
3. Submit once; show the visible failure and failed Gemini execution rather than claiming a successful revision.
4. Show that the original draft/critique and saved budget are preserved, failure count is 1/3, and approval is blocked by the recorded rejection. End the demo here. Approval/export are **not** successful demo steps.

No code, `.env`, README, MVP status or protected run was edited. This acceptance report is the only repository file changed; no push.

## Fresh-run approval attempts

Run C date: **2026-10-28 (Asia/Calcutta)**. **Overall verdict: FAIL under the requested acceptance rule.** The real browser completed generation, proposal confirmation, approval and technical-brief export on **attempt 1**, and the final artifact is immutable. However, reviewed/final content hashes differ by **one final-only memory metadata field**. Stopped at that mismatch, without modifying the result or making another attempt.

**Critic blocked approval: 0 of 1 completed attempts.** Attempts 2 and 3 were **not started**: attempt 1 was approvable, and the later hash mismatch independently required stopping. This is not a three-run reliability measurement or full MVP acceptance.

### Shared setup, scope and quota

- `git diff f79e059 HEAD -- backend frontend docker-compose.yml` was empty. Running application source matched **`f79e059281ffd302358b18e15e94cbbc864dc330`**; later commits before this task were documentation only. No code or `.env` changes.
- Used the cached **`gamemind-revise-tests:local`** SDK image, source bind mount **`<REPO_ROOT>/backend:/app`**, restart policy **`no`**, process-only `LLM_PROFILE=dev`, `GEMINI_TIMEOUT_SECONDS=180`, `DESIGN_AGENT_FALLBACK_TO_MOCK=true`, `PYTHONPATH=/app`. Effective model: **`gemini-3.5-flash-lite`** for all hosted nodes. Revise fallback remained excluded by default; no revise call occurred. Normal retry and per-run cap **12** stayed in place.
- First ran `gemini_usage.py` in a one-off container using those overrides, before backend startup. Pacific date **2026-10-28**: Flash-Lite **2/500**, **498 remaining**, RPM **5**; Flash **0/20**, RPM **3**. The minimum 30-request remaining-budget guard passed. CLI reads made no Google request.
- Started backend with the stdin-only Compose override and `up -d --no-build --pull never backend`; frontend with `NEXT_PUBLIC_API_URL=http://localhost:8000`, `LLM_PROFILE=dev`, `NEXT_TELEMETRY_DISABLED=1`, `npm run dev`. Health and readiness both returned **200**, effective provider `gemini`, healthy PostgreSQL/Chroma. Known non-fatal Chroma telemetry noise was ignored; no container restart or startup-stopping traceback occurred.
- Startup model verification consumed **one GET**, HTTP **200**; ledger rose **2→3**. It is counted separately from run inference. The health response still combined `llm_provider=gemini` with `ai_mode=local_demo`; the latter is not proof of offline execution.
- Drove real Playwright/Chromium **149.0.7827.55**, headless **1440×1000**, against the live frontend/backend. No route interception, fixtures, sign-in, finding adjudication, rejection or revision. Protected B3/B4b/faulted walkthrough/previously rejected run were not opened for mutation or changed. No runtime export/materialization or Unity operation.
- QA root, outside the repository: **`<QA_DIR>/fresh-run-approval-20261028-01`**. All screenshot names below are beneath its **`attempt-1`** subdirectory.

### Attempt 1 — approval/export worked; strict content equality failed

#### Workspace, source, decision and consent

| Record | Value |
| --- | --- |
| New workspace | **Run C Frostpeak approval 20261028 01** |
| Project ID | `run-c-frostpeak-approval-20261028-01` |
| Frostpeak source | `14d41feb-5757-47b0-9c52-662118414da1`, revision 1, four chunks |
| Resolved platform decision | `d3f9444c-7484-4349-8685-2e39dcc03558` |
| Run | **`fc541ba1-fa2d-48bc-bf04-20822bc37b18`** |
| Reviewed draft | `9e24ae35-3d46-46a3-a079-adfe20fd7700`, v1 |
| Frozen snapshot | `824a59b8-be30-4ad6-a45d-ff30076251b3` |

Created everything through the browser in the brand-new workspace. Loaded Frostpeak, ran local **Review GDD**, continued locally from its automatic hosted-review offer, then saved and marked resolved the exact decision:

> The target platform is Windows PC. Set unity_runtime_preview.content.target_platform to the exact string "Windows PC"; this is human design direction, not a GDD fact.

The same objective as the prior comparable run was used:

> Create a source-grounded design blueprint for Project Frostpeak with both starting NPCs and both quest hooks. Preserve every objective, quantity and reward. Include useful distinct spoken dialogue and practical implementation notes. Clearly label proposals; do not invent source support.

Run request had **max_revisions=2**, **defer_runtime=false** (runtime preview enabled), **allow_unspecified_memory=true** (same explicit memory scope as the comparable run), fresh-dialogue opt-in off and no fixed repeat/reset policy. Other three local questions remained open; they were not invented into source evidence.

The actual hosted-consent modal said:

> GOVERNED AI REVIEW — Start a cited review? The selected source revision may be sent to the configured hosted provider to create a cited draft and independent critique. No provider request is made until you confirm.

Clicked **Start governed review once**. Browser run creation returned **201**, reaching **awaiting_review** after **34,730 ms**. The selected-source/consent/decision setup is preserved in the request/response evidence.

| Browser mutation | Status |
| --- | ---: |
| POST `/api/v1/projects/` | 201 |
| POST `/api/v1/documents/demo/frostpeak` | 201 |
| POST `/api/v1/decisions/sync` | 200 |
| PUT decision text | 200 |
| PUT mark decision resolved | 200 |
| POST `/api/v1/design-agent/runs` | 201 |
| POST run `/review`, **approve only**, once | 200 |

#### Actual nodes, retries and requests

Transport logs show HTTP **200** for all four inference POSTs. No node used mock fallback, and the run was **not degraded**. The Summary itself was the correctly cited, locally extracted Section 1 premise, not a Gemini-authored premise.

| Node | Actual serving provider/model | Result / degraded | Latency | Input / output tokens | Real requests |
| --- | --- | --- | ---: | ---: | ---: |
| Plan | Gemini / Flash-Lite | completed / false | 5,422 ms | 395 / 174 | 1 |
| Retrieve | local retrieval / existing local lexical collection | completed / not a hosted fallback | 353 ms | 0 / 0 | 0 |
| Generate | Gemini / Flash-Lite | completed / false | 13,290 ms | 3,424 / 2,400 | 1 |
| Critique | Gemini / Flash-Lite | completed / false | 14,820 ms | 13,287 / 347, aggregate | **2** |
| Human review | local | waiting, then explicit approval completed | 41 ms recorded for resumed review | 0 / 0 | 0 |
| Finalize | local | completed | 68 ms | 0 / 0 | 0 |

The critic's first response failed the source-omission anchoring rule. Production code made its **one bounded corrective re-ask**, recorded as **`source_omission_reask=accepted`** / `independent_review_retries=1`. The initial response used **6,601 input / 193 output tokens**; re-ask **6,686 / 154**. This is why the trace has `retry_count=1`, `request_attempts=2`; it was **not** a transport 5xx retry or manual workflow retry. Diagnostics retain one initial `value_error` at the root, not the initial offending finding text. No claim is made about the truth of that discarded finding.

There were **zero transport retries/backoff**, truncation resends or repair completions. Total inference usage was **17,106 input + 2,921 output = 20,027 tokens**; cost unavailable, not measured zero. Full wire schemas: plan **2,364 bytes**, generation **20,525 bytes**, critique **16,071 bytes**, sent twice. No reduced revision schema was used.

#### Critique, scorecard and Approve control

Accepted critique:

> **ready_for_review** — Source coverage is fully realized and compliant with all document citations and design requirements.

**Findings: none.** Thus there are no accepted finding severities, paths, evidence indexes or quotes to list. Coverage: **covered** for Summary, narrative, art, NPCs, levels, systems, quests and runtime preview; **not_specified** for NPC memory. Exact accepted review and provenance remain in `review-evidence.json` and `final-trace.json`.

Scorecard before confirmations: grounding **1**, completeness **1**, consistency **1**, integration readiness **0**; **0.75 overall / passed=false**, with **Integration readiness only** as blocker and **20 unconfirmed proposals**. No unsupported/incomplete/recovered sections, quest integration gaps or request coverage gaps were reported. `finding-resolutions` read-only policy returned **`critique_blocked=false`**.

The Approve button was initially disabled solely because proposals were not confirmed, **not because the critic blocked it**. Checked the 20 displayed, artifact-bound proposal checkboxes individually. **Approve run then became enabled.** No degraded acknowledgement appeared: no fallback/degraded node existed, and the approval request correctly had `acknowledge_degraded=false`.

Clicked Approve **once**. Browser POST returned **200 in 426 ms**, run **completed**, final artifact v2, immutable. Request contained the exact draft ID and **20 proposal confirmations**. Only one review event exists, an **approve** event; no reject event was created.

#### Export and completed UI

Clicked **Download technical brief**. The governed run-final-artifact export GET returned **200** and triggered a real browser download, suggested filename `gamemind-agent-brief.md`. Saved **28,336 UTF-8 bytes** to:

```text
<QA_DIR>/fresh-run-approval-20261028-01\attempt-1\technical-brief.md
```

Brief structure: approved status/project/run/final version and frozen snapshot; source list; frozen resolved Windows PC decision; Summary/narrative/art/NPCs/memory/levels/systems/quests/runtime; source citations and frozen evidence excerpts. Quest state contracts are labelled **design proposals, not runtime bindings**, and checks are labelled **not executed**. Approved design is still `planning_only`, not a runtime release.

For repeat approve/reject/revise, the completed UI exposes **no such controls**: Approve run **0**, Request revision **0**, Send revision request **0**, Reject **0**. Thus those UI actions cannot be initiated; no hidden/forged API requests were sent. **These are UI unavailability results, not tested HTTP refusals.** After reload, the completed state, locked v2 artifact and export control still rendered. No second approval, rejection, revision or extra model request occurred.

#### Read-only persistence and strict integrity result

API and PostgreSQL **READ ONLY** transactions (verified `on`, then rolled back) confirm:

- Run **completed**, revision **0/2**, per-run real-request count **4/12**.
- Final artifact **`5c9d875a-4482-4063-9a82-b65808ac4fa1`**, **version 2**, **immutable=true**.
- GameBlueprint **`2e0d9e8b-e421-45f4-a7e7-cefb742833c2`**, same new project, **status=approved**.
- API final content equals persisted final content. Original v1 draft is retained.

Canonical hashes use Python `json.dumps(content, sort_keys=True, separators=(',', ':'), ensure_ascii=False)` then SHA-256, as in the previous verification. Both API snapshots and database rows produce:

```text
Reviewed v1: dbe29661c605d09f589d3963c4c94b33021af9f19e3c8b20dd10d79096e1b118
Final v2:    11b12b7aabc3f2c7f02982f7450c66b9af4336d1f22bf98f12960bf7618052b7
Equality:   FALSE
```

**Every differing JSON path (exactly one):**

| JSON path | Reviewed value | Final value |
| --- | --- | --- |
| `/npc_memory_design/memory_unspecified` | absent | `true` |

This is the existing, explicitly documented final-only metadata exception at **`backend/app/design_agent/workflow.py:895–897`**, which adds the marker to both candidate content and its expected comparison copy. The guard therefore allowed finalization. It is not a model-created lore change or the older six-note normalization defect. Nevertheless, the user's required rule for **this proof** is exact reviewed/final hash equality, with no exception: **FAIL**. No other content path differs. Stopped at that result; no final artifact/blueprint was edited or repaired, and no new attempt was started.

#### Plain assessment against the Frostpeak GDD

- **Good:** exact Section 1 premise; both starting NPCs; source lore/art/level details; both Ash Pass actions preserved independently; correct **100 gold + 250 XP**, **5 chunks**, **150 gold + sky-iron gear**. Windows PC is separately recorded as frozen human direction, not asserted as a GDD platform fact. Empty NPC memory remains honestly unassessed.
- **Numbering:** no Quest 0/off-by-one mismatch was found in this draft. Eldrin's progress/completion situations explicitly name **Quest Hook 1**, matching `quest_1` and border-post speech; Kaelen's explicitly name **Quest Hook 2**, matching `quest_2` and ore speech.
- **Dialogue:** no complete quest objective was simply pasted verbatim as the entire dialogue line. It now has speaker-labelled lines and NPC-specific greeting/progress/completion speech. However, quest dialogue hooks duplicate the same NPC progress lines in another section and mostly restate objectives. Eldrin sounds somewhat scholarly; Kaelen remains generic. This is improved scaffolding, not polished branching narrative.
- **Invented numbers:** no extra gameplay reward, quantity or timer number was found beyond source values. IDs, contract versions and generated test-state bookkeeping are implementation structure, not extra source-backed mechanics.
- **Unsupported/proposed facts:** source does not specify these speaker-to-quest/reward-giver assignments, a player party being wiped out, Eldrin paying resistance spoils, Kaelen's promised delivery reward, a camp location, flagpole interactions or death/reload/respawn rules. Major speaker associations, failure/restart rules and generated dialogue are labelled proposals, but details embedded in lines/situations/implementation notes are not individually distinguished as sourced versus invented. The source establishes faction choice matters; it does **not** resolve why the resistance pathfinder is delivering ore to the occupying commander. That branch needs human design work, not a claim of source contradiction or automatic correctness.
- **Concrete missed defect:** both NPC progress triggers have literal **`repeat_policy="name resets"`**, copied into their manual tests. This is a placeholder, not a specified repeat/reset rule. Greeting/completion use `no reset` without a clear frequency contract. The critic returned no finding despite the unusable progress policy.
- **Other missed issue:** Quest 1 says **“Ensure guard trigger zones reset correctly if player disengages.”** The source does not define that reset. It is not reconciled with the quest's explicit player-confirmed restart contract; the developer must decide what resets and when. The clean critic did not flag this ambiguity.
- **Brief usability:** usable as a first-pass design/integration discussion document: cited premise, distinct objective flags, event/action proposals, explicit limitations, frozen excerpts and repeatable proposed checks. Not ready to hand directly to an implementer as a finished contract: undefined reset language, faction/reward assumptions, verbose raw dialogue-trigger JSON and repeated boilerplate still need editing. The summary of the critic overstates compliance; no-findings does not validate these semantic details. No gameplay/manual integration tests were executed.

#### Screenshots and UX findings

All ten screenshots are in **`<QA_DIR>/fresh-run-approval-20261028-01\attempt-1`**:

1. `01-source-loaded.png`
2. `02-platform-resolved.png`
3. `03-run-setup.png`
4. `04-hosted-consent.png`
5. `05-generating.png`
6. `06-review-before-confirmations.png`
7. `07-proposals-confirmed-approve-enabled.png`
8. `08-after-approval.png`
9. `09-brief-exported.png` — dashboard after download; not an inline brief viewer.
10. `10-completed-after-reload.png` — visually inspected; locked completed state persists.

| ID | Rating | Finding |
| --- | --- | --- |
| C01 | **blocker for the requested integrity proof** | Final-only `memory_unspecified` metadata changes the canonical content hash despite successful approval/export. Existing exception permits this; the stricter acceptance rule does not. |
| C02 | **annoying** | A clean critic overlooks literal `name resets` placeholders and unsupported/ambiguous implementation details, while declaring full compliance. The user must still perform substantive content review. |
| C03 | **annoying** | Twenty mostly verbose/repetitive proposal checkboxes must be reviewed in the narrow sidebar; useful distinctions between sourced facts and proposals are buried in boilerplate. |
| C04 | **annoying** | The locked final Summary still displays **Review before approval**, and historical review advice says it cannot approve “this draft”. These labels remain confusing after completion. |
| C05 | **annoying** | Initial local Review GDD opens hosted consent before the platform decision is entered, requiring Continue with local review and then a second, deliberate entry into governed review. No inference happens on dismissal. |
| C06 | **cosmetic/wording** | Frozen evidence excerpts can begin/end mid-word or mid-heading, and brief dialogue triggers render as long JSON bullets. Citations are retained but the reading experience is rough. |

No browser page exceptions were recorded. Setup driver errors were limited to a diagnostic `main` locator matching nested main elements and attempting an absent Cancel button in the local-review offer (whose actual dismissal was Continue with local review). These caused no failed workflow/API request or duplicate mutation. No extra model request was used to recover the browser driver.

### Attempts 2 and 3

**Not run.** No additional workspace was created. Attempt 1 already cleared the critic gate and reached approval; the hash mismatch then triggered the mandatory stop. Critic-block frequency remains **0/1**, not 0/3.

### Final quota, evidence and cleanup

| Checkpoint | Flash-Lite requests today | Remaining | Flash requests |
| --- | ---: | ---: | ---: |
| Before Run C startup | 2 | 498 | 0 |
| After startup verification GET | 3 | 497 | 0 |
| After attempt 1 generation/critique | 7 | 493 | 0 |
| After approval/export; final CLI | 7 | 493 | 0 |

**Run C total: 5 new Google requests = one model-verification GET + four inference POSTs (plan 1, generate 1, critique 2).** Retrieval, human approval, finalize, export and reload used zero Google requests. No manual retry, transport retry/backoff, rejection, revision, finding-resolution write or sign-in. The run used **4/12** of its own cap. CLI snapshots, ordered transport logs and per-node `request_attempts` agree; intermediate per-node ledger positions **3→4→5→7** are reconstructed from those ordered calls, not separate CLI invocations between each node.

Root QA evidence: `usage-before.json`, `usage-after-startup.json`, `usage-after.json`, `backend.log`, `browser-evidence.json`. Attempt evidence: `start-response.json`, `review-evidence.json`, `reviewed-db.json`, `approval-response.json`, `final-api.json`, `final-db.json`, `final-trace.json`, `attempt-evidence.json`, `verification.json`, and downloaded `technical-brief.md`. Initial usage JSON transcribes the actual CLI output; later snapshots retain captured CLI stdout. Offline assertions verify one new run/approval, twenty exact confirmations, no reject/adjudication mutation, matching API/DB hashes and the **single** final-content difference.

Closed Chromium and exited Node. Frontend stopped with Ctrl+C; backend stopped with `docker compose stop backend`, exit **0**, restart count **0**, restart policy **no**, graceful worker/application shutdown. No remaining listeners on **3000/8000**. Existing PostgreSQL and Chroma remain running. No resources or historical data were deleted.

### Numbered demo script — only what worked

1. Create a fresh isolated workspace and load the Frostpeak sample.
2. Review local decisions, save and resolve Windows PC as human direction.
3. Open governed setup, retain runtime preview and explicit unspecified-memory scope, read hosted consent and start once.
4. Inspect the cited Summary, draft, evidence and accepted no-findings critique; explain that the critic used one bounded anchoring re-ask.
5. Review and select the twenty proposals; show Approve becoming enabled without a degraded acknowledgement.
6. Approve once; show completed, locked final v2 and retained review history.
7. Download the governed technical brief and show its saved file, citations, proposal labels and version.
8. Show approve/reject/revise controls are absent after completion, then reload and show the completed state persists.
9. Disclose the verified metadata hash difference. **Do not end the demo by claiming strict integrity acceptance, finished content quality or full MVP readiness.**

Only this acceptance document was changed in the repository. No `.env`, code, README, MVP status or protected-run modification; no push.
