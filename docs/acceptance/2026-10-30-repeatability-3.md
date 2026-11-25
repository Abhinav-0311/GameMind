# DEV workflow repeatability — R7, R8 and R9 after server-owned quest fields

Executed **2026-11-25, Asia/Calcutta**, approximately 11:36–11:44 for live workflow activity; quota day **2026-11-24, America/Los_Angeles**. The requested filename continues the previous reports’ naming sequence. `<QA_DIR>` is the author's local, unpublished QA evidence folder. This batch is under **`<QA_DIR>/repeatability-3-20261125-01/`**.

## Verdict and results

**PASS for the three observed mechanical workflows and the server-owned quest-field check. Content-quality acceptance is not established.** The new generation schema was accepted by Google, and the first generation response passed local validation, in each run. Neither quest had runtime bindings or dependencies in any draft, correction or final. All three runs saved a scoped correction, approved, exported and passed the integrity verifier. The narrower schema did not stop unsupported assumptions in other fields or make the critique dependable.

| Run | Start / correction API latency | Generation: HTTP, local result, wire size | Critique, initial → follow-up | Approval / export / verifier | Real inference attempts |
| --- | ---: | --- | --- | --- | ---: |
| R7 | 11,678.76 / 5,291.48 ms | 200; first response valid; full, **18,929 bytes** | `needs_revision`, 1 medium → `ready_for_review`, 0 | 14 confirmations; 200 / 200; 19,575 bytes; integrity passed | **7** |
| R8 | 10,369.17 / 3,954.08 ms | 200; first response valid; full, **18,974 bytes** | `ready_for_review`, 0 → `ready_for_review`, 0 | 18 confirmations; 200 / 200; 26,703 bytes; integrity passed | **5** |
| R9 | 17,632.77 / 10,393.29 ms | 200; first response valid; full, **18,979 bytes** | `ready_for_review`, 0 → `ready_for_review`, 0 | 20 confirmations; 200 / 200; 26,937 bytes; integrity passed | **6** |

Each completed plan, retrieval, generation, initial critique, correction, follow-up critique, human review and finalize. Browser-observed start durations were 11,761 / 10,434 / 17,693 ms; correction durations were 5,378 / 4,052 / 10,488 ms. These are not per-node durations or averages.

## Preconditions and common protocol

- Live execution on **main**, HEAD **`cda688a8fcb40ad6d0bee58ede6e00a9062f6361`**; `16a1678` is an ancestor. Initial status was exactly `?? docs/audit/`. Scope: **P1.3–P1.5, P2.3/P2.6, P3.5, P4.1–P4.2, P5.3**. This report does not change MVP status or claim acceptance of those phases.
- Used cached **`gamemind-revise-tests:local`** (`sha256:77a2481d5d69bc58d1f4f2fa93a6ff032dbf6a9c653c93ea7545d095d9ba592a`), google-genai **2.33.0**, current source bound to `/app`, restart policy **no**. Effective settings: `LLM_PROFILE=dev`, `GEMINI_DEV_MODEL=gemini-3.5-flash-lite`, `GEMINI_TIMEOUT_SECONDS=180`, `DESIGN_AGENT_FALLBACK_TO_MOCK=true`, revise excluded from fallback, schema reduction only on revise, 6,000-byte keep-literals cap, 12 requests/run, inline execution, 300-second lease. Production retries unchanged. No install, build, saved environment edit or model switch.
- `gemini_usage.py` ran before startup: **0 used / 500 remaining**, above the 40 threshold. `alembic current` and `heads` both **`f4a6b8c0d123`**. Normal startup ran `alembic upgrade head` with **no pending migration**. One model GET returned 200 and counted. Two HTTP readiness probes made while startup was still in progress got connection/read errors; after startup completed, health and readiness were healthy (DB/Chroma healthy, `ai_mode=gemini`, `llm_provider=gemini`), no restart.
- Real installed **Playwright Chromium 156.0.8078.4**, headless, 1440×1000, live frontend/backend on localhost ports 3000/8000. No intercepted APIs, fixture replies, response substitution or mutations outside browser controls. READ ONLY SQL snapshots and verifier were separate.
- Each attempt used a new workspace: **New project → Sources → Load Frostpeak demo → Decisions → Review GDD → Continue with local review → Save and mark Platform and controls resolved → Review GDD → hosted consent → Start governed review → View review trace**. Runtime preview enabled, unspecified memory allowed, default `fresh_dialogue=false`. Persisted revision limit **2**. Exactly three start POSTs; one correction POST and one approval POST per run. No sign-in, explicit reject, finding adjudication, manual retry, retry-critique, runtime release or Unity action. Earlier workspaces/runs were not modified by the browser driver.

