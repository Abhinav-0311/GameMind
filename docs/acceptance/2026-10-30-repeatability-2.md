# DEV workflow repeatability — R4, R5 and R6 after more-advisories

Executed **2026-10-30, Asia/Calcutta**, approximately 18:14–18:30 for application execution; quota date **2026-10-30, America/Los_Angeles**. `<QA_DIR>` is the author's local, unpublished QA evidence folder. This batch's screenshots, downloads, passive browser evidence and READ ONLY database snapshots are under **`<QA_DIR>/repeatability-2-20261030-01/`**, not in this commit.

## Verdict and results

**Mechanical workflow PASS for these three runs; content-quality acceptance NOT established.** All three fresh runs reached real review, saved one two-field correction, approved, downloaded a brief, reloaded the completed state and passed the documented-metadata integrity verifier. None used mock fallback. Corrections stayed within their exact field scopes, but not all replacements were meaningfully better writing. The critic cleared every draft and revision despite semantic defects. This is not a complete MVP or a general reliability result.

| Run | Completed nodes; server API latency | Critic / findings | Advisories | Correction | Approval / export / verifier | Real inference attempts |
| --- | --- | --- | --- | --- | --- | ---: |
| R4 | Plan, retrieve, generate, critique, correction, follow-up critique, review, finalize; start **14,622.61 ms**, correction **5,483.78 ms** | Both `ready_for_review`; **0 findings** | Initial **1 exact-copy true positive**, then none; new three checks none | Saved two hooks plus one permitted annotation; replacements remain bare commands | **17** proposal confirmations; approve **200**, export **200**, saved **22,818 bytes**, completed reload; **EQUAL_EXCEPT_DOCUMENTED_METADATA** | **5** |
| R5 | Same nodes; start **14,815.46 ms**, correction **4,409.60 ms** | Both `ready_for_review`; **0 findings** | **2 situation-label true positives**, remain after hook correction; new three checks none | Saved two hooks only; more speakable but generic | **18** confirmations; approve **200**, export **200**, saved **27,349 bytes**, completed reload; same verifier verdict | **5** |
| R6 | Same nodes; start **12,320.94 ms**, correction **5,508.75 ms** | Both `ready_for_review`; **0 findings** | None initially or after correction | Saved two hooks only; better spoken form, but adds ambiguous inventory-retention wording | **18** confirmations; approve **200**, export **200**, saved **27,468 bytes**, completed reload; same verifier verdict | **5** |

These API durations exclude human reading time. Driver-observed start durations were 14,704 / 14,875 / 12,374 ms; correction durations 5,588 / 4,538 / 5,611 ms. Do not confuse them with individual node latency. No averages are claimed.

## Preconditions, environment and protocol

- During **all live execution**, current branch was **main**, HEAD **`3910c42e4fb5f3d86f8ca61cff16e839da894afe`**; `cb5dd03` was an ancestor; `git status --short` showed only `?? docs/audit/`. No application code, `.env`, dependencies or model settings file changed. Afterwards, created **evidence/repeatability-2** from that main HEAD for this document only. No push.
- The previous report is **absent from this main checkout**. Read its locally retained version with `git show d2e9b2d:docs/acceptance/2026-10-29-repeatability.md`; compared its results with the original saved R1–R3 JSON under `<QA_DIR>/repeatability-20261030-01/`. Did not recreate, modify or commit that older report or its evidence.
- Scope: MVP **P1.3–P1.5, P2.6, P3.5, P4.1–P4.2, P5.3**, Frostpeak only. The requested document-only scope leaves `MVP.md`, README and phase acceptance unchanged.
- Used cached **`gamemind-revise-tests:local`**, image **`sha256:77a2481d5d69bc58d1f4f2fa93a6ff032dbf6a9c653c93ea7545d095d9ba592a`**, with current backend source bind-mounted at `/app`, restart policy **no**. No image build, dependency install or download.
- Process overrides: **LLM_PROFILE=dev**, **GEMINI_TIMEOUT_SECONDS=180**, **DESIGN_AGENT_FALLBACK_TO_MOCK=true**, **PYTHONPATH=/app**. Effective model **gemini-3.5-flash-lite**; revise fallback excluded by **["revise"]**; schema reduction nodes **["revise"]**; keep-literals threshold **6,000 bytes**; per-run cap **12**; inline execution; job lease **300 s**. Production retries were not overridden.
- Ran `gemini_usage.py` before backend startup: Flash-Lite **0 used / 500 remaining**, RPM **5**, RPD **500**, not exhausted. Required remaining budget **40** passed. Showcase Flash stayed **0/20**, RPM **3**. Startup verified Flash-Lite with **one Google model GET**, counted **0 -> 1**.
- `alembic current` and `alembic heads` both **f4a6b8c0d123**. The documented startup ran `alembic upgrade head`; **no pending migration applied**. `/health` and `/ready` returned **200**, DB and Chroma healthy. Health now correctly reported **ai_mode=gemini, llm_provider=gemini**; Home's observed text was **“AI review is an explicit, governed choice.”**, with Gemini in readiness.
- Real installed **Playwright Chromium 156.0.8078.4**, headless, fresh browser context, **1440×1000**, downloads enabled; live frontend `http://localhost:3000` / backend port 8000. **No interception, fixtures, response substitution, server-side draft construction or API mutation outside browser controls.** Passive capture retained actual requests/responses, screenshots, DOM text, errors and exports. Separate SQL snapshots explicitly asserted **transaction_read_only=on**.
- Three new isolated workspaces; one Frostpeak source and one run in each. Earlier runs/workspaces were not mutated. No sign-in, explicit rejection, legacy section revision, finding adjudication, retry-critique, runtime materialization or Unity action.

