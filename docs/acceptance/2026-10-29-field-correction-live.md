# Live field-scoped correction — Frostpeak / Gemini Flash-Lite

Execution date: **2026-10-30, Asia/Calcutta**; Pacific quota date: **2026-10-29**. The filename retains the date requested. `<QA_DIR>` denotes the author's local, unpublished evidence folder; screenshots, database snapshots and the exported brief are not committed.

## Verdict

**PASS for the narrow success-path check.** One real Gemini quest-hook correction changed exactly the selected string plus its enumerated server-derived proposal annotation, and produced better spoken dialogue. A new critique followed. The browser confirmed proposals, approved once, downloaded the brief and reloaded the completed state. The final artifact is immutable and the integrity verifier returned **EQUAL_EXCEPT_DOCUMENTED_METADATA**.

**Not full-MVP or general content-quality acceptance.** Quest 1 still contains a copied objective as dialogue, the critic missed it twice, and the brief contains an unsupported source-ordering assertion. The new hook is usable as a generic spoken invitation, not polished character-specific writing. The failed-correction -> original-approval branch was **not exercised** because correction succeeded; this run does not establish that separate live recovery outcome.

Only attempt 1 was used. No second workspace/run, rejection, finding-resolution action, sign-in, manual workflow retry, runtime download/materialization or Unity action occurred. No existing QA run was modified. The only repository change is this report; no code, `.env`, README, MVP status or dependency change.

## Setup and preconditions

- Branch: `feature/field-corrections`; tested HEAD: **`c1c496d7e3893d6dc554e696b3423b21984c43ae`**. Both `964eae7` and `3a88cad` passed ancestry checks. Initial working tree: only `?? docs/audit/`.
- Cached image: `gamemind-revise-tests:local`, installed `google-genai==2.33.0`, backend source bind-mounted at `/app`, restart policy **no**. Mounted and host `workflow.py` SHA-256 matched: `91d8b76723e8c43d3e5b4721ebe1ec2db289c0cce9798a83ef79a586c3f91d76`.
- Process-only settings: `LLM_PROFILE=dev`, model `gemini-3.5-flash-lite`, `GEMINI_TIMEOUT_SECONDS=180`, `DESIGN_AGENT_FALLBACK_TO_MOCK=true`, `PYTHONPATH=/app`. Effective fallback-disabled nodes and schema-reduction nodes were both `["revise"]`; literal-preservation threshold **6,000 bytes**, execution **inline**, per-run cap **12**. Production transport retry/repair policy was not overridden. Only API-key presence was checked, never its value.
- Ran `gemini_usage.py` **before backend startup** using a one-off SDK container with those overrides. Flash-Lite: **4 used, 496 remaining**, configured **5 RPM / 500 RPD**. Flash: **0 used, 20 remaining**, **3 RPM / 20 RPD**. The required remaining-budget threshold of 25 passed. This CLI reads the local ledger and makes no Google request.
- Started backend with the normal stdin-only Compose override, `up -d --no-build --pull never backend`; normal command remained `alembic upgrade head && exec uvicorn main:app --host 0.0.0.0 --port 8000 --reload`. Alembic current/head both reported **`f4a6b8c0d123`**. No pending migration or upgrade step was applied.
- Health and readiness returned **200**, database/Chroma healthy, effective provider **gemini**. Startup verification made one successful Google model GET, counted **4 -> 5**. Restart count stayed **0**.
- Frontend: normal `npm run dev`, process-only `NEXT_PUBLIC_API_URL=http://localhost:8000`, `LLM_PROFILE=dev`, telemetry disabled; served `http://localhost:3000`.
- Real Playwright Chromium **149.0.7827.55**, headless **1440 x 1000**, fresh browser context, live backend. No route interception, fixtures, response substitution or scripted API mutations. Read-only API requests and PostgreSQL verification were used for evidence, not to perform the flow.

The browser bridge timed out; the sandboxed Node session also had import/browser-launch restrictions. Direct host Playwright launched the installed Chromium successfully, without downloads. A settings-print diagnostic initially could not JSON-encode a frozenset; its corrected diagnostic made no model request. Locator mistakes waiting for decisions before pressing Review GDD, selecting the nested `main`, and treating the Quests tab as a button were driver errors, not workflow failures. They did not repeat any generation, correction or approval POST. Actual run mutations are enumerated below.