Resolved decision, same in each run:

> unity_runtime_preview.content.target_platform must be "Windows PC"; this is human design direction, not a GDD fact

Consent shown:

> The selected source text may be sent to Google's Gemini API to create a cited draft and independent critique. On the free tier, Google may use submitted content to improve its products. Use only demo or non-confidential material. Mock mode runs offline and sends nothing to a hosted provider. No provider request is made until you confirm.

All starts returned **201 / awaiting_review**, with locally extracted exact Section 1 summary, two independently tracked Ash Pass actions, the five-chunk mining target, both GDD rewards and the frozen platform decision. All initial and revised scorecards were **75%** (grounding/completeness/consistency **100%**, integration readiness **0%**, pending proposals). Coverage was `covered` except `npc_memory_design=not_specified`. The initial Approve button was disabled on all three; R7 also had a critic block. After correction and checking the current proposals, approval enabled. No degraded acknowledgement was required. Hosted nodes were all Gemini, not mock.

## R7

Workspace **repeatability-r7-frostpeak-dev-20261125**; source `f0d48183-825e-40d8-9fc6-6d2ab981ea7a`; decision `1ca20ff5-c38a-4ff2-b2a7-af5c8aab643d`; run `82004107-4e2d-4f08-8c46-21546a18d5d2`. Draft `00b5a441-c67e-4640-a7fa-9b6f9a4b98a6`; revised `e48fe41d-3dd7-4b50-aba6-174e2db47c64`; immutable final v3 `29bfc119-7d4a-4daf-abef-5c57251672ac`.

- **Initial finding:** medium, `quest_hooks=covered`, path `/quest_hooks/content/quests/1/state_contract/event_actions/q2_objective_1_completed`, evidence chunk `23252428-5b50-4ab5-8f87-dd4c6a277a55` (wire index **2**, reconstructed with the actual compaction builder from the frozen snapshot). It argued that “Extract exactly 5 chunks of raw sky-iron ore from the cliffside veins.” did not define a precise increment. The GDD requires a total, not an increment rule; an explicit total-reached event would be clearer, but an incremental trigger is not an established source requirement. The selected correction did **not** touch the event action. Follow-up returned no finding there, so the verdict changed without the cited field changing.
- **Advisories displayed:** none on v1 or v2 (zero positives, zero false positives observed). Both hooks exist but lack the concrete actions/amount or faction specificity; exact matching does not catch underspecified dialogue. NPCs have greetings only. That is an implementation gap for a fuller gameplay demo, not proof the run violated a requested stage count. Section 2 faction consequence appears in systems; Windows PC is the only runtime-preview field. No unsupported input, delivery or wrong Quest number found.

Submitted one correction selecting `/quest_hooks/content/quests/0/dialogue_hooks/0` and `/quest_hooks/content/quests/1/dialogue_hooks/0`:

> The two quest hooks are too vague to tell the player what to do. In the first hook, write a short in-world request that names the Ash Pass border post and requires both clearing the guards and raising the Northern flag, without imposing order. In the second hook, write a short spoken request to mine exactly five chunks of raw sky-iron ore from the cliffside veins. Do not add return, delivery, equipment, reward or completion claims. Preserve objectives, rewards, IDs, NPC speech and all other fields.