Common browser setup: **New project -> Sources -> Load Frostpeak demo -> Decisions -> Review GDD -> Continue with local review -> save and mark Platform and controls resolved -> Review GDD again -> hosted consent -> Start governed review**. Saved the same exact decision in every workspace:

> unity_runtime_preview.content.target_platform must be "Windows PC"; this is human design direction, not a GDD fact

Runtime deferral unchecked (**defer_runtime=false**); unspecified memory checked (**allow_unspecified_memory=true**). The ordinary decisions-page start omits `max_revisions`; persisted default **2** was verified for all three. `fresh_dialogue=false` remained the normal default, as in R1–R3. Each start and correction was submitted once.

Consent text shown in every run:

> The selected source text may be sent to Google's Gemini API to create a cited draft and independent critique. On the free tier, Google may use submitted content to improve its products. Use only demo or non-confidential material. Mock mode runs offline and sends nothing to a hosted provider. No provider request is made until you confirm.

Every initial start returned **201 / awaiting_review**. Every initial scorecard was **75%**: grounding/completeness/consistency **100%**, integration readiness **0%**, blocker **Integration readiness**, pending proposal confirmations. Approve displayed **Approval blocked**, disabled. The critic and advisories were separate from that proposal gate. Confirming proposals enabled **Approve run** even while R5's non-blocking advisories remained. No degraded acknowledgement appeared: every hosted execution was actually Gemini, degraded=false; approval events record `acknowledge_degraded=false`.

## R4

Workspace **repeatability-r4-frostpeak-dev-20261030**; source **2334e685-4125-4461-8af0-9f27411cc4c2**; decision **0206d4f4-d54a-4f80-989b-9a46b989e2dd**; run **58eada9e-e608-46bf-b064-309141935e6d**. Draft v1 **2ccf71f4-fad8-4674-af9d-3e82191f2fa4**, revision v2 **116f781c-4ae1-453c-a148-0d65a45fd11e**, immutable final v3 **5a4a330c-68cc-4ca7-9cbf-9a724fa59149**. Ended completed, revisions **1/2**, consecutive failures **0/3**, not degraded.

Initial and follow-up critique: **ready_for_review**, findings **[]**. Both coverage maps: all sections **covered**, except **npc_memory_design=not_specified**. No finding severity/path/evidence index exists to enumerate. The initial critic asserted **“No implementation defects or contradictions found.”** despite copied quest dialogue.

### Advisories and inspection

Displayed one **medium objective_text_copied_as_dialogue**, short ID **#8bebe956**, full ID **8bebe956b0f5a24ce2dd739e6bac56dbc439caa2daf729d1175efa8b2ffb5ad3**. Paths:

- `/quest_hooks/content/quests/1/dialogue_hooks/0`
- `/quest_hooks/content/quests/1/objective`
- `/quest_hooks/content/quests/1/objectives/0`

Compared dialogue and main objective: **“Mine 5 chunks of raw sky-iron ore from the cliffside veins.”**; individual objective omits the trailing period. **True positive.** The first hook was a close objective restatement, not an exact normalized match; correctly outside the exact-copy recognizer, but still weak dialogue.

All three **new** checks had **zero displayed/persisted entries**, before and after correction: both hook lists nonempty; NPC assumptions use explicit **quest_index 0/1**, not wrong displayed Quest labels; runtime content contains only **target_platform=Windows PC**, supported by the frozen decision. No in-scope missed trigger or false positive found. This does **not** exercise positive rendering of the three new types.

The exact Section 1 summary, source rewards/5-chunk total, NPC archetypes and Section 2 faction-choice/world-state consequence were retained. Narrative **and** systems contain the faction consequence. No unsupported input method or return/delivery instruction found. NPC progress/completion speech is generic but broadly eligible-state consistent; no invented guard count, XP=0 or difficulty rating found.

### One correction; complete before/after

Selected exactly the two existing quest hook fields. Dialog preview stated only the selected text and conditional exact creative-proposal annotations could change; existing assumptions remain. Entered:

> Both quest hooks are objective text rather than natural spoken invitations. Replace /quest_hooks/content/quests/0/dialogue_hooks/0 with one short in-world spoken invitation to reclaim the Ash Pass by clearing guards and raising the Northern flag; both actions remain required without adding order. Replace /quest_hooks/content/quests/1/dialogue_hooks/0 with one short spoken request to mine exactly five chunks of raw sky-iron from the cliffside veins. Do not add return, delivery or hand-in requirements, claim completion, or change objectives, rewards, IDs, NPC speech or unrelated fields.

