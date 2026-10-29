# Live mock-profile browser walkthrough — 2026-10-27

## Verdict

**The browser and live backend worked. The requested end-to-end product flow did not pass.**

The fresh Frostpeak run reached human review, but its mock draft had an empty gameplay-systems section and the wrong content in Summary. Approval was correctly blocked. One targeted rejection reached the real revision node, which failed because it did not materially change gameplay systems. The original draft and critique survived, no saved revision slot was consumed, and the failure counter increased to 1/3. No approval or export was possible. Those later checks are **not verified**, not passes.

This proves live mock-path behavior and safety gates, not hosted generation quality or MVP readiness. No application code, `.env`, existing run, model configuration or runtime approval was changed. Only this document belongs in the local commit; screenshots and machine-readable evidence remain outside the repository.

## Method and environment

- Real headless Playwright Chromium **149.0.7827.55**, desktop viewport **1440 × 1000**.
- Frontend: `http://localhost:3000/design-agent`; live API: `http://localhost:8000`.
- Backend process: `LLM_PROFILE=test`, `DESIGN_AGENT_FALLBACK_TO_MOCK=false`. The factory selects `MockDesignAgentProvider` directly; the Gemini startup-verification branch applies only to `dev`/`showcase`. No model calls were made.
- No `page.route`, request fulfillment, intercepted fixture responses, or `dashboard-states.mjs`. Creation, upload, consent, run start and rejection were driven through the rendered UI. Read-only API calls checked persisted state.
- The in-app browser and persistent `node_repl` kernels failed to initialize (`failed to write kernel assets`). Direct installed Node/Playwright launched and drove real Chromium successfully. This was not replaced by a simulated DOM.
- The browser stayed open across an idle/continuation interval. Its accumulated 957 API responses include 919 `/health` responses. The shell polls health every 30 seconds (`frontend/src/components/DashboardLayout.tsx`); these totals are not a generation latency or evidence of a request storm.
- QA directory: `<QA_DIR>/browser-walkthrough-20261027-01/`.
- Raw saved run, draft, critique, trace, console and page-network evidence: `<QA_DIR>/browser-walkthrough-20261027-01/browser-evidence.json`.
- Screenshot links below are local files, intentionally not committed. A remote reviewer needs the QA files separately to view them.

## Part A — B3, read-only

Workspace: `gemini-acceptance-frostpeak-b-f04-flash-lite-20261026-01`.

Run: `eece5567-9b67-4505-a336-09e6c69bc907`.

The workspace was selected in the browser and its current run opened. No approval, rejection, confirmation, acknowledgement or other B3 write was submitted.

| Check | Observed result |
| --- | --- |
| Status and saved revisions | `awaiting_review`, **1/2**, `degraded=true` |
| Badge | **Local fallback** visible |
| Warning | “This run contains degraded or mock-fallback output. It is not proof of hosted-model quality. Explicitly acknowledge this before approval; all design checks still apply.” |
| Approval | **Approval blocked**, native button disabled |
| Extra acknowledgement | Separate bordered warning titled “Degraded output requires your acknowledgement”; unchecked, enabled checkbox with “I understand this draft contains degraded/mock-fallback output and explicitly accept that risk for design approval.” |
| Proposal confirmations | **20** individual, enabled, unchecked checkboxes; labels identify NPC/quest and the proposal. Counter: **0 of 20 selected for draft version 2**. Text explains selections are unsaved until approval and do not verify GDD facts/runtime behavior. None was checked. |
| Critique context | Saved critique says ready for judgment and records no findings; current checks still show integration readiness 0% and unconfirmed proposals. Approval remains blocked. |
| After inspection | Read-only run API response was JSON-identical to the before response, including status, revision count, artifact and critique. This was checked again at the end. |