| Changed path | Before, verbatim | After, verbatim |
| --- | --- | --- |
| `/quest_hooks/content/quests/0/dialogue_hooks/0` | Secure the border post for our forces. | Clear the guards at the Ash Pass border post and raise the Northern flag. |
| `/quest_hooks/content/quests/1/dialogue_hooks/0` | Gather the raw materials from the cliffside. | Mine exactly five chunks of raw sky-iron ore from the cliffside veins. |

Correction: **Google 200**, **keep_literals / 608 bytes**, first response valid; API **200**, saved v2. Follow-up critique needed a single automatic source-omission corrective re-ask, then accepted `ready_for_review`, zero findings. The edits restore the missing specifics but read as task commands, not distinctive character writing. Confirmed 14 proposals, approved once, downloaded **R7-brief.md** and reloaded. Brief: faithful objectives and rewards, no invented runtime block or dependency; the exact-scope edit still does not supply actual integration bindings or richer speech.

Screenshots: **R7-01-source.png** through **R7-10-reloaded.png** in the QA folder (01 source, 02 decision, 03 consent, 04 review, 05 correction dialog, 06 corrected, 07 proposals, 08 approved, 09 export, 10 reloaded).

## R8

Workspace **repeatability-r8-frostpeak-dev-20261125**; source `e22bfdda-82ae-48fc-934a-0e071130583c`; decision `2ba7d05a-1100-411a-bfe4-71afa74bbc3f`; run `1df74eb7-9449-47ef-93a5-a0fe74c6cd70`. Draft `994a8754-c607-49f5-8823-4a26bde741ca`; revised `d7aa50e1-4798-4936-98bd-d51983cfe532`; immutable final v3 `8fb3e41c-e487-4d2d-87d2-5ad9956912ee`.

- **Both critiques:** `ready_for_review`, no findings. **No advisories displayed**, v1 or v2. Practical miss: `/unity_runtime_preview/content/input_assumptions` says **“Standard keyboard and mouse setup for tactical role-playing controls.”** This is absent from the GDD and the Windows PC decision. The exact runtime advisory watches particular fields, not `input_assumptions`; this is a coverage gap, not a triggering field whose advisory failed to render.
- **Additional missed defect:** both initial quest hooks repeat the nearby NPC progress speech verbatim once the speaker prefix is removed. The exact-copy advisory compares a quest hook to its objectives, not to NPC speech. Kaelen's **“without delay”** is unsupported urgency; no timer was defined. The hook correction removed it from the quest hook, not from the original NPC line. No return/delivery instruction or wrong Quest number found; faction-choice consequence is retained in systems. Kaelen's alignment with the player's goals remains a proposed speaker association, not a GDD-approved quest-giver rule.

One correction, same two paths:

> Both hooks repeat nearby NPC lines without clearly telling the player what to do; the mining line adds unsourced urgency and omits the quantity. Give Eldrin a short spoken Ash Pass request covering both clearing guards and raising the Northern flag with no required order. Give Kaelen a short spoken request to mine exactly five chunks of raw sky-iron ore from the cliffside veins. Add no deadline, return, delivery or hand-in step. Preserve the objectives, rewards, NPC speech, IDs and all other fields.

| Changed path | Before, verbatim | After, verbatim |
| --- | --- | --- |
| `/quest_hooks/content/quests/0/dialogue_hooks/0` | Eldrin: Keep your resolve steady against the Cinder Vanguard in the Ash Pass. | Eldrin: Clear the guards in the Ash Pass and raise the Northern flag. |
| `/quest_hooks/content/quests/1/dialogue_hooks/0` | Kaelen: Make sure you extract the raw sky-iron ore from the cliffside veins without delay. | Kaelen: Mine exactly five chunks of raw sky-iron ore from the cliffside veins. |