**Google 200**, **keep_literals / 608 bytes**, first response locally valid; follow-up critique Google **200**, no findings. Complete recursive diff:

| JSON path | Before, verbatim | After, verbatim |
| --- | --- | --- |
| `/quest_hooks/content/quests/0/dialogue_hooks/0` | Reclaim the Ash Pass border post by clearing guards and raising the Northern flag. | Reclaim the Ash Pass by clearing guards and raising the Northern flag. |
| `/quest_hooks/content/quests/1/dialogue_hooks/0` | Mine 5 chunks of raw sky-iron ore from the cliffside veins. | Mine exactly five chunks of raw sky-iron from the cliffside veins. |
| `/quest_hooks/content/quests/1/assumptions/3` | Absent | Generated quest dialogue hooks, event actions are creative proposals and require design approval before runtime use. |

Only those three paths changed. Objectives, rewards, IDs, NPC speech, other sections, citations and existing assumptions stayed unchanged. The exact-copy advisory disappeared and the new evaluation binds v2. **This is scope/validation success, not a meaningful writing improvement:** the first replacement merely drops “border post”; the second spells out five. Both remain task commands, with little voice or dramatic purpose.

Confirmed **17** proposals; approve **200 / completed**. Downloaded **R4-brief.md**, **22,818 bytes**, equal to the passive **200** export response. It states final version **3**, citations, source snapshot and frozen decision. No advisory list/IDs are exported. Read the saved brief: factual coverage is useful, but large JSON trigger dumps, repeated unexecuted contract checks, generic dialogue, unresolved actual engine bindings and unspecified failure/restart design keep this a scaffold, not an implementation-ready specification.

Screenshots: **R4-01-workspace.png** through **R4-11-reloaded.png** (source 02, decision 03, consent 04, review 05, correction dialog 06, corrected 07, confirmations 08, approved 09, export 10). Saved before/corrected/final/trace/diff JSON and pre-approval/completed READ ONLY DB snapshots use the R4 prefix.

## R5

Workspace **repeatability-r5-frostpeak-dev-20261030**; source **667fc11a-0f94-4348-b76d-d80f0ec553e0**; decision **0e675091-1202-47c7-97e4-70d26f961caa**; run **edf0418b-2055-487d-bc41-f07832bd739c**. Draft v1 **0b6d178f-0b24-49f6-b44c-09cb42601d21**, revision v2 **91f0c421-cb41-461d-b4fa-d3edd46cc82b**, immutable final v3 **cfd5bdde-c170-43cb-adfb-46450ef8c695**. Completed, revisions **1/2**, failures **0/3**, not degraded.

Both critiques **ready_for_review**, findings **[]**, same coverage map as R4. Initial summary claimed no conflicting decisions or missing design choices. The critic missed unsupported input, wrong numbering and narration instead of spoken quest hooks.

### Advisories, misses and prompt compliance

Displayed two **medium quest_label_mismatch** entries; both **true positives**:

| Short / full ID | Situation path; compared values |
| --- | --- |
| **#30297eaa** / `30297eaa164b7e9ba70bff7289b80d454779bd16ceaab409f48ab49bf3af4422` | `/npc_archetypes/content/npcs/0/dialogue_triggers/2/situation`: **Quest 0 completion**; linked `/eligibility/quest_id` **quest_1**, title **Quest Hook 1** |
| **#65d85aab** / `65d85aab22786787d1df44a371823556c73dc6352d852ee4743161a88509cc62` | `/npc_archetypes/content/npcs/1/dialogue_triggers/2/situation`: **Quest 1 completion**; linked `/eligibility/quest_id` **quest_2**, title **Quest Hook 2** |

Each panel message: **“The Quest label and linked quest ID disagree, or the numbered quest is absent. Review both fields; neither is assumed correct.”** Both entries remained unchanged after the hook-only correction, correctly bound to v2. They did not prevent approval after proposal confirmations.

The three **new** checks again had **zero** entries. Reasons and practical gaps:

- Hooks are populated, but **“Eldrin notes…” / “Kaelen demands…”** are narration, not spoken lines. Empty-list detection correctly does not claim to judge this. The new generation instruction was not obeyed in meaning.
- `/unity_runtime_preview/content/integration_notes/0`: **“Project targets Windows PC with primary keyboard and mouse input assumptions.”** No cited source or frozen decision specifies input. The check covers only `primary_input` and `target_platform`, so this unsupported assumption escaped it by appearing in a different field. Calling it an assumption is not source support; there is no corresponding input decision or runtime warning.
- `/npc_archetypes/content/npcs/0/assumptions/0`: **“Scoped proposal: Eldrin acts as a quest dialogue provider for Quest 0.”** Kaelen's equivalent says **Quest 1**, while linked to **quest_2**. These are wrong displayed numbers, not explicit indexes. The new recognizer deliberately requires **“associated with Quest N”**, so it abstained on this different phrasing. These are practical coverage misses, **not violations of the exact implemented rule**.