Evidence: 01 — B3 full page (`<QA_DIR>/browser-walkthrough-20261027-01/01-b3-full.png`), 02 — degraded acknowledgement and disabled approval (`<QA_DIR>/browser-walkthrough-20261027-01/02-b3-degraded-guard.png`).

## Part B — fresh isolated workspace

### Identity and setup

- Workspace name: **Browser walkthrough Frostpeak mock 20261027 01**.
- Workspace ID: `browser-walkthrough-frostpeak-mock-20261027-01`.
- Uploaded existing demo file: `<REPO_ROOT>/docs/demo/sample_gdd_frostpeak.md`.
- Document ID: `a9c31ff1-7ff6-4a9c-b9e3-d5bf66093d35`; revision 1, **4 indexed chunks**.
- Run ID: **`1b00f97a-04c6-4dd2-b3a7-bf839d4dfaa2`**.
- Draft artifact ID: `84793e3a-8312-44d9-84e2-89eb9d403acf`, version **1**.
- Objective: “Create a cited, reviewable Frostpeak design blueprint covering the two starting NPCs and both quest hooks. Preserve source objectives and rewards, and label implementation proposals.”
- Checked **Design only — defer runtime integration** and **Allow NPC memory to remain unspecified for this run**. Left **Generate fresh dialogue** unchecked and the optional repeat/reset policy blank. These are disclosed scope choices, not a waiver of other checks.

### Actions and outcomes

| Step | Actual browser/API outcome |
| --- | --- |
| Create workspace | UI modal → `POST /api/v1/projects/`, **201**; new workspace selected |
| Upload Frostpeak | Actual file input → `POST /api/v1/documents/upload`, **201**; success message and 4 source chunks visible |
| Configure run | Selected uploaded source, entered objective and the scope options above |
| Grant hosted-transfer consent | Clicked **Start design run**, inspected the **Governed AI review** dialog, then clicked **Start governed review**. Dialog said the source revision “may be sent to the configured hosted provider.” This remained an offline mock run; the confirmation did not cause a Google transfer. |
| Start run | `POST /api/v1/design-agent/runs`, **201**; response `awaiting_review`, provider `mock`, `degraded=false`; about **945 ms** from confirmation to response |
| Inspect draft | Used actual Summary, NPCs, Quests and Systems tabs; opened frozen Source evidence and inspected independent critique |
| Reject once | Clicked **Request revision**; selected **Systems** only and submitted the reason below |
| Revision result | `POST /api/v1/design-agent/runs/1b00f97a-04c6-4dd2-b3a7-bf839d4dfaa2/review`, **502**, about **633 ms** |
| Saved state after failure | Still `awaiting_review`; same artifact ID/version/content and same critique; `revision_count=0`, `max_revisions=2`, consecutive failures **1/3** |
| Proposal confirmation | **0 proposal checkboxes** existed on this fresh draft. No confirmations could be submitted. B3's 20 proposals were not used as a substitute. |
| Approve | **Approval blocked** remained disabled. No forced click, injected event or API bypass was used. |
| Open/export brief | No brief/export controls were available for this unapproved run. No final artifact or brief was produced/downloaded. |
| Approve/reject/revise after completion | **Not reached and not verified.** The run never completed. No second rejection or revision attempt was submitted. |

The one rejection reason was:

> Gameplay systems is empty despite source-supported faction/world-state consequences and gold/XP rewards. Populate the supported systems with citations, preserving the two NPCs and both quest objectives and rewards.

The saved failure was:

> Revision did not materially change every human-targeted section; unchanged: gameplay_systems

The UI displayed:

> The revision failed; the previous draft and critique are unchanged. No revision was consumed; 2 successful revision slot(s) remain. Consecutive failed revisions: 1/3. Inspect the failed revision in the trace before trying again.

After recording the failure, **Cancel** closed the client-side revision form. It did not submit another review action. The fresh QA run is deliberately left at the checkpoint above.

### What the draft and critique actually contained