Correction: **Google 200**, **keep_literals / 608 bytes**, first response valid; API **200**, saved v2. Clearer quest instructions and no new quest mechanic; voice is still largely a speaker label followed by task text. Confirmed 18 proposals, approved once, downloaded **R8-brief.md** and reloaded. The approved brief still contains the unsupported keyboard/mouse assumption and the unchanged NPC urgency. It is not an implementation-ready controls spec.

Screenshots: **R8-01-source.png** through **R8-10-reloaded.png**, with the same suffix sequence as R7.

## R9

Workspace **repeatability-r9-frostpeak-dev-20261125**; source `13567921-1d5b-4845-8946-b19e24441be3`; decision `900803e6-13dc-4a87-9a93-832c9e628462`; run `c7760c87-d9e1-48c0-8b64-e897c86f1442`. Draft `6c5584f4-59b8-4b6b-acf1-fe4f550709a6`; revised `755c996a-b858-4bb2-a657-7bf15c3d4e7e`; immutable final v3 `de9eb02c-bbcc-4b8c-adb3-259fce15e1e4`.

- **Both critiques:** `ready_for_review`, zero findings. **No advisories displayed** in either version. Practical misses: “Secure the perimeter” and “plant our banner” are an ambiguous substitute for clearing guards and raising the Northern flag. “Extract 5 chunks…” nearly copies the objective but differs by verb; correctly outside the exact-copy rule. The speaker-to-quest notes name the correct Quest Hook titles; no wrong displayed numbers, unsupported input method, or return/delivery/hand-in step found. Faction consequences appear in systems. Kaelen's quest-giver role is a proposal; the source does not specify that relationship.

One correction, same two paths:

> The Ash Pass hook says secure the perimeter and plant our banner, which does not clearly identify the required guard and Northern flag actions. Write one natural spoken request that names both at the Ash Pass border post, with no mandatory order. The mining hook reads like a copied task label; rewrite it as a short in-world spoken request to mine exactly five chunks of raw sky-iron ore from the cliffside veins. Do not add timers, delivery, return, hand-in or reward claims. Preserve objectives, rewards, IDs, NPC speech and other fields.

| Changed path | Before, verbatim | After, verbatim |
| --- | --- | --- |
| `/quest_hooks/content/quests/0/dialogue_hooks/0` | Secure the perimeter at Ash Pass and plant our banner. | At the Ash Pass border post, please clear the guards and raise the Northern flag. |
| `/quest_hooks/content/quests/1/dialogue_hooks/0` | Extract 5 chunks of raw sky-iron ore from the cliffside veins. | Mine exactly five chunks of raw sky-iron ore from the cliffside veins. |

Correction: **Google 200**, **keep_literals / 608 bytes**, first response valid; API **200**, saved v2. The first line is clearer and more conversational; the second is still near-objective wording after correction. Follow-up critique recovered from Google 503 via one normal counted retry. Confirmed 20 proposals, approved once, downloaded **R9-brief.md** and reloaded. The brief preserves supported details but contains repeated unexecuted state checks and proposed speaker links, not evidence of playable behavior.

Screenshots: **R9-01-source.png** through **R9-10-reloaded.png**. The common initial home screenshot is **00-home.png**.

## Quest field and quality comparisons

Initial generated artifacts are the denominator; the revision and final were also checked separately for the owned fields. Prior values came from retained B4b content, the saved R1–R6 initial JSON and the two earlier acceptance reports.

| Measure (runs, not individual fields) | B4b | R1–R3 | R4–R6 | R7–R9 |
| --- | ---: | ---: | ---: | ---: |
| Unsupported nested quest runtime values | 1/1 | 0/3 | 1/3 | **0/3** |
| Unsupported quest dependency | 1/1 | 0/3 | 2/3 | **0/3** |
| Generation passes on first response | 1/1 | 3/3 | 3/3 | **3/3** |