No in-scope false negative or false positive found for the new rules. The correctly cited exact summary and both quest rewards/quantity were retained. Faction consequence appears in narrative, not the systems list. No explicit return/hand-in instruction found.

### One correction; complete before/after

Applied the stated priority: correct existing narrative/objective-like hook text before situation labels. Two-field cap means the incorrect NPC labels were **not** corrected. Exact reason:

> Both quest dialogue hooks narrate what an NPC wants instead of being spoken lines. At /quest_hooks/content/quests/0/dialogue_hooks/0 write one short direct spoken request from Eldrin to the pathfinder to reclaim the Ash Pass border post by clearing guards and raising the Northern flag, with both actions required and no added order. At /quest_hooks/content/quests/1/dialogue_hooks/0 write one short direct spoken request from Kaelen to mine five chunks of raw sky-iron from the cliffside veins. Avoid third-person Eldrin notes or Kaelen demands phrasing. Do not add return, delivery, hand-in, equipment, rewards or completion claims. Preserve objectives, IDs, rewards, NPC speech and unrelated content.

**Google 200**, **keep_literals / 608 bytes**, first response valid; follow-up critique **200**, no findings. Exactly two changed paths; no annotation needed because the relevant annotation already existed:

| JSON path | Before, verbatim | After, verbatim |
| --- | --- | --- |
| `/quest_hooks/content/quests/0/dialogue_hooks/0` | Eldrin notes that the Ash Pass border post must be freed from occupying forces. | Pathfinder, please reclaim the Ash Pass border post by clearing guards and raising the Northern flag. |
| `/quest_hooks/content/quests/1/dialogue_hooks/0` | Kaelen demands the acquisition of raw sky-iron ore from the cliffside veins. | Mine five chunks of raw sky-iron from the cliffside veins. |

The new hooks are more speakable and preserve the required actions/quantity, but remain generic objective paraphrases. All unrelated content—including known numbering/input defects—was preserved. No second correction or finding-resolution action was taken.

Confirmed **18** proposals; approved **200 / completed**; saved/read **R5-brief.md**, **27,349 bytes**, matching the passive export response. It retains wrong situation/manual-test numbers, wrong assumption numbers and unsupported keyboard/mouse input. It also invents labelled failure/restart proposals: mining-tool break/repair-at-camp in assumptions versus equipment loss/player defeat and base-camp restart in the state contract. These are not source facts; their different conditions need human consolidation before implementation. The critic did not help. Approval here is deliberately isolated QA design approval, not certification that these defects are resolved.

**Additional nested-runtime defects found in the saved draft and actual brief:** unlike R4/R6, R5 has populated `quest.runtime` objects. `/quest_hooks/content/quests/0/runtime/objectives/0/quantity_required=1` assigns an unsupported guard count, despite the state-contract action saying eliminate all guards. Both quest runtime objects have **difficulty="Normal"**, absent from the GDD. `/quest_hooks/content/quests/1/runtime/xp_reward=0` converts unspecified XP to zero. The source only specifies 150 gold and sky-iron gear for this quest; unknown XP is not proof of zero. Runtime NPC slugs/target IDs are also not source-defined engine bindings. These objects are rendered verbatim in the exported brief as **Runtime**, not exercised in a game. In addition, quest 2 has **dependencies=["Quest Hook 1"]**, unsupported by an explicit source prerequisite, as in R6. Neither critique flags these. The three new checks inspect neither per-quest runtime bindings nor dependencies, so their silence does not validate them. The schema's required runtime fields (`QuestRuntimeBinding` / `QuestRuntimeObjectiveBinding` in `backend/app/design_agent/contracts.py`) enforce types, not source support. No raw hosted response was retained to independently assign every field's pre-assembly origin; the persisted/exported defects are certain.

Screenshots: **R5-01-source.png**, **02-decision**, **03-consent**, **04-review**, **05-correction-dialog**, **06-corrected**, **07-proposals**, **08-approved**, **09-export**, **10-reloaded** (all R5-prefixed `.png`). Before/corrected/final/trace/diff JSON and pre-approval/completed DB evidence retained.

## R6

Workspace **repeatability-r6-frostpeak-dev-20261030**; source **8cdc0b6f-c758-4884-94f8-be37e1150419**; decision **be3985b8-26ee-49fb-8f9a-c2db4580276e**; run **587fe103-99ab-4c6b-829e-4b8008d76319**. Draft v1 **30331db2-11b7-40d9-ab8c-aedc8821aef6**, revision v2 **b544502b-168f-4ce5-926f-af4a7af0779c**, immutable final v3 **03b25230-c93c-4f86-8858-ebf16fb4ee5c**. Completed, revisions **1/2**, failures **0/3**, not degraded.

Initial/follow-up critiques **ready_for_review**, findings **[]**, same coverage map. Follow-up summary explicitly says **“no implementation defects or conflicts with source evidence or binding design decisions.”** That is not credible semantic assurance for this content.

### Advisories and inspection

Displayed **“No exact matches found; this is not a quality guarantee.”** Persisted initial and revised advisory lists **[]**. New checks: no empty hook lists; assumption labels correctly use **Quest Hook 1/2**; runtime target Windows PC supported by the decision, no input-method claim. No in-scope missed trigger or false positive found.