Known non-fatal logs: Chroma telemetry signature error; missing optional Redis module falling back to in-memory cache; pypdf/ARC4 deprecation. None prevented startup/readiness. The legacy health `ai_mode=local_demo` label was not treated as provider evidence: effective provider, transport logs and trace showed Gemini.

QA root: `<QA_DIR>/field-correction-live-20261030-01/`.

## Attempt 1 — workspace, source, decision and consent

| Identity | Value |
| --- | --- |
| Workspace | `field-correction-frostpeak-dev-20261030-attempt-1` |
| Source | `b02eb217-8d16-405e-b99e-20a84e8194ef`, bundled Frostpeak, four chunks |
| Resolved decision | `7bd0e985-2070-4bda-8f00-c0e05aaac207` |
| Run | `b0ee5dfd-2275-4651-8bcc-280d9c218ebf` |
| Frozen evidence snapshot | `3fbe404f-9f07-4e02-ac20-c8a361f289d1` |
| Draft v1 | `05a12ca4-ad69-4886-8dfe-38d36cff6fbe` |
| Corrected v2 | `965a0488-a425-4eac-825f-b5153666b81e` |
| Final v3 | `71734648-e5e6-4ff5-8574-b03147fd4510` |
| Approved blueprint | `58fe8cad-6655-4443-a709-2453713d3704` |

Through the browser: created the workspace, loaded only Frostpeak, opened local GDD review, saved and marked Platform and controls resolved with the exact text:

> unity_runtime_preview.content.target_platform must be "Windows PC".

Reopened Review GDD. Runtime deferral was **unchecked**, so runtime preview was enabled; unspecified-memory scope was explicitly **checked** before generation. The normal decisions-page API omitted `max_revisions`; its default produced **2**, confirmed in the response and database. `defer_runtime=false` and `allow_unspecified_memory=true` were frozen; the runtime preview held `target_platform="Windows PC"`.

The consent dialog displayed:

> The selected source text may be sent to Google's Gemini API to create a cited draft and independent critique. On the free tier, Google may use submitted content to improve its products. Use only demo or non-confidential material. Mock mode runs offline and sends nothing to a hosted provider. No provider request is made until you confirm.

It also explained the fixed runtime/memory scope. **Start governed review was clicked once**, submitting `hosted_provider_consent=true` through the ordinary API. The first local-review opening was declined using Continue with local review while the decision was prepared; that made no inference request.

Screenshots: `02-new-workspace.png`, `03-frostpeak-loaded.png`, `04-hosted-consent-initial.png`, `05-resolved-platform.png`, `06-hosted-consent-final.png`, all under the QA root above.

## Initial draft, critique and advisory selection

The run reached **awaiting_review**, revisions **0/2**, consecutive failures **0/3**, **not degraded**. Generation passed local validation on its first response. Summary was the exact Section 1 premise, visibly labelled local exact-source extraction rather than model-authored; this was not mock fallback.

Accepted initial critique: **ready_for_review**, **findings `[]`**. Coverage was `covered` for every section except `npc_memory_design=not_specified`. No accepted finding paths or evidence indexes exist to list. The critic said "No defects found," but both quest hooks copied objective text.

The displayed non-blocking list contained two **medium / objective text copied as dialogue** entries. For both, the message was: "Dialogue exactly repeats an objective after text normalization. Review whether this is useful spoken dialogue."

| Displayed ID / full persisted ID | Paths and exact compared values |
| --- | --- |
| `#bafbffc0` / `bafbffc0eca64bce96c66d5e3eaacb9e40f71a392cdd92dd2a5525c830beecf9` | `/quest_hooks/content/quests/0/dialogue_hooks/0` equals `/quest_hooks/content/quests/0/objective`: `Reclaim the Ash Pass border post. Players must clear guards and raise the Northern flag.` |
| `#8bebe956` / `8bebe956b0f5a24ce2dd739e6bac56dbc439caa2daf729d1175efa8b2ffb5ad3` | `/quest_hooks/content/quests/1/dialogue_hooks/0` equals `/quest_hooks/content/quests/1/objective`: `Mine 5 chunks of raw sky-iron ore from the cliffside veins.` Also matches `/quest_hooks/content/quests/1/objectives/0`: the same text without its final period. |

Both were true positives. No quest-label mismatch or warning-in-rules advisory applied. NPC situation labels were not numbered Quest 0/1 labels, and their linked quest topics/IDs matched. These checks do not detect every semantic defect; their absence is not a complete quality check.

