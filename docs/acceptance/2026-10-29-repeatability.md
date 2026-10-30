# DEV workflow repeatability — three fresh Frostpeak runs

Executed **2026-10-30, Asia/Calcutta**; quota date **2026-10-29, America/Los_Angeles**. The filename retains the requested date. `<QA_DIR>` is the author's local, unpublished QA evidence folder. All evidence below is under `<QA_DIR>/repeatability-20261030-01/`; screenshots, exported briefs and database snapshots are not in this commit.

## Verdict and results

**Partial repeatability evidence, not full acceptance.** Three independent fresh runs reached real human review and approved immutable finalization. Two completed a saved browser brief download; R1's download was canceled and was not retried. All three passed the documented-metadata integrity verifier. Only R3 contained an eligible correction target, so this batch demonstrates **one** two-field correction, not three repeatable corrections or failed-correction recovery. Semantic defects still escaped the critic. No general reliability claim follows from these three runs.

| Run | Completed nodes; latency | Critic / findings | Advisories and accuracy | Defects/gaps not caught | Correction | Approval / export / verifier | Real inference attempts |
| --- | --- | --- | --- | --- | --- | --- | ---: |
| R1 | Plan, retrieve, generate, critique, review, finalize; start API **11,397.21 ms** | `ready_for_review`; **0 findings** | **0**; no applicable exact match | Faction-choice/world-state consequence omitted; empty quest dialogue lists and only greeting NPC stages limit usefulness | Skipped: no eligible copied hook or contradictory quest-label target | Approved; export GET **200**, browser download **canceled**, no saved/read brief; verifier **EQUAL_EXCEPT_DOCUMENTED_METADATA** | **3** |
| R2 | Plan, retrieve, generate, critique, review, finalize; start API **16,202.92 ms** | `ready_for_review`; **0 findings** | **0**; no applicable exact match | Empty quest dialogue lists; greeting says before assignment but eligibility is already active, requiring clarification | Skipped: no eligible copied hook or clearly wrong quest-number/topic situation | Approved; brief saved/read; verifier **EQUAL_EXCEPT_DOCUMENTED_METADATA** | **3** |
| R3 | Plan, retrieve, generate, critique, correction, second critique, review, finalize; start API **22,209.29 ms**; correction API **11,494.27 ms** | Initial and follow-up `ready_for_review`; **0 findings** each; initial critique recovered from one Google **503** | **2 medium exact-copy true positives**, removed after correction; **0 false positives** | Unmarked keyboard/mouse input; zero-based Quest labels in assumptions; unsupported return instruction; rewritten first hook still closely restates objective | **One request / two fields saved**, exactly two hook changes plus two permitted annotations; better spoken form, modest writing quality | Approved; brief saved/read; verifier **EQUAL_EXCEPT_DOCUMENTED_METADATA** | **6**, including the failed 503 attempt |

### Counts out of three, not percentages

- Reached human review: **3 out of 3**.
- Reached successful approval/finalization: **3 out of 3**.
- Saved browser brief export plus approval and verifier: **2 out of 3**. R1 is not counted as a successful end-to-end download.
- Critic cleared the initial draft: **3 out of 3**, despite the problems described below. R3 also cleared after correction.
- Runs where advisories fired and were correct: **1 out of 3**; two true-positive entries in R3. False-positive runs: **0 out of 3**.
- Corrections attempted: **1 out of 3**; successful saved scope-conforming corrections: **1 out of 3**, changing two strings in one request. R1/R2 skipped, not failed.
- Failed-correction dead-end recovery: **0 out of 3 exercised**; no failure was induced, so no successful or failed recovery outcome is claimed.
- Runs with a definite source-coverage/unsupported-content/numbering defect that escaped every automated check: **2 out of 3** — R1's omitted faction-choice consequence and R3's unsupported input/incorrect assumption labels. R2's sparse quest dialogue and ambiguous greeting eligibility are separately reported quality/implementation gaps, not counted as a definite source contradiction.
- Mock-served/degraded runs: **0 out of 3**. Runtime/Unity acceptance: **not tested**.

## Preconditions, environment and protocol