Both initial hooks are task commands/restatements. They are present and speakable, not rich authored dialogue. The Section 1 summary is exact; faction consequences appear in **systems**, though omitted from the narrative paragraph. Source reward/quantity preserved.

Real defects/gaps that survive to export:

- `/npc_archetypes/content/npcs/1/dialogue_triggers/2/text`: **“The sky-iron ore has been delivered. Your strength is noted.”** The GDD specifies mining, not delivery, and structured completion only requires the mining event. This is an unsupported completed-delivery assertion, distinct from R3's explicit instruction to return. Neither critique caught it. NPC speech is outside the correction allowlist; no out-of-scope edit was attempted.
- `/quest_hooks/content/quests/1/dependencies` is **["Quest Hook 1"]**. The GDD lists quest lines but specifies no prerequisite. This is an unsupported added dependency, not a proven source order. No matching explicit dependency proposal explanation was found in the quest assumptions. The critic missed it; the hook correction cannot alter it.
- Failure/death/fall, nearest-checkpoint reload, repeat/no-reset policy and generated event keys remain labelled implementation proposals, not tested gameplay. The relationship notes add faction/allegiance details beyond the source's high-trust scholar description; check those rather than treating citations as proof of every sentence.

### One correction; complete before/after

Selected the two existing hook strings; dialog displayed the same conditional annotation dependencies. Exact reason:

> Both quest dialogue hooks are bare objective restatements. Replace /quest_hooks/content/quests/0/dialogue_hooks/0 with a short natural spoken invitation addressing the pathfinder to reclaim the Ash Pass border post by clearing guards and raising the Northern flag. Replace /quest_hooks/content/quests/1/dialogue_hooks/0 with a short natural spoken request to mine five chunks of raw sky-iron from the cliffside veins, keeping the full quantity. Make these spoken requests rather than task labels. Do not add delivery, return, hand-in, reward or completion claims; preserve objectives, rewards, IDs, NPC speech and all other fields.

**Google 200**, **keep_literals / 608 bytes**, first response valid; follow-up critique **200**, no findings. Exactly two changed paths; no annotation change:

| JSON path | Before, verbatim | After, verbatim |
| --- | --- | --- |
| `/quest_hooks/content/quests/0/dialogue_hooks/0` | Clear the guards holding the border post and raise our standard. | Pathfinder, I need you to reclaim the Ash Pass border post by clearing out the guards and raising our Northern flag. |
| `/quest_hooks/content/quests/1/dialogue_hooks/0` | Extract raw sky-iron ore from the volatile cliffside veins. | Pathfinder, please mine five chunks of raw sky-iron from the cliffside veins and keep the full quantity for us. |

Spoken framing improves, but **“keep the full quantity for us”** may imply an unsupported inventory-retention requirement. The human's “keeping the full quantity” instruction intended preservation of the five-chunk total, not a new retention mechanic; the generated line is ambiguous. Do not count it as clean semantic correction success. The unchanged NPC delivered claim is a definite unsupported statement. No additional correction was attempted.

Confirmed **18** proposals; approved **200 / completed**; saved/read **R6-brief.md**, **27,468 bytes**, byte-identical to the passive export response. Version **3**, citations/provenance and decision are present; advisory metadata is absent. No invented guard count, XP=0 or difficulty rating found. The brief still needs design work on prerequisite logic, delivery language, faction roles and actual runtime bindings.

Screenshots: **R6-01-source.png** through **R6-10-reloaded.png**, same suffixes as R5, plus **R6-11-completed-viewport.png**. Saved before/corrected/final/trace/diff and pre-approval/completed DB evidence retained.

## Six requested comparisons: R1–R3 versus R4–R6

Counts use **initial generated drafts**, not silently cleaned post-correction output. Read the earlier actual JSON as well as the locally retained report. A populated hook list is not automatically spoken or useful dialogue; the distinction is stated below.

| Requested item | R1–R3, out of 3 | R4–R6, out of 3 | What this actually means |
| --- | --- | --- | --- |
| Three new advisories displayed, separately | empty **0/3**; assumption label **0/3**; runtime value **0/3**—**not implemented then** | empty **0/3**; assumption label **0/3**; runtime value **0/3** | No new-rule positive case occurred in this batch. Zero hits do not establish detection quality or improvement. R5's differently located/worded defects escape the narrow scope. |
| Both quests have at least one populated hook | **1/3** (R3; copied objectives) | **3/3** | Empty lists fell from **2/3 to 0/3** in this sample. But R5's initial hooks are narration; R4 includes an exact copy; R6 has task commands. This is not 3/3 good spoken dialogue. |
| Unsupported runtime input method, anywhere in runtime content | **1/3** (R3 primary_input) | **1/3** (R5 integration_notes) | The claim moved outside the checked field; no observed reduction. `primary_input` specifically: **1/3 -> 0/3**, not proof all input assumptions disappeared. Windows PC is human-supported in every run. |
| Unsupported return/delivery/hand-in content in NPC speech or hooks | **1/3** (R3 “Return when…”) | **1/3** (R6 “has been delivered”) | R3 adds an explicit instruction; R6 asserts an unsupported delivery. **Explicit new return/delivery instructions** are **1/3 -> 0/3**, but claiming the broader delivery problem solved would be false. R6's later retention wording is separately noted, not counted as a definite new hand-in step. |
| Section 2 faction-choice consequence retained in narrative or systems | **2/3** (R2/R3) | **3/3** | R4 both; R5 narrative; R6 systems. Better coverage observed in three cases, not established prompt causality or future reliability. |
| Wrong displayed Quest number in NPC assumption notes | **1/3** (R3) | **1/3** (R5) | R2/R4 explicit quest_index wording is not counted wrong. R5's “provider for Quest N” evades the exact association recognizer. |