B4b supplied four guards and Normal/Hard ratings; R5 supplied one guard and Normal for both. Both included unsupported zero XP on the second quest. B4b, R5 and R6 had an unsupported Quest Hook 1 dependency on quest 2. B4b is a single historical comparison, not part of the three-run denominator.

| Persisted values in draft / revision / immutable final | Quest 1 | Quest 2 | Draft and brief search |
| --- | --- | --- | --- |
| R7 | `null` / `[]` | `null` / `[]` | No counted guards, difficulty labels, `xp_reward`, or Quest Hook 1 dependency. Title/source title and empty draft dependency fields are benign hits. |
| R8 | `null` / `[]` | `null` / `[]` | Same; Quest Hook 1 also appears in a labelled speaker-association proposal, not as a prerequisite. |
| R9 | `null` / `[]` | `null` / `[]` | Same; Quest Hook 1 also appears in speaker-association/integration notes, not as a prerequisite. |

Each pair represents `runtime` / `dependencies`, not before/after. The briefs still correctly show quest 1's **100 gold and 250 XP** and quest 2's **150 gold and sky-iron gear** as sourced reward text. The explicit five-chunk mining total is also sourced; neither is an invented runtime value. No change was made to earlier artifacts.

| Six repeatability items, counted on initial drafts | R1–R3 | R4–R6 | R7–R9 |
| --- | --- | --- | --- |
| New advisory types displayed: empty quest dialogue / assumption label / runtime value | 0/3 each; not implemented then | 0/3 each | **0/3 each** |
| Both quests have populated hooks | 1/3 | 3/3 | **3/3** |
| Unsupported runtime input method anywhere in runtime preview | 1/3 | 1/3 | **1/3** (R8) |
| Unsupported return/delivery/hand-in content in NPC speech or hooks | 1/3 | 1/3 | **0/3** |
| Section 2 faction consequence in narrative or systems | 2/3 | 3/3 | **3/3**, all in systems |
| Wrong displayed Quest number in NPC assumptions | 1/3 | 1/3 | **0/3** |

Both hook lists had a spoken-form line or imperative in all three new drafts, not always natural or sufficiently specific speech. R7's commands, R8's duplicated speech, and R9's near-objective copy are not examples of consistently good writing. Separately, R7–R9 displayed **zero advisories of any type** on initial or corrected drafts. There are no advisory true/false positives to enumerate. No exact implemented trigger was identified that should have fired; the practical misses above include synonymous/near-copy text, cross-surface duplication, alternate runtime field names, and unsourced urgency. Zero warnings is not a quality signal.

## Nodes, retries and ledger reconciliation

All hosted rows: **Gemini / gemini-3.5-flash-lite**, degraded **false**. Retrieval: local Chroma lexical, four frozen excerpts per run, zero Google calls; all three query responses were 200. Review/finalize also used zero Google calls. Reported tokens are available response totals, not evidence that the failed 503s used no tokens.

| Run / node | Latency ms | Input / output tokens | Real attempts; status or special handling | Schema mode / bytes |
| --- | ---: | ---: | --- | --- |
| R7 plan | 3,368 | 372 / 165 | 2; 503 → 200 | full / 2,364 |
| R7 retrieve | 157 | 0 / 0 | 0 | local |
| R7 generate | 5,533 | 3,368 / 1,761 | 1; 200, first valid | full / 18,929 |
| R7 initial critique | 2,146 | 5,635 / 321 | 1; 200 | full / 11,778 |
| R7 correction | 1,520 | 2,362 / 117 | 1; 200, first valid | keep_literals / 608 |
| R7 follow-up critique | 3,336 | 11,383 / 354 | 2; 200 + 200, source-anchoring re-ask accepted | full / 11,778 |
| R8 plan | 1,723 | 370 / 170 | 1; 200 | full / 2,364 |
| R8 retrieve | 138 | 0 / 0 | 0 | local |
| R8 generate | 6,418 | 3,425 / 2,178 | 1; 200, first valid | full / 18,974 |
| R8 initial critique | 1,747 | 6,253 / 172 | 1; 200 | full / 15,807 |
| R8 correction | 1,460 | 2,454 / 123 | 1; 200, first valid | keep_literals / 608 |
| R8 follow-up critique | 2,167 | 6,250 / 169 | 1; 200 | full / 15,807 |
| R9 plan | 3,457 | 374 / 166 | 1; 200 | full / 2,364 |
| R9 retrieve | 141 | 0 / 0 | 0 | local |
| R9 generate | 8,937 | 3,449 / 2,222 | 1; 200, first valid | full / 18,979 |
| R9 initial critique | 4,769 | 6,312 / 196 | 1; 200 | full / 16,031 |
| R9 correction | 3,785 | 2,461 / 119 | 1; 200, first valid | keep_literals / 608 |
| R9 follow-up critique | 6,240 | 6,318 / 179 | 2; 503 → 200 | full / 16,031 |