Approve was initially **disabled**. The scorecard was **75%**: grounding/completeness/consistency **100%** each, integration readiness **0%**, sole blocker **Integration readiness**, with **16 unconfirmed proposals**. The current critic did not block approval. Thus the initial disabled state was explained by existing proposal confirmations, not advisories.

Screenshots: `07-draft-review.png`, `08-advisories-before.png`. The full API snapshot is `before-api.json`.

## One exact correction

Selected priority-(a) defect: Quest 2's copied hook, exactly **`/quest_hooks/content/quests/1/dialogue_hooks/0`**. Opened Request correction and explicitly checked **one** field. No advisory prefill was available.

The current value was:

> Mine 5 chunks of raw sky-iron ore from the cliffside veins.

The dialog said the action was not a rejection; a failed correction leaves the draft unchanged and still approvable if other gates allow; a saved correction uses one revision and gets a new critique. Its dependent-effect preview for this field was:

> Only this quest’s assumptions may gain the server’s exact “Generated quest … are creative proposals and require design approval before runtime use.” annotation, derived from its cited source. Existing assumptions remain.

This is a conditional annotation-form preview, not a prediction of the model's future replacement. The dialog also listed the manual-test dependency for situation edits, but none was selected. Full dialog text is retained in `browser-evidence.json`; `09-correction-dialog.png` records the scrolled dialog/reason/submission area. Not every field row is visible at once in that screenshot.

Entered this exact reason and clicked **Send correction request once**:

> The Quest 2 dialogue hook at /quest_hooks/content/quests/1/dialogue_hooks/0 is copied directly from the objective and reads like a task sheet, not spoken dialogue. Replace only that hook with one short, natural spoken invitation to mine five chunks of raw sky-iron from the cliffside veins. Do not claim the mining is already complete, invent a delivery requirement, or change the objective, quantity, rewards, IDs or other fields.

The request carried `decision=request_correction`, v1's `artifact_id`, that reason, and a one-element `target_paths` list; no section target or reject action. The schema log was **`node=revise mode=keep_literals bytes=558`**. Google returned **HTTP 200**; the first response passed local validation. **No revise schema/local-validation error, repair, truncation resend, provider retry or mock fallback occurred.** The ordinary review API returned **200 / awaiting_review** after correction and follow-up critique, with server duration **11,513.95 ms**.

### Complete v1 -> v2 content diff

Independent recursive comparison of both full saved contents found exactly these two changed paths:

| JSON pointer | Before | After |
| --- | --- | --- |
| `/quest_hooks/content/quests/1/dialogue_hooks/0` | `Mine 5 chunks of raw sky-iron ore from the cliffside veins.` | `Hey there, would you mind heading over to the cliffside veins and mining five chunks of raw sky-iron for us?` |
| `/quest_hooks/content/quests/1/assumptions/4` | Absent | `Generated quest dialogue hooks, event actions are creative proposals and require design approval before runtime use.` |

No other path changed. All prior assumptions stayed; objectives, rewards, quest IDs, state contracts, NPC speech/eligibility/manual tests, citations and all unrelated sections remained identical. No manual-test change was expected for this hook edit.

**Plain assessment:** the new string is genuinely more useful dialogue: a spoken invitation instead of an objective pasted into a dialogue slot. It preserves five chunks, raw sky-iron and the cliffside location; it neither claims completion nor adds a delivery action. It is generic/casual and not tailored to Kaelen's cautious voice. "For us" is proposed voice/context, not a new verified GDD fact. This is a meaningful narrow improvement, not high-end narrative writing.

### Audit/counters before approval

`db-before-approval.json` was collected in a PostgreSQL transaction with **`transaction_read_only=on`**, scoped only to this new run/project:

- **Zero review events**, hence no rejection event. Inline execution created **zero queue jobs**, as expected.
- Run **awaiting_review**, revision **1/2**, consecutive failures **0/3**, not degraded; per-run Gemini count **6/12**.
- Request execution `7ca93686-26fe-4d54-8ef0-68cff0153959`: status **completed**, action **request_correction**, outcome **saved**.
- Recorded reviewer **local_developer**, user ID **null**; exact reason and path; original v1 artifact ID/version; original hook string; original full-content hash; request fingerprint; conditional dependent-effect rule; actual before/after assumptions; resulting v2 artifact ID; revision count **1**, error **null**. A human-review execution also recorded the action/reason/paths and linked request execution.
- Original v1 hash: `d50f730f6d1fa74f7b44ddb081486b77a7b2bd60979240e3d2d2a920bc1a5ddc`.
- Corrected v2 hash: `975c9a023536db8c13e20dea209c747a91b6fe3aeb3bdb9b3e680999d0f76a8f`.