**Strict usable-spoken-line reading:** before correction R1/R2 offer no quest speech and R3 copies objective text; R4 offers an imperative plus an exact copy, R5 narration, R6 terse imperatives. It would be misleading to label the populated-list increase as a measured improvement in dialogue quality. After correction all three new runs have direct-address/imperative text, but R4 barely changes and R6 adds ambiguity. No fuzzy score or average was used.

No in-scope false negatives were found for the new rules because no initial/revised draft satisfied their exact trigger conditions. Practical misses are explicitly retained: R5's input in integration notes, alternate numbering-note phrasing, narration/near-copies, R6 delivery and prerequisite claims. Existing advisories produced **3 true-positive entries across 2/3 runs**, **0 observed false positives**; they are warnings, not approval vetoes or complete defect detection.

## Per-node provider, latency, tokens and requests

Every plan/generate/critique/revise below was actually **Gemini / gemini-3.5-flash-lite**, **degraded=false**, checked against persisted executions **and** timestamped transport logs. Each logged hosted HTTP attempt was **200**, each initial response locally accepted. All retry counts, repairs, truncation retries, source-anchoring corrective re-asks and local recoveries were **0**. Thus there was no retry status/backoff to report, and no test of transient-error recovery this time.

| Run / node | Latency ms | Input / output tokens | Real attempts | Wire schema mode / compact bytes |
| --- | ---: | --- | ---: | --- |
| R4 plan | 4,151 | 373 / 160 | 1 | full / 2,364 |
| R4 retrieve | 332 | 0 / 0 | 0 | local_retrieval / chroma-local-lexical-v1; 4 excerpts |
| R4 generate | 6,785 | 3,407 / 1,980 | 1 | full / 20,525 |
| R4 initial critique | 2,822 | 6,018 / 198 | 1 | full / 14,134 |
| R4 correction | 2,177 | 2,468 / 115 | 1 | keep_literals / 608 |
| R4 follow-up critique | 2,771 | 6,034 / 164 | 1 | full / 14,180 |
| R5 plan | 2,171 | 373 / 163 | 1 | full / 2,364 |
| R5 retrieve | 197 | 0 / 0 | 0 | local_retrieval / chroma-local-lexical-v1; 4 excerpts |
| R5 generate | 9,626 | 3,385 / 2,476 | 1 | full / 20,510 |
| R5 initial critique | 2,522 | 6,543 / 165 | 1 | full / 17,304 |
| R5 correction | 1,899 | 2,456 / 119 | 1 | keep_literals / 608 |
| R5 follow-up critique | 2,181 | 6,541 / 186 | 1 | full / 17,304 |
| R6 plan | 1,653 | 372 / 114 | 1 | full / 2,364 |
| R6 retrieve | 197 | 0 / 0 | 0 | local_retrieval / chroma-local-lexical-v1; 4 excerpts |
| R6 generate | 7,831 | 3,399 / 2,360 | 1 | full / 20,525 |
| R6 initial critique | 2,199 | 6,412 / 163 | 1 | full / 16,077 |
| R6 correction | 2,614 | 2,436 / 135 | 1 | keep_literals / 608 |
| R6 follow-up critique | 2,510 | 6,436 / 157 | 1 | full / 16,077 |

Review/correction-request/finalize are local, zero requests. Completed correction-resume / approval / finalize node latencies: R4 **9 / 35 / 53 ms**, R5 **11 / 38 / 60 ms**, R6 **9 / 36 / 65 ms**. Reported token totals: R4 **18,300 input / 2,617 output**; R5 **19,298 / 3,109**; R6 **19,055 / 2,929**. Cost unavailable. Summary in every draft was labelled **locally extracted exact source**, not falsely counted as mock generation or model authorship.

### Ledger reconciliation

All CLI readings use Pacific day **2026-10-30**; Flash-Lite RPM/RPD **5/500**, showcase **3/20**. Showcase remained **0 used / 20 remaining** throughout.

| Actual gemini_usage.py checkpoint | Flash-Lite used | Remaining |
| --- | ---: | ---: |
| Before startup | 0 | 500 |
| After startup model verification GET | 1 | 499 |
| After R4 initial review | 4 | 496 |
| After R4 correction / finalization / export | 6 | 494 |
| After R5 initial review | 9 | 491 |
| After R5 correction / finalization / export | 11 | 489 |
| After R6 initial review | 14 | 486 |
| After R6 correction; again after finalization/export and before shutdown | 16 | 484 |