At the start, `git branch --show-current` was **main**, HEAD **`7da123b05514ad8d1785b4774785fa76ef8b1111`**; only `?? docs/audit/` was untracked. `git merge-base --is-ancestor` passed for **3a88cad, 2eb1880, 964eae7**. Created **evidence/repeatability-1** from that main HEAD. No application source, `.env`, dependency or configuration file changed; no push. The earlier unavailable Docker engine caused no inference request. Once Docker was on, the shell sandbox initially denied its pipe/local sockets; authorized host execution worked. Those were launch/access limitations, not extra workflow attempts.

Scope: MVP **P1.3–P1.5, P2.6, P3.5, P4.1–P4.2, P5.3**, limited to Frostpeak and three runs. No checklist or whole-phase acceptance is changed. `MVP.md` remains unchanged under the requested report-only scope.

- Existing image **gamemind-revise-tests:local**, SHA-256 `77a2481d5d69bc58d1f4f2fa93a6ff032dbf6a9c653c93ea7545d095d9ba592a`, with pinned Google SDK, current backend source bind-mounted at `/app`.
- Process-only Compose overrides: **LLM_PROFILE=dev**, **GEMINI_TIMEOUT_SECONDS=180**, **DESIGN_AGENT_FALLBACK_TO_MOCK=true**, **PYTHONPATH=/app**, restart policy **no**. Model **gemini-3.5-flash-lite** for all hosted nodes; fallback-disabled nodes **["revise"]**, reduction nodes **["revise"]**, keep-literals threshold **6,000 bytes**, per-run cap **12**, inline execution. No production retry-policy override.
- Ran `gemini_usage.py` in a one-off SDK container **before backend startup**: Flash-Lite **11 used / 489 remaining**, **5 RPM / 500 RPD**; Flash **0 / 20**, **3 RPM / 20 RPD**. Required remaining threshold **40** passed.
- Backend started with `docker compose -f docker-compose.yml -f - up -d --no-build --pull never backend`, with the overrides supplied on stdin, not saved to a file. Normal image startup remained `alembic upgrade head && exec uvicorn main:app --host 0.0.0.0 --port 8000 --reload`.
- Alembic current and heads both **f4a6b8c0d123**; **no pending migration applied**. Health/readiness **200**, DB/Chroma healthy. Restart count stayed **0**. Startup model verification used one Google GET, **11 -> 12**.
- Frontend started with normal `npm run dev`, process-only `NEXT_PUBLIC_API_URL=http://localhost:8000`, telemetry disabled and npm offline. No install/build/source rewrite.
- **Real Playwright Chromium 156.0.8078.4**, installed executable, headless 1440×1000, fresh context, `acceptDownloads=true`, against `http://localhost:3000` / live port 8000. No request interception, fixture responses, response substitution or API mutation outside browser controls. Passive response/DOM/screenshot capture only. All auxiliary API evidence requests were GETs; database evidence explicitly asserted `transaction_read_only=on`.
- Three new workspaces, one source and one run each. Old QA runs/workspaces were not changed. No sign-in, reject, legacy section revision, finding-resolution action, retry-critique, runtime materialization or Unity action.

Common setup through the browser: New project, Sources → Load Frostpeak demo, Decisions → Review GDD → Continue with local review, save and mark Platform and controls resolved, Review GDD again, grant consent. The exact frozen decision in all three was:

> unity_runtime_preview.content.target_platform must be "Windows PC"; this is human design direction, not a GDD fact

Runtime deferral unchecked (**defer_runtime=false**); unspecified-memory scope checked (**allow_unspecified_memory=true**). The normal decisions-page start omits `max_revisions`; its existing default produced **2**, verified in all persisted runs. `fresh_dialogue=false` remained the normal default; no extra requirement for three NPC stages was injected. Each start button was clicked once.

Consent shown in every run:

> The selected source text may be sent to Google's Gemini API to create a cited draft and independent critique. On the free tier, Google may use submitted content to improve its products. Use only demo or non-confidential material. Mock mode runs offline and sends nothing to a hosted provider. No provider request is made until you confirm.

All initial starts returned **201 / awaiting_review**. Initial Approve was disabled solely pending proposal confirmations: scorecard **75%**, grounding/completeness/consistency **100%**, integration readiness **0%**, blocker **Integration readiness**. Confirming the displayed proposals enabled approval; every actual approve returned **200 / completed**. No degraded acknowledgement appeared because none of the hosted nodes fell back to mock. These were design approvals, not content-quality certification or runtime release.

## R1