- **Summary is wrong for its section.** Its description starts “The visual identity of Project Frostpeak utilizes a Stylized Dark Fantasy theme” and describes colors/textures, rather than the pathfinder, occupied kingdom and resistance premise present in the GDD.
- Both **Eldrin** and **Kaelen** were extracted, with their source descriptions and citations. Their dialogue hooks and triggers were **None specified**. This is source extraction, not useful newly authored dialogue.
- Both quest hooks retained their visible objectives and rewards: reclaim the border post, clear guards/raise the Northern flag, **100 gold and 250 XP**; mine **5** chunks of sky-iron, **150 gold and sky-iron gear**. But structured `Objectives`, dialogue hooks, failure states and state contracts showed empty/unspecified values. The singular `Objective` contains prose while the plural `Objectives` says **None specified**.
- **Systems** had **0 citations** and every displayed field empty: economy, core loop, game modes, progression, accessibility and constraints. The warning “No explicit economy, rewards, or crafting rules found in the source document” is overbroad: the GDD and visible quest tab explicitly contain gold/XP/item rewards. That does not establish a complete economy, but it does contradict the blanket absence wording.
- Current checks showed **47%** pre-approval quality: grounding 88%, completeness 0%, contradiction checks 100%, integration readiness 0%. The high contradiction score is not proof of design quality; missing content still blocked approval.
- The mock critique said **10 review items**. The screen also included a separate high-severity current system finding for empty design content. The integrity gate correctly refused to treat warnings/citations as content.
- Each saved mock finding displayed **“Finding origin is unknown or stale. A new critique is needed before this finding can be dismissed.”** Human finding review was read-only with a signed-in-owner/editor requirement, despite this being a newly created local mock run.
- Frozen evidence opened from the Quests tab showed the actual stored revision-1 excerpt, including both quest objectives and reward amounts. Systems correctly showed no recorded evidence references for its empty output.

### Persisted node trace

| Node | Provider | State | Stored latency |
| --- | --- | --- | ---: |
| plan | mock | completed | 8 ms |
| retrieve_evidence | local_retrieval | completed | 310 ms |
| generate_blueprint | mock | completed | 29 ms |
| critique | mock | completed | 22 ms |
| human_review, initial | system | interrupted | 0 ms |
| human_review, rejection | system | completed | 42 ms |
| revise | mock | **failed** | 27 ms |
| human_review, return | system | waiting | 0 ms |

The pure mock profile is not the same as hosted fallback: this fresh run reports `provider_name=mock`, `degraded=false`. No Gemini/NVIDIA node served it. Trace “reported tokens” are not evidence of hosted requests or billing.

## Part C — UX findings

| ID | Rating | Finding, user impact and evidence | Focused recommendation, not implemented |
| --- | --- | --- | --- |
| UX01 | **blocker** | The included Frostpeak demo cannot reach approval on this mock path: empty Systems has no citations, Summary shows art direction, and the current integrity gate blocks completion. This is not a usable happy-path demo. Screenshots 10, 18. | Correct the offline extraction/section selection and establish an approvable included-demo baseline without weakening checks. |
| UX02 | **blocker** | The one normal targeted revision did not change Systems and returned 502. The user cannot recover this particular blocker through the tested revision attempt. State preservation is good, but there is no approved/exportable result. Screenshots 15–20; saved trace error above. | Make the mock revision either perform the supported correction or explicitly explain that this correction is unsupported before promising a revision. Keep failure-slot protections. |
| UX03 | **annoying** | The critique warns that rewards were not found while both reward amounts are visible in Quests and the frozen excerpt. Fresh findings also all look “unknown or stale,” so the review appears broken or unreliable. Screenshots 12–14, 20. | Make absence wording reflect the actual extracted evidence, and give fresh mock findings accurate provenance. Do not conflate incomplete economy design with absent rewards. |
| UX04 | **annoying** | Approval is in a long, narrow right rail. Scrolling to its bottom leaves most of the screen blank; B3 requires reading 20 proposal checkboxes before the separate acknowledgement and final action. Important choices are far from the draft. Screenshots 01–02, 19. | Keep the action summary easy to find and group proposals by record/section; retain explicit per-proposal review. |
| UX05 | **annoying** | The disabled **Approval blocked** control remains a bright lime primary button with strong border/shadow. It visually invites clicking even though it cannot act. Native disabled behavior is correct. Screenshots 02, 19. | Give disabled approval a clearly disabled appearance while retaining the visible reason. |
| UX06 | **annoying** | Mock setup uses the hosted-transfer consent dialog without a prominent offline/mock explanation. The post-start provider is only small `mock` metadata. An interviewer can reasonably ask whether an actual AI provider was used. Screenshot 09; trace confirms mock throughout. | Name the effective offline mode in setup and consent; distinguish permission from an actual data transfer. |
| UX07 | **cosmetic** | Raw design-schema presentation exposes `Fresh Dialogue false`, UUID evidence references and many `None specified` rows. The duplicate singular/plural Objective displays make intact source objectives look missing. Screenshots 11–12. | Present developer-facing design content first; group absent fields and technical metadata rather than rendering the schema literally. |