**16 total Google requests = 1 startup GET + 15 inference POSTs.** Per-run persisted counters **5/12, 5/12, 5/12**. Ordered logs and `request_attempts=1` reconstruct node counter ranges: R4 **1->2->3->4->5->6**, R5 **6->7->8->9->10->11**, R6 **11->12->13->14->15->16**, in plan/generate/initial critique/revise/follow-up order. These are reconstructions, not claims of separate CLI calls between individual fast nodes. Approval, export, verifier, SQL snapshots and local retrieval used zero Google requests. No manual retry, probe, quota/auth error or extra run.

## Integrity, correction audit and completed controls

READ ONLY snapshots **before each approval** show **zero review events**, no reject event, no queued job (inline), completed `correction_request` with outcome **saved**, reviewer **local_developer**, null user ID, exact reason/paths/current values, original artifact ID/version/hash, request fingerprint, dependent-effects preview and actual dependent changes, plus result artifact ID. Revision count **1/2**, consecutive failures **0/3**, awaiting_review. The completed snapshot has exactly **one approve event**, bound to revised v2, no reject event, an approved GameBlueprint and immutable final v3. Failed-correction recovery was **not exercised**.

All diffs are enumerated above. Only selected hook paths and R4's exact dependent annotation changed. Resolved Windows PC decision, frozen scope flags, evidence, objectives, rewards, IDs and unrelated content stayed unchanged. Advisory evaluations bind the revised artifact IDs, not stale v1. Critique request hashes remain identical before/after each correction: R4 `e27ba64006700718e641bba8d7293991fa60af23377b7776c9489be1b189b6a3`; R5 `679a51a28216a9da2170881a7fa608da6e90dd4449f69d44b7f65f68c071fd22`; R6 `61baa797d50768a94318f9b5d794f575208213a7b21b5cb985e4b7cd2895eda8`. Artifact provenance hashes change appropriately with corrected content; no identity/gate was edited to clear a draft.

Ran `backend/verify_final_integrity.py` through the live READ ONLY path for each completed run, exit **0**:

| Run | Raw reviewed SHA-256 | Raw final SHA-256 |
| --- | --- | --- |
| R4 | `31a6258db60d347ec6b35be470dda582cda5df2e20b142473eef585d9132629c` | `ea09ca87891f5478fb520f948e68d6e3b57131813a4c690af0b6aeff98e39a8c` |
| R5 | `9a2be21a115c3e6cfc2f9236deafeb90f252ce66a6356668a33b0c8d489f6f0f` | `82f44bede3206cbfd87aff4c3b1cffeb6ef8f3a2e9985fa42cbe00f1b72f1bce` |
| R6 | `8f16fc81e612aa7ad97fb38d80218da52ddea7e668a9bec6e37b01ad6301ea04` | `bd5aa057931bcd8344666b55b674824f00c9acce906b746f0b8c94eae99e8991` |

Every verdict **EQUAL_EXCEPT_DOCUMENTED_METADATA**, only differing/permitted path **`/npc_memory_design/memory_unspecified=true`**, **offending_paths=[]**. Runtime deferral did not apply. **Raw hashes are not equal.** This meets the documented integrity policy, not strict byte equality.

After each approval, **Approve / Request correction / Request revision / Reject controls were absent**, leaving **Download technical brief**, **Download runtime JSON**, New run and Refresh. Reload preserved Approved / Final artifact locked / Review complete. No second mutation was submitted against a completed run; UI removal is the observed refusal, not a newly exercised API immutability attack. Runtime JSON was not downloaded. Each saved brief exactly matches its real passive export response and contains no advisory panel/list/IDs.

## UX findings

| ID | Rating | Observed issue or positive limit | Evidence |
| --- | --- | --- | --- |
| REP2-01 | annoying | Critic's clean, complete verdict still misses exact copied dialogue, wrong labels, unsupported input, added dependency, delivered-ore claim and R5's unsupported runtime count/XP/difficulty. Completeness 100% is structural, not semantic safety. | All review DOM/screenshots, drafts, briefs and stored critiques |
| REP2-02 | annoying | Empty-list improvement does not ensure speech: R5 returns narration and R4's correction barely edits commands. No advisory catches near-copy/narration by design. | R4/R5 before/after tables |
| REP2-03 | annoying | Review requires **17/18/18 individual proposal checkboxes**, in a narrow column; correction chooser repeats long paths and dependency prose. Exact scope is useful, but reading burden is high. | R4-06/08, R5-05/07, R6-05/07 screenshots |
| REP2-04 | annoying | Decisions' “preparing”/trace-link transition still requires opening View review trace although the inline start already reached awaiting_review. | Passive start 201 responses and Decisions DOM |
| REP2-05 | annoying | R5's alternate note wording and input in integration_notes escape the new recognizers; no in-scope bug found, but users must not read “no exact matches” as assurance. | R5 saved content and advisory panel |