Follow-up critique: **ready_for_review**, **findings `[]`**, same coverage labels (memory `not_specified`, other sections `covered`). It still missed the unchanged Quest 1 copy and source-ordering issue. The updated advisory evaluation was bound to v2, with exactly **one** remaining entry: `#bafbffc0` for Quest 1. Quest 2's copy advisory disappeared. The scorecard stayed **75%** with integration readiness as the sole blocker and **17** proposals, because the new permitted annotation also needed confirmation.

Evidence: `corrected-api.json`, `before-after-diff.json`, `db-before-approval.json`, `trace.json`, `10-correction-result-viewport.png`.

## Approval, export and completed state

Confirmed all **17** displayed proposals through their UI checkboxes. Approve became **enabled while Quest 1's advisory remained**. No degraded acknowledgement appeared because no hosted node used mock/degraded output. Clicked **Approve run once**: **HTTP 200**, run **completed**, immutable final **version 3**, blueprint **approved**.

Clicked **Download technical brief** once. The governed final-artifact endpoint returned **200**, downloading `gamemind-agent-brief.md`; saved as `<QA_DIR>/field-correction-live-20261030-01/technical-brief.md`, **23,800 bytes**. It contains the corrected spoken hook, unchanged objectives/rewards/IDs, citations, frozen excerpts, the frozen Windows PC decision, explicit proposal labels, version **3**, and memory's unspecified warning. It does **not** contain the advisory list/IDs or present them as critique findings. The UI downloaded Markdown; no in-app brief-preview screen was proved.

The correction/Approve/Request revision controls were all **absent** on the completed run (counts **0 / 0 / 0**), so the UI provided no action to submit any of them again. No forced post-completion API mutation was made. Reload preserved completed/locked state and the same three absent controls. This is UI refusal by hiding actions, not a claimed observed backend 409 from another POST.

Final READ ONLY database/API checks: run **completed**, revisions **1/2**, failures **0/3**, final v3 **immutable=true**, approved blueprint exists, exactly **one review event**, decision **approve**, linked to corrected v2. There were still **zero reject events**. Screenshots: `12-approval-enabled.png`, `13-approved-quest.png`, `14-export-complete.png`, `15-completed-reload.png`.

### Final-integrity verifier

Ran `python -B verify_final_integrity.py b0ee5dfd-2275-4651-8bcc-280d9c218ebf` against live data, using its READ ONLY database path, exit **0**:

```json
{
  "reviewed_sha256": "975c9a023536db8c13e20dea209c747a91b6fe3aeb3bdb9b3e680999d0f76a8f",
  "final_sha256": "1edd437b20e94baf665dccc401f46cccb438fb35d686c6722408b693e0bd48cd",
  "differing_paths": ["/npc_memory_design/memory_unspecified"],
  "permitted_additions": [{"path": "/npc_memory_design/memory_unspecified", "value": true}],
  "offending_paths": [],
  "verdict": "EQUAL_EXCEPT_DOCUMENTED_METADATA"
}
```

Raw hashes are **not equal**. The one difference is the documented deterministic metadata addition justified by frozen unspecified-memory scope and reviewed empty/uncited/warned memory. Runtime deferral was false and added no metadata. No broader ignored section or arbitrary content difference was accepted.

**Dead-end verdict:** correction-success path passed without writing a rejection; approval completed normally. **Failed-correction recovery is NOT TESTED live here.** It was neither induced nor inferred from this success.

## Real requests, models, latency and validation

All hosted executions were actually **Gemini / gemini-3.5-flash-lite**, not mock. Transport logs independently show one startup GET and six inference POSTs, all HTTP **200**. Trace fallback/degraded flags, repair/local-recovery/truncation flags and transport evidence agree.