Workspace **repeatability-r1-frostpeak-dev-20261030**; source **3a7aa32b-3267-490c-ad39-51f5485830a7**; decision **7ba57aa2-5cf4-4243-80a8-a4f842aaf3f1**; run **88c53a97-a9d2-429b-aa1c-8d68a2662bc2**. Draft v1 **e826cabf-c34d-4f3c-8a6c-e620b804b777**; final v2 **e965ea99-2d5f-45a3-9d20-31f2f98a9bc0**. Revisions **0/2**, consecutive correction failures **0/3**, not degraded.

Critic verdict **ready_for_review**, findings **[]** — no severity/path/evidence index to enumerate. Coverage: all nine sections `covered` except `npc_memory_design=not_specified`. It claimed no missing source elements or defects. The advisory panel displayed **“No exact matches found; this is not a quality guarantee.”** Persisted `advisories=[]` was bound to v1.

Both `/quest_hooks/content/quests/0/dialogue_hooks` and `/quest_hooks/content/quests/1/dialogue_hooks` were **[]**. NPCs each had only one greeting, with no numbered quest situation mismatch. There was no allowable existing copied hook or clearly contradictory quest-label field to correct. **Skipped correction**; no reason, replacement, correction request or before/after correction pair exists. Empty collections cannot be created through the first-version field correction allowlist, and no broader revision was attempted.

Confirmed **13** proposals, approved **once**, final immutable and approved blueprint present. Export GET returned **200**, but Playwright's single download failed with **`download.saveAs: canceled`**. Browser console/page errors were both empty; there was no observed application error banner. The cause cannot be assigned to application code versus this browser/driver from the retained evidence. **Did not retry export**, fetch a replacement brief, or claim it was saved/read. The run ended at that export failure; subsequent inspection was read-only.

Draft assessment against the GDD:

- Correct Section 1 exact cited summary, named setting/lore/art/level, both required Ash Pass actions, five-chunk mining and both source rewards. No invented guard quantity, zero-XP reward, difficulty rating, input-method claim or false source-order assertion found.
- The GDD's explicit **“Faction choice holds high consequences for gameplay and world state flags”** is absent from the generated narrative/systems content. Source references alone do not preserve this design consequence; the critic's complete-coverage claim missed this omission.
- Quest dialogue is absent, not copied. Greetings are plausible creative proposals but sparse. No progress/completion stages were required by this particular normal start, so their absence is not reported as a schema violation.
- Speaker/quest assignments, no-reset policies and state/event names are proposals, not new GDD facts. No executable bindings, explicit failure/restart design or tested implementation exists. Windows PC has human-decision provenance, not source authority.

Verifier **EQUAL_EXCEPT_DOCUMENTED_METADATA**, only `/npc_memory_design/memory_unspecified=true`; no offending paths. R1 proves approval/integrity here, **not a completed saved-download journey**.

Screenshots: `R1-01-workspace.png`, `R1-02-source.png`, `R1-03-decision.png`, `R1-04-consent.png`, `R1-05-review.png` (still Decisions after start), `R1-06-design-review.png`, `R1-07-quests.png`, `R1-08-approve.png`, `R1-09-export-canceled.png`. Data: `R1-before.json`, `R1-final.json`, `R1-trace.json`, `R1-db.json`.

## R2

Workspace **repeatability-r2-frostpeak-dev-20261030**; source **427b3f05-f1e4-4909-9dcd-c62ca2f5cdb7**; decision **1b550f46-f58d-4dfa-923e-d266893fd094**; run **f7dc4a1a-15a0-4c2f-9dbb-ae8d87f1537d**. Draft v1 **6b851d70-940c-49e4-8564-b6a7b89a596a**; final v2 **721229bd-dd24-49f2-8e3d-62b490d94c7b**. Revisions **0/2**, failures **0/3**, not degraded.

Critic **ready_for_review**, findings **[]**; same coverage map as R1. It claimed complete and consistent coverage. Advisory panel again displayed **“No exact matches found; this is not a quality guarantee.”**, persisted empty list bound to v1. Scorecard **75%**, **14** pending proposals initially.

Both quest hook lists were empty again. NPC situations had no numeric Quest label and no clearly swapped quest topic. The greetings say **“Initial meeting before quest assignment”**, while requiring an active incomplete quest. This needs lifecycle clarification, but is not a definite swapped quest-label defect; no ambiguous correction target was manufactured. **Skipped correction**, no correction reason or replacement pair. Confirmed **14** proposals; one approval succeeded.