R7 plan and R9 follow-up critique each retried on attempt 2 after 503. Timestamp gaps from 503 to next schema/send log were **559 ms** and **906 ms**, respectively; these include scheduling overhead, not a separately measured sleep. R7 follow-up's first HTTP-200 critique failed the local source-anchored omissions rule (one root value error); the one corrective re-ask passed and is separately recorded as accepted. No other corrective re-ask, generic repair, truncation resend or syntax recovery. Reported token totals: R7 **23,120 / 2,718**, R8 **18,752 / 2,812**, R9 **18,914 / 2,882**. Correction-resume / approval / finalize latencies: R7 **13 / 36 / 58 ms**, R8 **11 / 39 / 52 ms**, R9 **10 / 39 / 53 ms**.

| Actual CLI checkpoint | Flash-Lite used | Remaining |
| --- | ---: | ---: |
| Before startup | 0 | 500 |
| After startup GET | 1 | 499 |
| R7 initial review | 5 | 495 |
| R7 after correction | 8 | 492 |
| R8 initial review | 11 | 489 |
| R8 after correction | 13 | 487 |
| R9 initial review | 16 | 484 |
| After R9 correction, approval, export and verifier | **19** | **481** |

Flash-Lite RPM/RPD **5/500**; showcase Flash **0 used / 20 remaining** throughout (RPM **3**). **19 total = 1 startup model GET + 18 inference POSTs.** Persisted run counters **7/12, 5/12, 6/12**; logs and CLI reconcile. Reconstructed cumulative ranges in hosted-node order (plan, generate, initial critique, revise, follow-up): R7 **1→3→4→5→6→8**, R8 **8→9→10→11→12→13**, R9 **13→14→15→16→17→19**. No quota or auth errors.

## Correction audit, integrity and completed controls

Pre-approval READ ONLY snapshots show zero review events, no reject, and one saved `correction_request` per run. Records include reviewer `local_developer` (null user ID), exact reason, two selected paths, original artifact ID/version and hash, original values, request fingerprint, dependent-effects preview, no actual dependent changes, and result artifact ID. Every recursive diff is completely listed above. No objective, reward, ID, NPC line, citation, assumption, frozen setting, or unrelated field changed; corrected advisory evaluations bind v2. Each critique request hash stayed the same across its run's correction; the stored artifact provenance hash changed with content.

After approval, each run had exactly one approve event on v2, revisions **1/2**, consecutive failures **0/3**, completed state, an approved GameBlueprint, and immutable final v3. The governed download matched the passive HTTP 200 body byte for byte; each brief identifies final version 3 and includes provenance, citations, snapshot, and the frozen platform decision. Advisory panel metadata is absent. The read-only verifier exited **0** on each:

| Run | Raw reviewed SHA-256 | Raw final SHA-256 |
| --- | --- | --- |
| R7 | `79f2f91c680c6c36507d3c5b4e60162a70a111bfd63a5f0cbe955b2cd0aea5be` | `5b338986db0f48cb6d96e14cb18fabf6de188e4943ebb3794c10cc190fcc30d1` |
| R8 | `61506e3151f17bc93f6d53174935878cb7b5891fa1e101f647e0580acae5c068` | `879321e7ffa2c70ce7ac47d3a43fdea8fc60f10acbc8b1ff1650448c88dfbc3a` |
| R9 | `2bbd29dda7e78f63b25c076a315f96d307792b05f73f4e0cfd5c5aee3252d46c` | `25566e451bf96c3a52ceb1bd890169b2c10101f5460c4480a96aff836a809f8f` |

All **EQUAL_EXCEPT_DOCUMENTED_METADATA**. Only different path: `/npc_memory_design/memory_unspecified=true`; offending paths **[]**; runtime deferral did not apply. Raw hashes are not equal. Reload preserved completion, final lock and brief download. Approve, reject and correction/revision controls were absent on completed runs; no second mutation was sent to test the API.

## UX findings and limits

| ID | Rating | Observation |
| --- | --- | --- |
| REP3-01 | annoying | R7's critic blocked on mining increment mechanics, then cleared after unrelated hook changes; R8 missed an unsupported control assumption. A clean verdict is not semantic evidence. |
| REP3-02 | annoying | Scope preview is useful, but 14/18/20 individually confirmed proposals and long raw paths slow a short review. |
| REP3-03 | annoying | Decisions still requires opening View review trace after the inline run has already reached review. |
| REP3-04 | annoying | A populated hook list and empty advisories can coexist with generic commands, repeated NPC speech and unsupported prose. The panel accurately describes exact local checks, but does not certify content. |

No blocking UI issue, console error, page exception or frontend API 4xx/5xx during the batch. R7's first automation locator expected a critique heading and then tried to filter checkbox input text; the page was live and the dialog was already open. Corrected the locators without reloading the run, re-submitting start, or making an extra correction POST. Non-fatal startup messages: Chroma telemetry signature error (all three retrievals worked), missing Redis optional cache dependency (in-memory fallback), pypdf ARC4 deprecation. No responsive/accessibility audit was performed.

The batch proves the changed schema and server-owned fields on three fresh hosted Frostpeak runs, scoped correction mechanics and three governed exports. It does **not** demonstrate general hosted reliability, robust critique, safe free-text assumptions, failed-correction recovery, work on other GDDs, implementation readiness or Unity. All three briefs remain cited design scaffolds.

## Evidence and shutdown

Retained **31 screenshots**, three briefs, browser requests/responses and DOM snapshots, before/revised/final and recursive-diff JSON, pre-approval and completed READ ONLY snapshots, verifier JSON, quota checkpoints and timestamped backend logs under the QA folder. The post-run evidence check verified exact correction paths, no rejection, counters, exported body equality, immutable final, all persisted quest field values and reconciliation of the 18 POSTs plus one GET.

Startup followed the prior report: process-only stdin Compose override for the cached image, profile, timeout, fallback and `PYTHONPATH=/app`; `docker compose ... run --rm --no-deps --pull never --entrypoint python backend gemini_usage.py`; `alembic current` / `heads`; `docker compose ... up -d --no-build --pull never backend`; local `npm run dev` with `NEXT_PUBLIC_API_URL=http://localhost:8000`, telemetry disabled and npm offline. Read-only in-run checks used `docker compose exec -T backend python gemini_usage.py` and `python verify_final_integrity.py <new-run-id>` inside that backend.

After the final ledger read, closed Chromium first, stopped frontend with **Ctrl+C**, and stopped backend with **`docker compose stop backend`**. Backend exited **0**, restart count **0**, background cleanup shutdown completed, and nothing listened on 3000/8000 afterwards. PostgreSQL, Chroma and the new QA workspaces were left in place. Only this report is committed on **evidence/repeatability-3**; no code, `.env`, previous evidence, `docs/audit/`, README or MVP status changes. No push.