| Node | Actual provider/model | Degraded | Latency | Input / output tokens | Real requests / ledger positions |
| --- | --- | --- | ---: | ---: | --- |
| Startup verification | Google model GET / Flash-Lite | N/A | Not separately timed | Not returned | 1; **4 -> 5** |
| Plan | Gemini / Flash-Lite | false | 2,169 ms | 373 / 171 | 1; **5 -> 6** |
| Retrieve | local retrieval / chroma-local-lexical-v1 | N/A, not fallback | 312 ms | 0 / 0 | 0; stays **6** |
| Generate | Gemini / Flash-Lite | false | 8,892 ms | 3,357 / 2,143 | 1; **6 -> 7** |
| Initial critique | Gemini / Flash-Lite | false | 5,949 ms | 12,123 / 350 total | 2; **7 -> 9** |
| Field correction / revise | Gemini / Flash-Lite | false | 2,191 ms | 1,702 / 74 | 1; **9 -> 10** |
| Follow-up critique | Gemini / Flash-Lite | false | 8,900 ms | 6,048 / 178 | 1; **10 -> 11** |
| Approval / finalize / export / reload | local | no fallback | Review 394 ms; finalize 49 ms | 0 / 0 | 0; stays **11** |

Initial plan-through-critique node latencies sum to **17,322 ms**; that is not a separately timed browser end-to-end measurement. Inference tokens total **23,603 input + 2,916 output = 26,519**. Cost is unavailable, not measured zero.

The initial critique's first HTTP-200 response failed the source-anchored-omissions validation rule. The production **one corrective re-ask** succeeded: `source_omission_reask=accepted`, `independent_review_retries=1`, `request_attempts=2`, `retry_count=1`. First response: **6,019 / 179** tokens; corrective response: **6,104 / 171**. Diagnostics retain a root-path `value_error`, not the offending raw finding/value; no exact discarded finding is claimed. This was **not** a transport 5xx retry, truncation resend, generic JSON repair, manual retry, or degraded fallback. The revised draft's critique needed only one request.

Wire schemas observed in the transport log: plan **full / 2,364 bytes**; generation **full / 20,510**; initial critique **full / 14,282**, twice; correction **keep_literals / 558**; follow-up critique **full / 14,328**. All local validation/assembly/preservation gates remained in force. No 400/429/5xx, auth error, transport retry/backoff or timeout occurred.

| CLI snapshot, Pacific date 2026-10-29 | Flash-Lite used / remaining | Flash used / remaining |
| --- | --- | --- |
| Before backend startup | **4 / 496** | **0 / 20** |
| After startup | **5 / 495** | **0 / 20** |
| After initial generation/critique | **9 / 491** | **0 / 20** |
| After correction/critique | **11 / 489** | **0 / 20** |
| After approval/export/reload, final CLI | **11 / 489** | **0 / 20** |

Total new Google attempts: **7 = 1 startup GET + 6 inference POSTs**. Run counter **6/12** reconciles with the six inference requests; startup is outside that run. Intermediate per-node ledger positions above are reconstructed from ordered transport calls and trace attempt counts, not separate CLI invocations between every node. The named stage snapshots are actual CLI readings. No quota/auth stop condition occurred.

### Browser mutations and important responses

| Action | Method/route | Result |
| --- | --- | --- |
| New workspace | POST `/api/v1/projects/` | 201 |
| Load Frostpeak | POST `/api/v1/documents/demo/frostpeak` | 201 |
| Local reviews, before and after decision | POST `/api/v1/decisions/sync`, twice | 200 each |
| Save decision; resolve it | PUT `/api/v1/decisions/7bd0e985-2070-4bda-8f00-c0e05aaac207`, twice | 200 each |
| Start governed run, once | POST `/api/v1/design-agent/runs` | 201 / awaiting_review |
| Exact correction, once | POST this run's `/review`, `request_correction` | 200 / awaiting_review, v2 |
| Approve, once | POST this run's `/review`, `approve` | 200 / completed, final v3 |
| Export brief, once | GET this run's `/exports/technical-brief` | 200 / downloaded |
| Read-only run/trace/finding reads | GET, this run/project only after creation | 200 |

There were no browser console errors or page exceptions. No absent-human-evaluation 404 was observed. Browser evidence records no reject action, finding-resolution POST or duplicate run/correction/approval request.

## Honest content assessment

Good: exact cited Section 1 premise; faithful named setting/factions/art direction; correct **5 chunks**, **100 gold + 250 XP**, **150 gold + sky-iron gear**; distinct, eligible NPC stages; explicit proposed state contracts/manual checks; narrow field preservation; cited frozen sources and human platform direction survive export. The corrected hook is actually spoken prose and remains in the brief. No invented guard count, extra reward, difficulty rating, zero-XP reward, keyboard/mouse input, or unsupported persistent-memory capability was found in this draft.