One browser export succeeded: download `R2-brief.md`, **22,921 bytes**, matching the passively captured **200** export response byte-for-byte. Read the actual saved brief. Final is immutable; approved blueprint exists. Verifier **EQUAL_EXCEPT_DOCUMENTED_METADATA**, only the permitted memory flag, no offending paths.

Brief assessment:

- Correct exact premise, factions/lore/art/level, quest actions, **5** chunks, **100 gold + 250 XP**, **150 gold + sky-iron gear**. Faction-choice/world-state consequences are retained, unlike R1. Windows PC is explicitly presented as frozen human direction with a runtime review note.
- No quest hooks are offered as dialogue. That avoids the exact-copy defect but supplies no quest invitation to implement. The three NPC stages per character are generally usable generic prototypes, not polished character writing.
- Greeting situation/eligibility is ambiguous: “before quest assignment” versus `lifecycle=active`. The manual test repeats both rather than explaining how they coexist. The critic did not request clarification; the numeric-label advisory correctly abstained. This is not counted as a proven source contradiction in the counts above.
- Assumptions say `quest_index 0/1`, while IDs are `quest_1/quest_2`; these are explicitly indexes, not a false claim that a Quest 0 exists. They are developer-unfriendly but not counted as a numeric-label advisory false negative.
- Flagpole interaction, “eliminate all guards,” no-reset rules and speaker/quest links are implementation proposals, not source-defined mechanics. Failure/restart remain unspecified. No new reward/count/difficulty/input-method or explicit source-order assertion was found. No invented persistent-memory capability.
- Export is a verbose cited scaffold with JSON trigger dumps and duplicated unexecuted checks. It states approved version **2**, source IDs, frozen evidence and proposal warnings; it is not an implementation-ready spec.

Screenshots: `R2-01-decision.png`, `R2-02-consent.png`, `R2-03-review.png`, `R2-04-quests.png`, `R2-05-approve.png`, `R2-06-export.png`. Data: `R2-before.json`, `R2-final.json`, `R2-trace.json`, `R2-db.json`, `R2-brief.md` and the passively captured export response.

## R3 — two-field correction

Workspace **repeatability-r3-frostpeak-dev-20261030**; source **e6b981cc-c55d-45cb-addb-cbb40ff6e07a**; decision **a960644b-2f3b-46d9-a20b-3044d82fbbd3**; run **3343b7c0-d250-4f56-a9f9-58c5726fe88a**. Draft v1 **80adf02a-3a8b-4bc6-8e2c-1431a55b9898**; revision v2 **e811e4b8-0080-4368-aae3-63b71b25ff38**; final v3 **6524a51b-237e-4f50-9b03-eeaaa7736b19**.

Initial critique: **ready_for_review**, findings **[]**, same coverage map as R1/R2, **75%** scorecard, **18** proposals. The initial critic request received Google **503**, then its normal bounded production retry received **200**. It was not mock fallback. The accepted critique said no defects or conflicts against source/design direction.

### Advisory list as displayed

Both entries: **medium**, check `objective_text_copied_as_dialogue`; message **“Dialogue exactly repeats an objective after text normalization. Review whether this is useful spoken dialogue.”**

| Short / persisted ID | Paths | Exact compared values | Assessment |
| --- | --- | --- | --- |
| `#bafbffc0` / `bafbffc0eca64bce96c66d5e3eaacb9e40f71a392cdd92dd2a5525c830beecf9` | `/quest_hooks/content/quests/0/dialogue_hooks/0`, `/quest_hooks/content/quests/0/objective` | Both `Reclaim the Ash Pass border post. Players must clear guards and raise the Northern flag.` | True positive |
| `#68b34547` / `68b345478b3b18ea2393f313a00803b3617eac5b16a22ff385d244d4c2b61060` | `/quest_hooks/content/quests/1/dialogue_hooks/0`, `/quest_hooks/content/quests/1/objective` | Both `Mine 5 chunks of raw sky-iron ore from the cliffside veins.` | True positive |

No false positive or missed qualifying **exact-match** case was found. No numeric Quest situation mismatch or misplaced memory-rule warning applied. Wrong labels elsewhere and paraphrases are outside these exact checks' scope, not evidence of a fuzzy detector that failed.