No blocking UI, download, console error, page exception or frontend API 4xx/5xx was observed **during the running workflow checks**. The explicit pre-shutdown browser check reported console/errors **[]**. The final retained buffer contains **11 ERR_CONNECTION_REFUSED console messages after intentionally stopping the servers while Chromium was still open**: ten Next HMR WebSocket reconnect errors and one failed resource load; the final health request was at 13:00:49Z, after backend shutdown at 13:00:25Z. These are shutdown-induced, not silently discarded workflow errors. No page exception occurred. All three browser downloads worked, unlike R1's canceled download; this does not diagnose that old cancellation. Health/Home effective-provider wording is now correct. Consent names Google and its free-tier data-use terms. No absent-human-evaluation 404 appeared. Chroma query calls returned **200** for all three retrievals; no query 500 observed. The known non-fatal telemetry signature error appeared once at startup and did not prevent readiness. No retrieval fix was made or claimed. No full responsive, accessibility or performance audit was performed.

## Counts summary and honest interpretation

- Fresh runs created, real human review reached: **3/3**.
- Hosted generation locally accepted on first response: **3/3**; mock-served/degraded: **0/3**.
- One correction request with two exact fields: **3/3 attempted and saved**; out-of-scope changes **0/3**; failure/dead-end path **0/3 exercised**.
- Approval, saved/read browser brief, immutable final, completed reload and verifier: **3/3**.
- Critic blocked approval: **0/3 initial**, **0/3 follow-up**, despite the documented defects. No finding-resolution action or gate bypass.
- Three new advisory types: **0 entries**, so this is **not** a positive live test of their renderers or recall. Existing advisory true-positive runs **2/3**, observed false-positive runs **0/3**.
- Faction consequence observed **3/3**, compared with **2/3** previously. Empty quest hook lists **0/3**, compared with **2/3** previously. Unsupported input and wrong assumption labels each remain **1/3**. Unsupported delivery content also remains **1/3**, with a changed failure form.

This sample supports a repeatable mechanical path with small scope-preserving edits and all three downloads. It does **not** demonstrate reliable semantic critique, consistently good dialogue, absence of unsupported mechanics, reliable larger revisions, failed-correction recovery, implementation readiness or Unity. Unsupported dependencies appeared in **2/3** new drafts (R5/R6); nested runtime quantity/XP/difficulty defects in **1/3** (R5). Delivery/retention wording also escaped despite the revised instructions. Three runs cannot establish that the prompt caused the observed coverage/list changes, and no statistical/general improvement claim is made. The exported product is still a cited design scaffold requiring actual design judgment.

## Evidence, commands and shutdown

Retained **33 screenshots** (32 named snapshot captures including the initial loading Home, plus the completed viewport), three saved briefs, before/corrected/final/trace/diff JSON for each run, three pre-approval and three completed READ ONLY snapshots, `baseline-comparison.json`, `browser-evidence.json`, timestamped `backend.log` and `shutdown.log`. Evidence lives only under the QA folder. CLI/verifier outputs were observed directly and reproduced above; no separate raw CLI files are claimed.

Normal startup, using a process-only stdin Compose override:

```powershell
# Override: cached SDK image, restart "no", LLM_PROFILE=dev,
# GEMINI_TIMEOUT_SECONDS=180, DESIGN_AGENT_FALLBACK_TO_MOCK=true, PYTHONPATH=/app
$override | docker compose -f docker-compose.yml -f - run --rm --no-deps --pull never --entrypoint python backend gemini_usage.py
$override | docker compose -f docker-compose.yml -f - run --rm --no-deps --pull never --entrypoint sh backend -c 'alembic current && alembic heads'
$override | docker compose -f docker-compose.yml -f - up -d --no-build --pull never backend
# From frontend/, process-only NEXT_PUBLIC_API_URL=http://localhost:8000,
# LLM_PROFILE=dev, NEXT_TELEMETRY_DISABLED=1, npm offline:
npm run dev
docker compose exec -T backend python gemini_usage.py
docker compose exec -T backend python verify_final_integrity.py <new-run-id>
```

Setup/diagnostic limitations: initial Node ESM loading and sandbox Chromium launches failed **before any model call**; the installed executable launched successfully through the authorized host process. A read-only snapshot query initially ordered executions by nonexistent `created_at`; corrected the QA reader to use valid columns, with no write or workflow retry. Initial navigation snapshots caught loading states; waited for observed controls. These are driver/setup mistakes, not extra design attempts. The older report being on a different local branch was handled by reading its retained commit, not by switching the live app away from main or merging unrequested history.

After final CLI **16 / 484 remaining**, stopped backend with **`docker compose stop backend`** (exit **0**), frontend with **Ctrl+C** (expected interrupted process), closed Chromium/context and exited the driver. Verified backend exited **0**, restart count **0**, restart policy **no**, graceful cleanup-worker shutdown, and **no listeners on ports 3000/8000**. PostgreSQL, Chroma and new QA workspaces remain; no volumes or old evidence deleted. No application test suite, runtime materialization or Unity operation.

Only **this document** is included in the local evidence-branch commit. `docs/audit/` remains untracked and untouched. No code, `.env`, README, MVP status, prior run or prior acceptance report was edited. No push.