There were **0 uncaught page JavaScript errors**. The only captured browser-console error was the failed revision's `502 Bad Gateway` resource message. Of captured API responses, that review POST was the only HTTP status >=400. The UI showed a specific recoverable error rather than crashing or losing the draft. Browser-driver locator timeouts were automation mistakes, not counted as application failures: exact text/accessibility matching and an assumed `tabpanel` role needed adjustment.

No meaningful server wait was slow in this check: creation returned in roughly 945 ms and the failed correction in 633 ms. Time spent idle, reading evidence, taking screenshots and across the continuation gap is not model latency. This was not a production performance benchmark, responsive audit or accessibility certification.

## What worked, in natural demo order

1. **Create a game workspace:** the normal modal creates it, selects it and keeps the source/run lists isolated.
2. **Upload the GDD:** success feedback names the file, shows its source type, and exposes all four chunks for inspection.
3. **Declare scope before starting:** runtime deferral and memory-unspecified choices are visible and remain fixed on the run.
4. **Confirm transfer permission deliberately:** the start dialog requires another deliberate action. In this check it still used only mock code.
5. **Inspect a versioned draft:** tabs show two extracted NPCs and both source quest objectives/rewards. Do not describe this as creative hosted generation.
6. **Open frozen evidence:** the citation panel shows the saved revision and actual excerpt, not silently changed latest-source content.
7. **Show honest quality gates:** missing systems content remains a blocker even with positive scores in other dimensions.
8. **Request a scoped correction:** explicit target-section selection and written feedback are available. The failure is visible in both the banner and trace.
9. **Demonstrate no lost work:** a failed correction preserves the artifact/critique, does not consume a saved revision slot, and accurately shows the separate failed-attempt counter.
10. **Demonstrate degraded review safety on B3:** badge, warning, proposal selections and extra acknowledgement are visible; approval stays disabled without those actions. No B3 state was changed.

The honest demo ends at the current blocked review. **Do not script approval/export or post-completion immutability as successful based on this walkthrough.**

## Screenshot index

All files are under `<QA_DIR>/browser-walkthrough-20261027-01/`.