### Request, outcome and complete diff

Selected **exactly two** hook fields in Request correction. The dialog showed both current strings and the conditional dependency: only that quest's assumptions may gain the exact server-derived creative-proposal annotation, retaining all existing assumptions. It explained this is not rejection; failure preserves the original, while success consumes one revision and re-critiques. No situation/manual-test field was selected.

Entered this exact reason and submitted **once**:

> Both quest dialogue hooks are copied objectives, not spoken invitations. At /quest_hooks/content/quests/0/dialogue_hooks/0 replace the task-sheet text with one short natural spoken request to reclaim the Ash Pass border post by clearing guards and raising the Northern flag; require both actions without adding an order. At /quest_hooks/content/quests/1/dialogue_hooks/0 replace the copied objective with one short natural spoken invitation to mine five chunks of raw sky-iron from the cliffside veins. Do not claim either quest is complete, add a return or delivery requirement, or change rewards, objectives, IDs, existing NPC speech or any other field.

Log: **`Gemini schema node=revise mode=keep_literals bytes=608`**. Google **200**, first response locally accepted; no validation errors, generic repair, truncation resend, corrective re-ask or revise fallback. Review API **200 / awaiting_review**, **11,494.27 ms** including follow-up critique.

Full v1 → v2 recursive content comparison found **exactly four changed paths**:

| Path | Before, verbatim | After, verbatim |
| --- | --- | --- |
| `/quest_hooks/content/quests/0/dialogue_hooks/0` | `Reclaim the Ash Pass border post. Players must clear guards and raise the Northern flag.` | `Please reclaim the Ash Pass border post by clearing the guards and raising the Northern flag.` |
| `/quest_hooks/content/quests/1/dialogue_hooks/0` | `Mine 5 chunks of raw sky-iron ore from the cliffside veins.` | `Could you mine five chunks of raw sky-iron from the cliffside veins for us?` |
| `/quest_hooks/content/quests/0/assumptions/5` | Absent | `Generated quest failure states, dialogue hooks, event actions are creative proposals and require design approval before runtime use.` |
| `/quest_hooks/content/quests/1/assumptions/5` | Absent | `Generated quest failure states, dialogue hooks, event actions are creative proposals and require design approval before runtime use.` |

Only the selected fields and enumerated server annotations changed. All previous assumptions, objectives, rewards, IDs, citations, NPC speech/situations/eligibility/manual tests and unrelated sections remained identical. No manual-test dependency was expected.

The first replacement removes the third-person “Players must” and is speakable, but **mostly adds “Please” to the objective**: modest improvement, still close paraphrase rather than strong authored dialogue. The second is a clearer spoken invitation. Both preserve the source actions/quantity, introduce no ordering/delivery/completion claim, and are generic rather than character-specific. They are better in form, not proof of narrative quality.

READ ONLY evidence **before approval** (`R3-before-approval-db.json`): **zero review events**, no reject event, **zero queue jobs** (inline). Correction-request execution **completed**, outcome **saved**; recorded `local_developer`, null user ID, exact reason/paths/current strings, original artifact ID/version/hash, request fingerprint, dependent-effects preview, exact before/after assumptions, result artifact ID. Revisions **1/2**, consecutive failures **0/3**, run **awaiting_review**, **6/12** inference attempts. No stale artifact or unrecorded action was used.

Follow-up critique: **ready_for_review**, findings **[]**, memory `not_specified`, all other sections `covered`. New advisory evaluation was bound to **v2**, advisories **[]**; both exact-copy entries disappeared. Scorecard stayed **75%** until confirmations; proposals increased **18 -> 20** due to the two allowed annotations. It missed the remaining semantic problems below.

Confirmed **20** proposals and approved once: **200 / completed**, final v3 immutable, approved blueprint present. Exactly one final review event, decision **approve**, bound to v2; no reject events. Export **200**, downloaded/read `R3-brief.md`, **28,736 bytes**, byte-identical to its passively captured response. Corrected hooks and version **3** present; advisory list/IDs not exported. Verifier passed the documented-metadata policy, not strict raw equality.

### Remaining draft/export defects and assumptions