Weak or wrong:

1. **Quest 1's dialogue hook is still its objective verbatim**, including "Players must". The advisory correctly remains; neither initial nor follow-up critic caught it. Only one field was authorized for correction, so it was not changed. Its advisory is deliberately not exported, although the bad line itself is exported.
2. **"Source ordering: clear guards then raise the Northern flag" is not established by the GDD.** The source requires both actions, not an order. Other generated manual checks explicitly test both action orders, making this note internally confusing. A citation and 100% structural grounding score do not validate that ordering claim.
3. Quest-giver assignments, new speech, interaction events, `no reset`, state flags and observable engine actions are implementation/creative proposals, not GDD facts. They need implementation choices and real tests. The new casual "Hey there" hook is not a convincing Kaelen-specific voice; its speaker is not explicitly assigned by this hook field.
4. Failure and restart actions are unassigned; "default server rules apply" is not a complete failure/retry design. Runtime remains **planning_only** with no executable bindings. Windows PC is the frozen human decision, not something stated in the GDD; the brief's separate decision provenance matters more than its runtime section's source citations.
5. The brief is faithful to the approved scaffold but verbose: JSON dialogue-trigger objects, repeated manual-test prose and state-contract dumps need editing before a small team could use it as a clean implementation handoff. It is **not an implementation-ready specification**.

The critic's statement that all source elements were "thoroughly reviewed" and no defects existed was overconfident. This successful one-field correction does not solve critic accuracy or whole-draft usefulness.

## UX findings

No blocker prevented this narrow flow.

| ID | Rating | Observed issue | Screenshot/evidence |
| --- | --- | --- | --- |
| FC01 | annoying | Eight verbose exact-path choices repeat dependency prose; the selected hook scrolls away while entering the reason/submitting. No advisory-path prefill or persistent selected-field summary. Current value and dependency text are present, but not all visible together. | `09-correction-dialog.png`, saved dialog DOM |
| FC02 | annoying | The long, narrow review column combines score explanations, advisories and 17 individual confirmations, producing substantial scrolling/empty space alongside the short Summary. | `07-draft-review.png`, `12-approval-enabled.png` |
| FC03 | annoying | Home still describes NVIDIA and shows Local Demo while the effective provider is Gemini. The actual governed consent is provider-aware and correct; the legacy Home/health mode label is misleading. | `01-home.png`, health output |
| FC04 | cosmetic | In the captured Quests view, Summary retains the visually strongest lime tab treatment while Quests content is displayed; the active-tab signal is ambiguous. No claim of broken tab navigation: selecting the tab worked. | `13-approved-quest.png` |

What worked: effective-provider/free-tier consent, source-scoped decision, visible exact-copy comparisons and short IDs, explicit one-field selection, honest dependent-effect explanation, source/identity preservation, refreshed v2 advisories, proposal-bound approval, immutable final/export, and durable completed-state reload. Console/page-error counts were zero.

## Evidence and cleanup

Screenshot paths are `<QA_DIR>/field-correction-live-20261030-01/<filename>` for the filenames listed above. `11-corrected-quest-and-review.png` does **not** exist: that attempted capture was interrupted by the incorrect button-role selector; the actual Quests view was later captured as `13-approved-quest.png` using its real tab role. No failed selector was repeated as a workflow mutation.

Other retained evidence: `browser-evidence.json`, `start-response.json`, `before-api.json`, `corrected-api.json`, `before-after-diff.json`, `db-before-approval.json`, `approval-response.json`, `final-api.json`, `db-final.json`, `trace.json`, `technical-brief.md`, timestamped `backend.log` / `backend-stderr.log`, and `shutdown.log`. PostgreSQL verification used explicitly READ ONLY transactions; no test suite was run against application data.

Closed the fresh browser/context and exited its Node driver. Stopped frontend with Ctrl+C (expected interrupted-process exit), then **`docker compose stop backend`**. Backend exited **0**, restart count **0**, restart policy **no**; logs show graceful cleanup-worker/application shutdown. No listeners remained on **3000/8000**. Existing PostgreSQL/Chroma remained running; no workspace, run, QA folder or persistent volume was deleted. Final quota remained **11 Flash-Lite / 0 Flash**. No push.