| File | Captured state |
| --- | --- |
| 01-b3-full.png (`<QA_DIR>/browser-walkthrough-20261027-01/01-b3-full.png`) | B3 full read-only review |
| 02-b3-degraded-guard.png (`<QA_DIR>/browser-walkthrough-20261027-01/02-b3-degraded-guard.png`) | Unchecked acknowledgement and disabled approval |
| 03-new-workspace-dialog.png (`<QA_DIR>/browser-walkthrough-20261027-01/03-new-workspace-dialog.png`) | Workspace creation modal |
| 04-new-workspace-created.png (`<QA_DIR>/browser-walkthrough-20261027-01/04-new-workspace-created.png`) | Immediately after creation, including loading transition |
| 05-sources-empty.png (`<QA_DIR>/browser-walkthrough-20261027-01/05-sources-empty.png`) | New workspace's empty source library |
| 06-frostpeak-uploaded.png (`<QA_DIR>/browser-walkthrough-20261027-01/06-frostpeak-uploaded.png`) | Successful upload and indexed chunks |
| 07-run-setup.png (`<QA_DIR>/browser-walkthrough-20261027-01/07-run-setup.png`) | Initial run setup |
| 08-run-configured.png (`<QA_DIR>/browser-walkthrough-20261027-01/08-run-configured.png`) | Objective and scope selected |
| 09-hosted-transfer-consent.png (`<QA_DIR>/browser-walkthrough-20261027-01/09-hosted-transfer-consent.png`) | Consent dialog before confirmation |
| 10-awaiting-review-v1.png (`<QA_DIR>/browser-walkthrough-20261027-01/10-awaiting-review-v1.png`) | First complete review screen |
| 11-draft-npcs.png (`<QA_DIR>/browser-walkthrough-20261027-01/11-draft-npcs.png`) | NPC tab |
| 12-draft-quests.png (`<QA_DIR>/browser-walkthrough-20261027-01/12-draft-quests.png`) | Quest tab |
| 13-frozen-evidence.png (`<QA_DIR>/browser-walkthrough-20261027-01/13-frozen-evidence.png`) | Loaded frozen source excerpt |
| 14-independent-critique.png (`<QA_DIR>/browser-walkthrough-20261027-01/14-independent-critique.png`) | Independent critique panel |
| 15-reject-once-reason.png (`<QA_DIR>/browser-walkthrough-20261027-01/15-reject-once-reason.png`) | Systems-only rejection and exact reason |
| 16-revision-failed-banner.png (`<QA_DIR>/browser-walkthrough-20261027-01/16-revision-failed-banner.png`) | Failed revision banner |
| 17-revision-failed-full.png (`<QA_DIR>/browser-walkthrough-20261027-01/17-revision-failed-full.png`) | Full page after failed correction |
| 18-systems-empty-approval-blocked.png (`<QA_DIR>/browser-walkthrough-20261027-01/18-systems-empty-approval-blocked.png`) | Empty Systems, source warnings and approval blocker |
| 19-approval-still-disabled.png (`<QA_DIR>/browser-walkthrough-20261027-01/19-approval-still-disabled.png`) | Disabled approval, 0/2 saved revisions and 1/3 failed attempts |
| 20-failed-revision-trace.png (`<QA_DIR>/browser-walkthrough-20261027-01/20-failed-revision-trace.png`) | Expanded persisted node trace |

## Final safeguards and limits

- `docker compose exec -T backend python -B gemini_usage.py` at the end reported Pacific date **2026-10-26**, `gemini-3.5-flash-lite` **16** requests and `gemini-3.8-flash` **0**. Counts exactly match the pre-walkthrough baseline. No Google request or model call was made.
- Captured UI mutations were only: create new project, upload the GDD, create this run and submit its one rejection. No B3 review mutation occurred; its final API response remained identical to the before snapshot.
- New QA data is retained in the new workspace. No cleanup deleted or modified existing application/QA data.
- The browser was closed after saving evidence. The existing frontend and offline backend were left running.
- `.env` hash and tracked source state were unchanged before the report. Existing untracked `docs/audit/` was not edited/staged. No implementation fix, model switch, fresh test-suite run, runtime materialization or Unity action was performed.
- Approval, brief export and post-completion approve/reject/revise handling remain **unverified on the fresh run** because the normal path was blocked. Mobile layout, keyboard-only operation and production/hosted reliability were not tested.