- **Unmarked input assumption:** `/unity_runtime_preview/content/primary_input` is **`Keyboard and Mouse`**. Neither Frostpeak nor the frozen Windows-PC decision specifies that input. Runtime warnings are empty; citations do not support this extra requirement. Both critiques missed it and the three advisory checks do not cover it. It remains in the approved exported brief.
- **Numbering inconsistency outside the situation allowlist:** Eldrin's assumption says **“associated with Quest 0”**, but his progress/completion use `quest_1` and the Ash Pass; Kaelen's says **“associated with Quest 1”**, but his stages use `quest_2` and mining. Unlike R2's explicitly named `quest_index`, these are misleading displayed Quest labels. Situations themselves correctly name their quests, so the situation-only numeric advisory abstains by design. Both critics missed them. They remain exported.
- **Unsupported extra instruction:** `/npc_archetypes/content/npcs/1/dialogue_triggers/1/text`: **“The cliffside veins contain the sky-iron we require. Return when you have gathered the required ore.”** The GDD specifies mining, not returning/delivery; the structured quest completes on mining alone. Even as proposed speech this introduces an unneeded next step that conflicts with that implementation expectation. The narrow hook correction could not edit NPC speech; both critics missed it and it remains exported.
- Quest failure/death/fall and checkpoint-reload semantics are invented but explicitly labelled **proposals**, with human confirmation. They are not proven GDD facts or executed fail-safe tests. Repetition remains `no reset`; manual checks do not prove runtime behavior.
- **No fabricated new numeric reward, guard count, XP=0, difficulty rating or asserted guard-before-flag source order was found.** Both actions remain independent/all-required; source 5-chunk total and rewards are preserved. Summary is the exact Section 1 premise; memory is honestly unassessed.
- The corrected first hook still restates its objective closely. This is an intentional exact-advisory coverage limitation, not an exact-match false negative. A clean post-correction advisory list is not a “good dialogue” score.

Screenshots: `R3-01-decision.png`, `R3-02-consent.png`, `R3-03-review.png`, `R3-04-correction-dialog.png`, `R3-05-corrected.png`, `R3-06-approve.png`, `R3-07-export.png`. Data: `R3-before.json`, `R3-corrected.json`, `R3-diff.json`, `R3-before-approval-db.json`, `R3-final.json`, `R3-trace.json`, `R3-db.json`, `R3-brief.md`, passive export response.

## Per-node provider, latency, tokens and attempts

All plan/generate/critique/revise rows below were actually served by **Gemini / gemini-3.5-flash-lite**, **degraded=false**, independently checked against transport logs and persisted executions. Retrieval was **local_retrieval / chroma-local-lexical-v1**, not an LLM/mock fallback. Human review/finalize were local, zero model requests. Summary alone used the labelled exact-source extractor, not mock generation.

| Run / node | Latency ms | Input / output tokens | Real HTTP attempts | Retry / schema evidence |
| --- | ---: | ---: | ---: | --- |
| R1 plan | 2,155 | 373 / 173 | 1 | No retry; full 2,364 bytes |
| R1 retrieve | 740 | 0 / 0 | 0 | Four frozen excerpts; scoped lexical recovery after Chroma errors |
| R1 generate | 5,859 | 3,400 / 1,694 | 1 | First response valid; full 20,540 |
| R1 critique | 2,187 | 5,557 / 173 | 1 | First response valid; full 11,292 |
| R1 human review / finalize | 43 / 54 | 0 / 0 | 0 | Approval only |
| R2 plan | 3,001 | 372 / 173 | 1 | No retry; full 2,364 |
| R2 retrieve | 133 | 0 / 0 | 0 | Four frozen excerpts |
| R2 generate | 7,728 | 3,334 / 2,027 | 1 | First response valid; full 20,490 |
| R2 critique | 4,614 | 5,868 / 164 | 1 | First response valid; full 13,907 |
| R2 human review / finalize | 35 / 51 | 0 / 0 | 0 | Approval only |
| R3 plan | 4,248 | 369 / 171 | 1 | No retry; full 2,364 |
| R3 retrieve | 123 | 0 / 0 | 0 | Four frozen excerpts |
| R3 generate | 11,914 | 3,379 / 2,373 | 1 | First response valid; full 20,540 |
| R3 initial critique | 5,543 | 6,679 / 157 returned for successful response | **2** | Google 503 -> normal retry -> 200; full 15,914 twice |
| R3 correction / revise | 5,035 | 2,448 / 121 | 1 | First response valid; **keep_literals 608** |
| R3 follow-up critique | 5,998 | 6,725 / 160 | 1 | First response valid; full 16,006 |
| R3 correction review / approval / finalize | 13 / 36 / 60 | 0 / 0 | 0 | No rejection |

Node timing and start/review API duration are distinct; neither includes human reading time. Initial plan/retrieve/generate/critique node sums: **10,941 ms**, **15,476 ms**, **21,828 ms**, respectively. No averaging or general latency claim.

R1 tokens **9,330 input / 2,040 output**; R2 **9,574 / 2,364**; R3 returned usage **19,600 / 2,982**. The failed 503 returned no token usage, so these are reported totals, not a claim that the failed attempt consumed zero tokens. Cost unavailable. No truncation, repair, source-anchoring corrective re-ask, hosted-to-mock substitution or local response recovery occurred in these runs.

R3 transient-error evidence: **06:30:42.705770Z** Google POST **503**, next schema/send log **06:30:43.668526Z**, second POST response **06:30:47.100260Z 200**. Persisted `request_attempts=2`, `retry_count=1`, `independent_review_retries=0`. Exact jitter/sleep duration is **not logged**; the observed response-to-next-send gap is approximately **0.963 s**, not an isolated sleep measurement. Existing transport code sleeps `0.5 * 2**retries + jitter(0, 0.5)` before this first retry. No manual retry, quota/auth error, timeout, second retry or exhausted cap.

### Quota reconciliation

| Actual CLI reading, same Pacific day | Flash-Lite used / remaining | Flash used / remaining |
| --- | --- | --- |
| Before startup | **11 / 489** | **0 / 20** |
| After startup GET | **12 / 488** | **0 / 20** |
| After R1 | **15 / 485** | **0 / 20** |
| After R2 generation / approval | **18 / 482** | **0 / 20** |
| After R3 initial review | **22 / 478** | **0 / 20** |
| After R3 correction / follow-up critique | **24 / 476** | **0 / 20** |
| Final, after approval/export | **24 / 476** | **0 / 20** |

**13 new Google requests = 1 startup GET + 12 inference POST attempts**. Per-run counters **3/12, 3/12, 6/12** reconcile with CLI and ordered transport calls. By node: R1/R2 each plan 1, generate 1, critique 1; R3 plan 1, generate 1, initial critique 2, revise 1, follow-up critique 1. Retrieval/approval/export/verifier consumed zero Google requests. No new NVIDIA request or other document used.

## Integrity and audit

All three `verify_final_integrity.py <run-id>` executions used the live READ ONLY path and exited **0**. In each: **EQUAL_EXCEPT_DOCUMENTED_METADATA**, only `/npc_memory_design/memory_unspecified=true`, **offending_paths=[]**. No runtime-deferred addition because frozen deferral was false. Raw hashes **differ**, as expected under the documented exception; this is not strict byte-equality acceptance.

| Run | Reviewed content SHA-256 | Immutable final content SHA-256 |
| --- | --- | --- |
| R1 | `e032f9ca5d82155c5f7234122cb6700dca58cc6852f9d43b1f0b7854192f6e50` | `2299699388a3a4a1462cc441690facfc8bf1aca20fe36fb190b06dc4997b96e1` |
| R2 | `e229e685d53d400b573712dbc2bbe589ed46b5a5660537b686f8481e8593d8bb` | `555220ca943395f5607a852d8c3bbb4e327cc07e7f3a428d9af2d04c1973de98` |
| R3 | `b10f7b4fd6ed889754523792bc4509adb70f3c1ef5de98ce4525832b7109b474` | `6a82f58f42c6d1c80eb2de12b7a94d020b761e7cca828a25c46b1dea7a1bec24` |

Canonical digest: sorted-key compact JSON, `ensure_ascii=False`, UTF-8 SHA-256. All saved final artifacts were immutable and runs completed, with approved GameBlueprint records. R1/R2 each have only the v1 approval event; R3 has only the v2 approval event. Frozen settings and resolved decision retained; advisory evaluations bind to the corresponding draft/revision, not final metadata. No historical run/artifact was repaired.

## UX / operational findings

| ID | Rating | Observed problem and limit of diagnosis | Evidence |
| --- | --- | --- | --- |
| REP01 | blocker for R1's saved-download step | Export response 200 but browser download canceled. R2/R3 downloads worked. No retry; cannot distinguish transient Chromium/driver failure from application blob/download timing offline. Do not claim a confirmed server/export defect. | `R1-09-export-canceled.png`, passive export 200, driver `download.saveAs: canceled` |
| REP02 | annoying | Long narrow review column, 13/14/18–20 individual proposals and repeated score prose require extensive scrolling while most of the draft area is blank. | `R1-06-design-review.png`, `R2-03-review.png`, `R3-03-review.png` |
| REP03 | annoying | Exact-field chooser repeats long paths/dependency prose. Selected fields scroll away while writing the reason; no advisory-prefill entry point or persistent concise selection summary was observed. | `R3-04-correction-dialog.png`, retained dialog DOM |
| REP04 | annoying | Critic says complete/no defects and completeness reads 100% although quest dialogue is empty in R1/R2, while R3 contains unmarked input/numbering defects. Structural-check disclaimers are present but do not make the broad clean verdict useful semantic evidence. | All review screenshots, saved critics/drafts |
| REP05 | annoying | Decisions says the governed review is “now preparing” even after the inline API has reached awaiting_review. The user must open View review trace; the status copy lags the actual result. | `R1-05-review.png`, all start responses 201 / awaiting_review |
| REP06 | annoying | Home's NVIDIA/Local Demo framing and health `ai_mode=local_demo` are misleading for an effective Gemini DEV process. Consent itself correctly names Google and its free-tier terms. | Initial browser DOM; `/health` effective `llm_provider=gemini` |
| REP07 | annoying / operational | R1 Chroma HNSW queries returned repeated internal 500s; existing code recovered with scoped PostgreSQL lexical fallback. No run failed, no mock provider served output, and no repair was attempted. This is distinct from the known telemetry signature noise. | Timestamped backend logs, four retained frozen excerpts, completed retrieval trace |

No browser console errors or page exceptions were recorded. No missing-human-evaluation 404 appeared in the UI's passive network evidence. Independent evidence GETs initially omitted the required `X-Game-Project-ID` header and returned workspace-scoped 404; correcting the read-only diagnostic header succeeded. Those diagnostic mistakes did not mutate a run or constitute a retried workflow step. Initial driver mistakes (duplicate Load demo locator, Review GDD sought on Sources, and treating a saved response URL string as a function) likewise caused no repeated mutation. No full responsive/accessibility/performance audit was performed.

## What this batch actually establishes

The workflow can take three fresh real Flash-Lite drafts through human approval and immutable finalization without manual server-side content construction. One transient Google 503 recovered under normal counted retries. R3's two-field correction used a tiny schema, preserved its full scope and audit trail, recomputed advisories and exported corrected content. Two saved browser downloads and all three integrity checks succeeded.

It **does not** establish correction repeatability on three independent drafts, failed-correction approval recovery, reliable critic semantics, absence of unsupported assumptions, implementation readiness, or a complete MVP. In two runs there was no eligible correction field; in the third the first rewritten line is only marginally more conversational. R3 approved/exported unsupported input and misleading labels despite two clean critiques. R1 did not complete a saved download. Those limitations are not softened into a blanket PASS.

## Evidence and shutdown

All screenshot filenames above resolve under `<QA_DIR>/repeatability-20261030-01/`. Retained **22 screenshots**, `browser-evidence.json` (passive requests/responses, DOM snapshots, console/errors), per-run before/final/trace JSON, READ ONLY DB snapshots, R3's pre-approval audit/diff, two downloaded briefs and their passive response copies, and timestamped backend stdout/stderr. CLI/verifier results were recorded directly in tool output and reproduced above; no separate CLI JSON files are claimed.

After the final CLI counts, closed the fresh browser/context and exited its Node driver. Frontend stopped with **Ctrl+C** (expected interrupted-process exit); backend stopped with **`docker compose stop backend`**, **exit 0**, restart count **0**, restart policy **no**. No listeners remained on **3000/8000**. Existing PostgreSQL/Chroma and all new QA workspaces/evidence were retained. No deletes, test-suite execution against application data, source/`.env` edits, runtime materialization, Unity operation or push.

Only this acceptance document is included in the local evidence-branch commit. `docs/audit/` remains untracked and untouched.
