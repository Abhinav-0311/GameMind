# Phase 4: live generation and dashboard acceptance

**Result: acceptance failed. The QA exercise is finished; the recovery phase is not accepted.** No successful end-to-end demo or production-reliability claim is justified.

## Scope and method

- Authorization: six NVIDIA HTTP requests total, including retries/repairs, across two new isolated QA workspaces. Exactly **6/6** were sent. No further requests are authorized by this check.
- CyberRakshak and the bundled **synthetic** Frostpeak sample were uploaded through the live documents API and indexed normally. Frostpeak is not evidence of performance on an independently authored public GDD; that check remains open.
- Existing model/env settings were unchanged: planning `nvidia/nemotron-3.5-lightning-30b-a3b`; generation/critique `nvidia/nemotron-3-super-120b-a12b`. Token limits: planning 1024, generation 4096, critique 1024. A counting HTTP client enforced three requests per GDD and six globally; normal retries/repairs consumed that allowance.
- Run creation exercised the real FastAPI route, service, Chroma retrieval, PostgreSQL persistence and durable LangGraph workflow through an in-process TestClient with only the budget-counting NVIDIA transport dependency injected. It did **not** prove a browser-clicked generation submission over the running API server. Browser reads and export checks used the real running backend, without fixtures.
- Before either run, missing hosted consent returned 409 with zero NVIDIA calls. Source/decision actions affected only the new QA workspaces. The browser's API mutation guard observed no attempted mutations during the read-only walkthrough.
- No approval, finalization, runtime materialization, existing draft edits, installation, model swap, environment edit, commit or push. Only this report and new QA data/screenshots were deliberately saved. Docker Desktop and the existing dashboard were started; existing containers retain their normal migration/backfill/background lifecycle. This is not a before/after audit proving every background-managed row or vector stayed untouched.

## Saved evidence

| Case | Workspace | Run | Result |
| --- | --- | --- | --- |
| CyberRakshak | `qa-phase4-cyberrakshak-20261009-0a99014d` | `78872977-c8e5-491e-b5ca-6b88afa6ffc2` | Failed generation; no artifact or critique |
| Frostpeak | `qa-phase4-frostpeak-20261009-a9840523` | `3177ccf2-1564-496b-bcc3-d27be9716380` | Draft/critique saved; awaiting review; approval blocked |

- CyberRakshak document: `422995fb-215e-49d7-9a48-558b518a8130`, 17 indexed chunks. Evidence snapshot: `1e32aeee-64d8-4601-8bda-7b140c324a47`.
- Frostpeak document: `b80f6ed2-f7ad-43c1-a47c-8b8abb3a8f6f`, 4 indexed chunks. Artifact: `664b4b7c-1c65-4275-ba4d-e9a3a0de5851`.
- Group: `phase4-20261009-0c85b5ad`. Each new run's `model_config.qa_http_calls` stores sanitized response content/usage, and `qa_manual_assessment` stores semantic/browser outcomes. No credentials or private reasoning were saved in these records.

| Request | Case / node | Seconds | Outcome |
| --- | --- | ---: | --- |
| 1 | CyberRakshak plan | 14.643 | Valid, stop |
| 2 | CyberRakshak generate | 28.746 | Malformed JSON, stop |
| 3 | CyberRakshak JSON repair | 24.409 | Same parse failure, stop |
| 4 | Frostpeak plan | 6.256 | Valid, stop |
| 5 | Frostpeak generate | 34.611 | Valid structured draft, stop |
| 6 | Frostpeak critique | 4.449 | Valid critique, stop |

CyberRakshak route duration was approximately 68.4 seconds; Frostpeak approximately 46.0 seconds. No response was truncated and no transport retry occurred. One hosted JSON repair was attempted. No semantic revision was sent. Provider-reported total tokens: CyberRakshak 18,605; Frostpeak 17,524. Dollar cost is unavailable, not measured as zero.

## Confirmed acceptance failures

### P4-01 — High: source retrieval misses the needed passages

Evidence: CyberRakshak's planner repeats objective/integration vocabulary across section queries. The frozen snapshot contains seven chunks, but neither story-plan chunk 6 nor 7. Actual chunk `5359f4a6-48f0-4c22-8b1a-ac3d39a9cfc2` explicitly contains Level 5, Firewall Fortress, and its safe-route/malicious-path actions. A separate **read-only** query using the source terminology retrieved that chunk and the remaining level sequence immediately; it did not replace the saved evidence.

The raw quest instead cites PATCH and wrong-interaction chunks `4206c7ec-81aa-4fb0-8adc-5cf383084297` and `68857440-53dd-4a1c-8777-f15047195ccc`. They do not establish Level 5 mechanics. The raw levels section is empty. In Frostpeak, the premise chunk `3dfc5765-454b-4f0d-9327-f4ea0dfc2f5c` is present in the snapshot but not routed to `summary`; its summary citation is consequently removed. This is not missing source content.

Likely cause: objective-heavy planner queries plus top-three lexical retrieval do not guarantee section/explicit-entity coverage. `_ensure_level_coverage` checks already-retrieved evidence against the compacted payload, not the complete selected document.

Focused fix: reuse section-specific query construction and actual source headings/explicit named targets to retain the relevant passage before generation. Preserve workspace/document scope and citation filtering; do not fix this by accepting unrelated citations or increasing context indiscriminately.

Likely files: `backend/app/design_agent/nvidia_provider.py` (`plan`, `_ensure_level_coverage`), `contracts.py` (`build_section_queries`), `workflow.py:286` (`_retrieve_evidence`), and, only if needed, `services/rag_service.py:495` (`query_lore_sections`). Risk: medium; retrieval relevance/latency can regress.

Verify: replay both saved planner outputs against their QA source IDs with no inference; assert the Firewall Fortress passage is quest evidence, every required level survives compaction, and Frostpeak's premise is summary evidence. Keep foreign-workspace/document exclusion checks.

### P4-02 — High: structured generation and repair still fail

Evidence: requests 2 and 3 both report `finish_reason=stop`, but parsing fails at line 102, column 5, offset 6274 with a mismatched closer. `generate_blueprint` records `structured_output_invalid`; the create route returns 503 and saves no artifact. The repair repeats the same structural error; its bytes are not identical to the initial response.

Cause: malformed model output, not truncation or an unavailable key. Repair did not correct it. Existing validation correctly fails closed.

Focused fix: address output reliability using existing schema/compact-output mechanisms; assess existing guided-JSON support for the configured route before relying on it. Do not silently guess interior delimiters, accept partial artifacts or add another model.

Likely files: `backend/app/design_agent/nvidia_provider.py` (`generate`, `_complete`), `llm_provider.py:631` (`complete`), and existing structured-output tests. Risk: medium; schema controls must preserve design values and existing repair-integrity checks.

Verify: replay both saved malformed responses locally; they must remain rejected without a genuinely valid completion. A later separately authorized live check must yield a valid complete response without altering facts or emptying records.

### P4-03 — High: fresh dialogue request still produces copied examples

Evidence: the initial and repair responses contain all three supplied PATCH example lines verbatim. Fresh warnings delivered: **0/3**. The response even describes source-derived wording as new. Its warning/event pairings and fixed repeat/reset policy are present, but do not make copied text fresh.

Cause: source-example anchoring/instruction noncompliance. The explicit flag and prompt did not change this response. Because JSON parsing failed first, this run did not reach the saved-artifact fresh-dialogue gate.

Focused fix: separate quoted example dialogue from fresh-generation inputs while keeping the original source/provenance intact, and retain the existing source-reuse approval blocker. Do not mark copied lines acceptable merely by confirming proposals.

Likely files: `backend/app/design_agent/nvidia_provider.py` (generation payload), existing grounding/fresh-dialogue tests. Risk: medium; filtering examples must not erase character facts or falsify excerpt provenance.

Verify: local source-reuse gate tests must continue passing. Later authorized generation must produce three genuinely new, useful PATCH warnings with the three correct situations and the unchanged fixed policy. Semantic paraphrase review remains necessary.

### P4-04 — High: Frostpeak's valid draft is not integration-ready

Evidence in artifact `664b4b7c-1c65-4275-ba4d-e9a3a0de5851`:

- Quest objective checks are `guards_cleared == true AND flag_raised == false` and `flag_raised == true AND guards_cleared == false`. When both actions are recorded, **both checks are false**. No action order makes both objective checks succeed as written. An assumption saying final success requires both does not correct those notes.
- The requested greeting, progress reminder and completion line became a greeting and two **partial-progress** lines. The third line explicitly says guards still stand. There is no requested both-actions-complete dialogue.
- `quest_hooks.content.quests[0].reward` is null although the source explicitly supplies 100 gold and 250 XP. The assumption that these rewards are preserved “via runtime null” is false: an unbound runtime is not a reward record.
- All three lines are fresh relative to this source (22, 19 and 18 words); Eldrin's formal/lore-oriented profile is supported, and linking him to the quest is visibly labelled as a proposal. Those positive results do not cancel the failures.

Cause: model instruction noncompliance plus internal contradictions that field-shape validation cannot detect. Existing quality checks correctly disclose that they are structural, not playtest/semantic proof.

Focused fix: independent objective predicates, one explicit combined-completion transition, the missing completion situation/line, and source reward preservation. Reuse current generation/review contracts; do not build a general game-state engine for this correction.

Likely files: `backend/app/design_agent/nvidia_provider.py` (generation/review instructions), existing semantic-quality regressions and, only for deterministic enforceable invariants, `grounding.py`. Risk: medium; avoid imposing one game's ordering/reset policy on every GDD.

Verify: inspect the four-state truth table, both action orders, failure/restart proposals, and the actual completion line. Confirm `reward` contains the supported reward while `runtime` remains null; new words and unbound controls remain proposals. Requires a new authorized live response before claiming model compliance.

### P4-05 — High: independent critic misses the important defects

Evidence: Frostpeak's critic says the cited source does not specify clearing guards and raising the flag. The cited text explicitly states “Players must clear guards and raise the Northern flag.” It also treats clearly proposed failure notes as conflicting with confirmation requirements. It misses the mutually exclusive checks, absent completion dialogue and missing reward.

Cause: semantic review failure despite valid critique JSON and an independent request. The critic does return `needs_revision`; the system does not approve this draft.

Focused fix: focus the existing critic on source entailment, requested situations, reward preservation and objective-state counterexamples. Keep proposed implementation distinct from executed implementation. Do not equate a critic response or its numeric score with acceptance.

Likely files: `backend/app/design_agent/nvidia_provider.py:450` (`critique`) and existing evaluation/semantic-quality tests. Risk: medium; overfitting a rubric to one GDD would hide generalization failures.

Verify: review the saved draft and source without inference; the explicit source actions must not be labelled unsupported, and the three concrete defects must be identified. Later authorized live critique must demonstrate this behavior on more than one case.

### P4-06 — Medium: failed requests disappear from trace token totals

Evidence: CyberRakshak's dashboard trace reports 920 tokens (the planner), while its HTTP responses report 18,605 tokens. Failed generation/repair consumed 17,685 reported tokens but their node shows zero. Frostpeak's successful-node trace correctly totals 17,524.

Cause: `workflow.py:201` (`_fail_execution`) saves sanitized completion diagnostics but does not populate execution token columns from failed attempts. The frontend trace at `frontend/src/app/design-agent/page.tsx:1075` sums only those columns.

Focused fix: retain usage for failed provider attempts without double-counting combined truncation/retry diagnostics. Keep monetary cost explicitly unavailable when not supplied.

Likely files: `backend/app/design_agent/workflow.py`, possibly `llm_provider.py` if explicit aggregate failure usage is needed, and existing telemetry tests. Risk: low-to-medium; incorrect aggregation can overcount retries.

Verify: replay initial+repair failure diagnostics and assert the node/trace retain 17,685/18,605 tokens respectively; cover truncation and transport failures separately. No live inference is needed for this fix.

## Browser and safety verification

- **22 explicit browser checks passed**, with no page errors, failed requests or attempted API mutations in the completed checklist. This is not a full accessibility, performance or all-route audit.
- Both indexed sources and full-chunk disclosure work; source-scoped decision screens load. Each new source has three open decisions; none was invented/resolved to force acceptance.
- CyberRakshak correctly shows failed review, unavailable critique, visible error trace and no approval control.
- Frostpeak shows the saved NPC/quest content, critique and blocked approval. The scoped revision form can be opened and filled, but was **not submitted** because the inference budget is exhausted.
- Both review screens have no horizontal page overflow at 375, 768 and 1440 pixels, in light and dark modes. Keyboard activation of the Runtime tab works. Saved desktop screenshots were visually inspected; the long proposal sidebar makes Frostpeak's review lengthy, but no redesign was performed.
- For both runs, real backend technical-brief and runtime exports return 409. Neither unapproved run can export final content.
- Counts in each new workspace: zero game blueprints, NPC profiles, runtime quests, agent jobs and review events. Frostpeak has one mutable draft and one critique; CyberRakshak has neither. No run is completed/approved.
- The configured browser origin is `http://localhost:3000`. `http://127.0.0.1:3000` fails CORS with the current environment; settings were not changed to bypass it.
- The focused offline Phase 3 contract suite was rerun safely: **3 passed in 8.30s**, using `--noconftest -p no:cacheprovider`. No full-suite/build result is claimed for this turn, and no new tests or application code were added.
- `.env` SHA256 stayed `639E3F7AFAB903AA7F8323F6845C86E5977193C5430D91F9EC295461B88EF9EB`; `.env.example` stayed `19AB99C641BAF7A63419AF8FF82553420E79D24639470EB653E840CE6BEE1A0E`.
- Two transient QA-script issues were corrected without altering the app: the node-execution timestamp is `started_at`, not `created_at`; browser selectors needed the actual label/native summary and displayed status case. After the first script stopped, the continuation restored its persisted three-call ledger before using Frostpeak's remaining allowance. No generation request was repeated because of script errors.

## Ranked next work — no new feature phase

1. Fix **P4-01** first, replaying saved plans/source locally until named quest and broad section evidence are correct. This needs no NVIDIA calls.
2. Address **P4-02/P4-03** narrowly: one valid fresh dialogue/quest response, preserving provenance and fail-closed validation. Keep current models and interfaces; do not expand the product.
3. Correct **P4-04/P4-05** together: executable objective meaning, requested completion dialogue, supported rewards and a critic that catches real defects instead of disputing explicit source facts.
4. Fix **P4-06** with local diagnostic replays so the next live failure remains observable.
5. Only after those local gates, obtain a new bounded inference authorization and repeat this acceptance target in new QA workspaces. Add an independently authored, license-verified public GDD as a separate generalization check. A successful browser-submitted generation/revision and approved export remain unverified; approval/materialization require explicit scope authorization.

Read-only reproduction now: open `http://localhost:3000`, select either QA workspace above, inspect Sources → Decisions → Design Agent, then inspect the trace and Frostpeak NPC/Quest tabs. Do not submit a new run/revision or approve either draft. This reproduces a failed/blocked acceptance review, not a successful five-minute product demo. Unity remains out of scope.

## P4-01 implementation follow-up — 2026-10-09

**Source retrieval is fixed for the two saved-plan regressions. Overall Phase 4 acceptance remains failed; P4-02 through P4-06 are still open.** The original saved runs, evidence snapshots and drafts above remain historical failure evidence, not regenerated successes.

Changes are limited to the shared summary search in `backend/app/design_agent/contracts.py` and section-query batching/provenance in `backend/app/services/rag_service.py`. Planner queries are retained, with the existing section-specific search added in the same batch when different. Duplicate-section scores retain their maximum. Project/document filtering and provider payload limits are unchanged. No new retrieval framework, model, schema or UI was introduced.

Verification:

- Before the fix, both new saved-plan regressions and the extended batch/provenance test failed. They pass with the fix. Only two new test cases were added; existing batching and HNSW fallback tests were updated.
- Replayed both exact saved planner outputs against the real index in a database read-only transaction, without inference or saving results. CyberRakshak retrieved 14 unique chunks and compacted to the unchanged 10-item limit: its overview, PATCH companion passage, actual Firewall Fortress quest mechanics and all ten levels survive. Frostpeak retrieved/retained four chunks, including its correctly routed overview and quest reward evidence (100 gold, 250 XP).
- Cross-workspace document queries returned no evidence. Both saved runs' full model configurations remained unchanged, including their three-call ledgers.
- Focused offline regressions: **186 passed, 5 database-dependent tests deselected** using `--noconftest -p no:cacheprovider`; three existing isolated RAG/HNSW fallback tests also passed. This is **189 focused checks, not a full-suite result**. The separate earlier 50-test selection overlaps and is not added to this total.
- Scoped `git diff --check` passed. No NVIDIA requests, environment/model changes, runtime approvals or application-data writes were made for this fix. Both environment hashes above remained unchanged.

Risk/limits: known design sections can now contribute up to two searches each instead of one, increasing retrieval work and the candidate union; final provider evidence remains capped at the existing 10 items in this environment. This replay verifies source selection and boundaries, not fresh generation quality or generalization to every GDD. No fresh inference, full backend suite or new browser-submitted acceptance run was performed.

Next: address P4-02/P4-03 using saved malformed responses and source-reuse evidence first. The prior six-request NVIDIA budget is exhausted; any later live generation requires new bounded authorization. Unity and approval/materialization remain out of scope.

## P4-02/P4-03 implementation follow-up — 2026-10-09

**P4-02's saved syntax failure is locally recoverable; P4-03 has a generation-input mitigation, not proof of fresh/useful model output. Overall acceptance remains failed.** P4-04, P4-05 and P4-06 remain open. No saved QA run was regenerated or approved.

### Focused changes

- `backend/app/design_agent/llm_provider.py`: recognize only a mistyped `]` closing a section's content object immediately before its `citations` field. The root/section/content nesting must match, all sections and explicit section fields must exist, duplicate keys are rejected, and the complete result must validate. Strings, keys, values, arrays and citation values are not edited. Incomplete values, inner-array errors, extra prose and other ambiguous syntax retain the existing fail-closed/bounded-repair behavior. Recovery is marked in diagnostics and retains the existing recovered-output review blocker; it is not treated as clean generation.
- `backend/app/design_agent/nvidia_provider.py`: for an explicit fresh-dialogue flag, project quoted bullet lists under explicit example/sample dialogue headings into retained `content_segments` plus omitted-example offsets. Retained segments are exact source substrings with original chunk offsets, not a fabricated continuous excerpt. Companion roles, voice facts and implementation context remain available. Frozen evidence, grounding and critique retain the complete original quotations. Normal non-fresh generation is unchanged, and the existing freshness flag is carried into compact dialogue revisions.
- Existing regression files cover the observed delimiter pattern, rejection boundaries, true/false freshness behavior, CRLF/Unicode quotes and nonzero source offsets. Existing source-reuse checks still block copied lines when fresh dialogue is required. No model, environment, schema, database, dashboard or Unity changes were made.

### Evidence and verification

- Tests were written first: the observed delimiter pattern and fresh-generation projection failed before the application changes. The final focused offline selection passed **227 checks, with five database-dependent cases deselected**, using `--noconftest -p no:cacheprovider`. This is not a full-suite result, coverage measurement or generation-quality benchmark.
- Replayed both actual saved CyberRakshak responses through the normal generation adapter with an HTTP mock transport and repair disabled. The initial response required four delimiter replacements; the saved repair required three. Each used one mocked response, preserving canonical schema-normalized design content and citation values. Neither required another model request.
- Both recovered drafts remain blocked by `Recovered output` and `Fresh dialogue`, alongside their existing grounding/completeness/integration issues. Recovering the JSON does not make the copied dialogue or wrong quest evidence acceptable.
- Using the real indexed source and saved planner queries, the fresh-generation projection omitted five explicit PATCH example spans. None of the three copied target warning fragments remained in the generation evidence. Every retained segment matched its original chunk substring at the recorded offsets.
- Database access used `SET TRANSACTION READ ONLY`. The saved run's complete model configuration/call ledger and frozen snapshot were unchanged after replay. **Live NVIDIA requests: zero.** `.env` and `.env.example` hashes remain those recorded above. Scoped `git diff --check` passed.
- Two transient replay assertions were corrected: the saved repair has three mismatches, not four; preservation comparisons must use the existing schema-normalized representation because validation derives/defaults fields. The final replay completed for both records. An existing Chroma telemetry compatibility warning appeared during retrieval; retrieval and all replay assertions completed, and no dependency change was attempted.

### Limits and next step

Recovery intentionally does not handle arbitrary malformed JSON. Example filtering recognizes explicit quoted-list formats, not every inline quotation or a block whose heading was cut out of an excerpt. Previous dialogue remains visible when revising an existing draft; copied/paraphrased lines still need the original-source gate and semantic review. The projection adds offset metadata overhead while keeping the existing source selection and item/character limits.

No fresh inference, browser-submitted generation, full backend suite or approved export was performed. A future bounded live check must demonstrate genuinely new, correctly paired dialogue—not merely valid JSON. First address **P4-04/P4-05** locally using Frostpeak's saved objective checks, missing completion line/reward and inaccurate critique; keep model settings unchanged. The prior NVIDIA allowance remains exhausted.

## P4-04/P4-05 local hardening — 2026-10-09

**The observed quest-check contradiction now has a deterministic blocker, and independent critique receives the human request. Fresh generation/critic compliance remains unverified; P4-04/P4-05 are not closed as live acceptance findings.** The historical Frostpeak draft still has a null reward, missing completion line and inaccurate saved critique.

Changes:

- `backend/app/design_agent/grounding.py`: recognize the specific mirrored required-objective pattern in explicit Objective/Event/State/Check notes. Both notes set their own quest flag true but require the other's flag false. The scorecard exposes the counterexample where both flags are true, fails contradiction/integration checks and supplements critique with a high-severity finding. Proposal confirmation cannot clear it. This does not evaluate arbitrary expressions, infer flags from prose or rewrite a quest.
- `backend/app/design_agent/workflow.py`, `provider.py`, `nvidia_provider.py`: pass an optional `review_request` through the existing provider boundary, containing the original objective, latest rejection reason, freshness flag and repeat policy. Previously the critic had no original objective against which to check missing requested dialogue. Mock/fallback providers and existing test-provider overrides accept the same internal keyword; no public API or database schema changed.
- Generation/revision instructions require independently recorded completed actions, requested combined-completion dialogue and source rewards in `quest.reward` even with `runtime: null`. Critique instructions compare request coverage, inspect the complete cited objective passage, test the four boolean states/both action orders, and distinguish actual contradictions from unconfirmed proposals. Existing independent findings are preserved, not silently removed as false positives.

Verification:

- Regression-first tests failed for the missing contradiction blocker/request context and reward/completion instructions, then passed after implementation. The final safe offline selection completed **232 passed, 5 database-dependent tests deselected in 6.93s**, using `--noconftest -p no:cacheprovider`; not a full-suite or coverage result. An intermediate narrower selection accidentally included a database-fixture test with conftest disabled and produced a missing-fixture error; the final selection explicitly excludes all five such cases. No test database was initialized.
- The saved bad checks produce `[false,false]`, `[true,false]`, `[false,true]`, `[false,false]` across the four guard/flag states. The manually authored independent-check correction passes both action orders and preserves `100 gold and 250 XP` with runtime null. This fixture is reference logic, not AI-generation evidence. Nonmatching stage-transition prose is not classified as this explicit flag contradiction.
- Read-only replay of actual Frostpeak run `3177ccf2-1564-496b-bcc3-d27be9716380` confirmed the contradiction blocker survives confirmation of every proposal. The shared approval gate rejects the equivalent regression even when a critic claims readiness.
- Replaying the saved critic with an HTTP mock yielded its original findings plus the deterministic high-severity counterexample. The captured request contained the original human objective and scoped source text explicitly specifying both actions and `Reward: 100 gold and 250 XP.` The supplemental review is idempotent.
- The replay used `SET TRANSACTION READ ONLY`; run configuration/call ledger, artifact, critique and frozen snapshot remained unchanged. **Live NVIDIA calls: zero.** Environment hashes remain unchanged, and scoped `git diff --check` passed. No approval, export, UI work, model change, install, commit or push was performed.

Limits/risk: the new check recognizes a narrow explicit notation, not arbitrary quest semantics or engine execution. Other predicates, missing requested situations, reward omissions and source entailment still require independent/human review. The stronger prompt and supplied request do not prove a hosted critic will stop making false claims. Stored historical scorecards are not refreshed automatically, although approval rechecks current logic. Five database-dependent tests, a browser walkthrough and fresh generation remain unrun.

Next: fix **P4-06** failed-request token accounting using saved diagnostics. Then seek a new bounded inference allowance for fresh end-to-end generation/critique acceptance; the previous allowance is exhausted. Unity and runtime approval remain out of scope.

## P4-06 failed-request token accounting — 2026-10-11

**Local accounting is fixed and regression-tested. Overall live acceptance remains failed; historical records have not been backfilled.**

Changes:

- `backend/app/design_agent/workflow.py`: failed executions retain nonnegative integer usage reported by completed provider responses, including failed JSON repairs. Disjoint diagnostic entries are summed; already combined retry usage is counted once. If generation succeeds but subsequent grounding/persistence fails, the returned provider usage and model are retained. Failure status and approval behavior are unchanged.
- `backend/app/design_agent/llm_provider.py`: when a truncated response is followed by a failed retry, preserve the first response's reported usage and request-attempt count in the sanitized error diagnostics. No additional retries or model requests were introduced.
- Usage is explicitly scoped to completed responses. Missing usage stays unavailable rather than becoming an estimate of billable tokens. Failure cost remains unavailable unless a successful provider result already supplies it.

Verification:

- Regression-first tests reproduced missing accounting before implementation. The final safe offline selection completed **253 passed, 5 database-dependent cases deselected in 9.39s**, using `--noconftest -p no:cacheprovider`. This includes existing provider tests and ten new parameterized/validation cases; it is not a full backend-suite or coverage result. The narrower provider/diagnostics selection passed 31 tests and overlaps this total.
- Covered invalid repairs, both truncated responses, successful truncation retries with invalid output, timeouts before/after completed responses, repair truncation/timeouts, equal usage on distinct requests, and post-generation validation failures. Tests use mock transports and mock database sessions, not live inference or database writes.
- Read-only replay of saved CyberRakshak run `78872977-c8e5-491e-b5ca-6b88afa6ffc2` on detached in-memory copies recovered **11,823 input + 5,862 output = 17,685 tokens** for the failed generation node. The real trace serializer then totaled **18,605 tokens**, including the planner. The saved failed node still has zero tokens: this replay did not change its historical dashboard trace.
- Database reads used `SET TRANSACTION READ ONLY`; saved rows and the run configuration/request ledger were compared afterward and remained unchanged. **Live NVIDIA requests: zero.** `.env` and `.env.example` hashes are unchanged. Scoped `git diff --check` passed. No install, model/environment change, approval, commit or push occurred.

Limits: a timed-out request may have consumed provider resources without returning usage; those unknown tokens cannot be reconstructed. No historical backfill, browser verification, fresh generation or full-suite run was performed.

Next: obtain a new bounded NVIDIA allowance, then repeat isolated end-to-end generation/critique acceptance for useful, fresh CyberRakshak dialogue and correct Frostpeak quest completion/reward handling. Count retries and repairs within that allowance. No runtime approval or Unity work until dashboard acceptance is demonstrated.

## Fresh acceptance and bounded critic hardening — 2026-10-11

**Acceptance still fails. Local syntax recovery and request visibility are improved; fresh dialogue coverage and critic judgment are not proven fixed.**

### Authorized live check

The user explicitly authorized a new six-request allowance. All six were used, with a hard three-request cap per GDD. Normal retry/repair attempts counted toward the cap. The actual FastAPI routes, PostgreSQL, Chroma and LangGraph ran through an in-process TestClient with only the counting provider transport injected; this was not browser-submitted inference. Existing configured models and token limits were unchanged.

| Case | New isolated workspace | Run | Outcome |
| --- | --- | --- | --- |
| CyberRakshak | `qa-phase4-cyberrakshak-20261011-2e348428` | `c0380866-666c-4471-af1b-0c033f741b29` | Three planning ReadTimeouts, about 90 seconds each; no generation or critique |
| Frostpeak (bundled synthetic sample) | `qa-phase4-frostpeak-20261011-638a9c51` | `a43e8190-3e49-42b7-9a08-98263bfbe067` | Planning 46.199s, generation 13.716s, critique 5.360s; draft saved, critique invalid, run failed |

Group: `phase4-20261011-814988fa`. New Frostpeak artifact: `d64d1a72-1c53-4680-938e-9a478ec7454a`; frozen snapshot: `356b0966-fefe-4abf-98f7-3bd54066b61c`. Sanitized completion responses and detailed manual findings are saved in each new run's `qa_http_calls` and `qa_manual_assessment`. Reconstructed source text matched the historical content fingerprints; uploads indexed 17 CyberRakshak chunks and 4 Frostpeak chunks. Historical QA run/node/artifact/critique/snapshot records were compared and remained unchanged during the exercise.

Frostpeak positives: one source-named Eldrin profile, one Ash Pass quest, valid complete generation without repair, source reward `100 gold and 250 XP`, runtime null, independently recorded objective checks, and no exact source reuse in its three spoken lines. These do not establish semantic freshness, game execution or acceptance.

Confirmed defects:

- `QA-11-01` (High): requested Ash Pass progress and both-actions-complete dialogue became a generic progress line and unrelated idle lore. A greeting and three well-shaped mappings do not prove request coverage.
- `QA-11-02` (Medium): the idle mapping invents an `every 30 seconds` repeat timer despite the request prohibiting invented timers.
- `QA-11-03` (Medium): failure/reset notes exist, but a concrete restart Event/State/Check is absent. Final combined success is only runtime-preview prose with flag names different from the objective notes.
- `QA-11-04` (High): the critic emits a complete critique object followed by an extra outer `}`. Full JSON parsing fails at line 25, column 1, offset 3023. Its attempted repair was stopped before sending by the exhausted allowance.
- `QA-11-05` (High): the raw critic disputes the reward directly stated in Hook 1 and treats labelled encounter/animation proposals as unsupported facts. It misses the incorrect requested situations, timer and restart gap. Its original findings have not been silently removed or accepted as correct.

The real running backend returned healthy status. Live reads of both new runs/traces succeeded; cross-workspace reads returned 404 and both unapproved exports returned 409. Missing consent was rejected before inference. Both QA workspaces have zero approved blueprints, runtime NPCs/quests, agent jobs and review events. Frostpeak has no saved critique. Its trace correctly retains **16,705 reported tokens**, including **7,539** from failed critique. CyberRakshak timeout usage/cost is unknown, not demonstrated to be zero. The frontend at `localhost:3000` refused connection; no browser acceptance claim is made.

### Local follow-up, with no further inference

- `llm_provider.py`: recover only one extra trailing outer brace after a complete bare critique object, with `finish_reason=stop`, no truncation retry, unique keys, every explicit critique/finding field, bounded complete nesting and successful schema validation. No field, finding, string or source fact is rewritten. Missing fields, duplicate keys, extra fields/objects/closers, prefixed prose and truncated responses are not recovered by this rule. Existing bounded failure/repair handling remains available.
- `nvidia_provider.py`: place unchanged human requirements before task/schema text in generation and critique; revisions highlight their rejection reason. Critique explicitly prioritizes requested situations, prohibited timers and restart transitions. Do not classify arbitrary natural-language requests with heuristic approval gates.
- Critic input is an in-memory projection that removes only exactly reproduced server-derived hooks, manual tests and trigger-mapping notes. Distinct tests/notes, assumptions, mappings, citations, quest instructions and source evidence remain. No saved artifact is shortened or rewritten.
- A recovered critique adds an explicit high-severity review failure and remains `needs_revision`. Existing API/worker approval gates reject it even if every proposal is confirmed. All original independent findings remain visible; syntax recovery is not semantic validation.

Verification: regression-first checks reproduced the recovery, approval and prompt/projection gaps. An initial truncation-boundary assertion expected the wrong error subtype; it was corrected to the existing truncation error without changing retry behavior. The focused files passed **44 tests**; the broader safe offline selection passed **264 tests, 5 database-dependent cases deselected in 7.63s**, using `--noconftest -p no:cacheprovider`. The selections overlap; these are not full-suite, coverage or hosted-generation results.

Read-only replay of the actual saved Frostpeak critic used one mock response, no repair and **zero NVIDIA requests**. It preserved all three original model findings, retained 7,539 reported tokens and added one approval blocker. Critic artifact JSON shrank from **11,348 to 8,215 bytes (27.6%)** by removing exact duplicates only; this is not a measured reduction in end-to-end latency or total prompt tokens. Quest notes and compacted source evidence were unchanged. The saved run, artifact and snapshot were rechecked and remained unchanged after replay.

`.env` and `.env.example` hashes remain unchanged. No model changes, installs, runtime approvals, commits or pushes were made. No new inference allowance remains. Next: improve request-level semantic acceptance against these saved cases before any further hosted acceptance run; the clearer prompts alone are not proof that missing dialogue, restart rules or critic false positives are solved. Keep Unity out of scope.

## Explicit-request approval hardening — 2026-10-11

The subsequent `resolve` request authorized local fixes, not another hosted allowance. This change closes identifiable request-coverage bypasses; it does **not** establish fresh generation acceptance or solve arbitrary critic semantics.

Changes:

- `grounding.py` adds bounded checks against the original human objective, never against instructions found in GDD evidence. Recognized English requests for greeting, quest-in-progress reminders and completion require identifiable proposed situations. Idle lore and a return after an unspecified task no longer cover those requests. These are presence/label checks, not proof that a line has the correct meaning, voice or quest association.
- Explicit timer prohibitions check numeric intervals in repeat policies. A ban on extra/new timers permits an interval literally present in that NPC's cited evidence; an absolute ban does not. Negated intervals are not active repeat rules. A literal source match is not semantic entailment; other spellings, units and free-form constraints still need review.
- Explicit failure/restart Event/State/Check requests require separately headed, nonempty notes. An explicitly requested final success from both/all actions requires a Completion/Event/State/Check note. Where objective notes explicitly assign boolean flags, the completion check must AND the same identifiers; OR and renamed flags are rejected. No expression is executed and no arbitrary state machine is validated.
- Request gaps appear as high findings and a `Request coverage` blocker. Proposal confirmation cannot satisfy them. NVIDIA critique receives those gaps and retains every independent finding; a false or recovered critic is never silently rewritten into approval evidence.
- API inline/queued approval, worker human review and finalization recompute against the persisted human objective. Checkpoint objective text cannot weaken that final gate. The existing local/mock-provider quality-review conditions were not broadened.
- Generation/revision prompts document the expected situation and transition-note conventions. No public API fields, database tables, dependencies, model selection or environment values changed.

Verification:

- The safe offline selection passed **276 tests, 5 database-dependent cases deselected in 8.24s**, with `--noconftest -p no:cacheprovider`. This adds twelve cases to the earlier 264-case selection, covering request gaps, a clearly labelled hand-written reference, exclusions, preserved critic findings, cited/absolute timer constraints, four approval boundaries and combined flag checks. This is not a full-suite or measured-coverage result. An initial new-test collection error used pytest's reserved parameter name; a worker-test stub also initially omitted keyword arguments. Both test-harness mistakes were corrected.
- The actual saved Frostpeak draft and invalid critic were replayed through one **mock** HTTP response under `SET TRANSACTION READ ONLY`, with **zero NVIDIA requests** and repair disabled. All three original critic findings remained intact. The returned nine findings comprise those three, the recovery blocker and five request gaps: progress dialogue, completion dialogue, timer, restart transition and combined-success transition.
- Both the recovered critic and a deliberately false `ready_for_review` critic could not approve the saved draft, even with all proposals confirmed. An in-memory, hand-written reference with corrected situations, explicit reset policy and matching Restart/Completion checks had no request-coverage gaps. It was not saved, generated by NVIDIA, approved or executed in a game.
- Run, artifact and snapshot column hashes remained unchanged after replay. `.env` and `.env.example` hashes still match the preceding section. Scoped `git diff --check` passed apart from existing line-ending warnings. Frontend code was not changed or browser-revalidated.

Remaining acceptance gate: a newly authorized, bounded hosted run must actually produce useful requested lines and a clean evidence-faithful critique. The saved critic's reward/proposal false positives remain historical failures, not proven model fixes. Unknown natural-language requirements and creative quality still require independent/human review. Do not move to Unity or call this phase accepted on the strength of these guards alone.

### Four-request Frostpeak QA and focused local follow-up — 2026-10-11

The later, explicitly authorized four-request check used a new isolated workspace, `qa-frostpeak-four-20261011-4321aefe`, and run `aba6ce88-c734-4eb2-8ddf-fe69771dc68a`. It used the bundled synthetic Frostpeak sample, not a publicly sourced real GDD. Its request allowance is exhausted.

Hosted result before this follow-up:

- Requests 1–2 exercised normal in-process API/workflow planning and generation. Generation returned three duplicate `player_approaches` mappings and was correctly rejected; the run remains **failed**, with no saved design artifacts or runtime approval. This was not browser-submitted inference.
- Request 3 was a QA-guided direct-provider regeneration against the same frozen evidence and original human objective, not a successful normal-flow resume. It produced distinct, usable draft lines and preserved the source reward, but completion was bound only to raising the flag after clearing guards. Flag-first then guards could satisfy both flags without triggering completion. Restart cleared the flags without specifying quest-state reactivation.
- Request 4 returned valid critique JSON. Its three original findings incorrectly or ambiguously challenged character/quest mappings already labelled as proposals; it missed the transition problems. The local matcher also falsely claimed the existing `ash_pass_complete` dialogue was missing. No JSON repair occurred. Four requests consumed 27,180 reported tokens; measured provider-call time totalled 50.827 seconds. Cost was unavailable.

Focused local changes following `next`:

- Recognize a multiword quest-scoped completion trigger such as `ash_pass_complete` when its scope occurs in both a candidate quest and the human request. Unrelated, negated and progress labels remain negative controls. This is label coverage, not proof of the spoken line's meaning.
- For explicitly requested combined-success notes with multiple recognized boolean objective flags, require the Event to declare coverage of either/each required action or objective, rather than relying only on the AND predicate. The declared convention does not execute event bindings. Deliberately ordered designs still need separate ordering review.
- For explicitly requested restart notes, require an explicit `quest_state` (or `quest`) active assignment and a same-key active predicate. A flag reset, different-variable predicate, negated activation or optional OR check is insufficient. This bounded convention can require clarification of other lifecycle vocabulary; it is not a general state-machine interpreter or proof that all reset effects are correct.
- Generation/revision and critique prompts explain these integration expectations. No schema, database, frontend, environment or model-selection changes were made in this follow-up. Independent critic findings are preserved, never automatically discarded to obtain approval.

Verification:

- The new regressions first reproduced the false completion warning and missed transition checks. A later test fixture initially omitted the required critique `summary`; the fixture was corrected without weakening validation.
- The same safe offline selection used above passed **286 tests, 5 database-dependent cases deselected in 8.15s**, using `--noconftest -p no:cacheprovider`. Ten additional cases cover the observed excerpts, negative labels, approval blocking, preserved findings, restart predicates and a clearly hand-written transition reference. This is not a full-suite, measured-coverage, browser or Unity result.
- The actual saved candidate and raw independent critique were replayed under `SET TRANSACTION READ ONLY`, with **zero new NVIDIA requests**. The false missing-dialogue gap disappeared; `completion_event` and `restart_reactivation` remained. All three original independent findings were retained in the recomputed five-finding critique. A deliberately false ready verdict still could not approve the original candidate with all proposals confirmed.
- An in-memory, hand-written correction of only the Restart and Completion notes had no request-coverage gaps. It was not fresh model output, saved, approved or executed in a game. The declared reference was walked through in both action orders; this does not validate an actual engine implementation.
- The saved run's status/configuration and frozen evidence snapshot remained unchanged. Configuration SHA-256 stayed `0acbd1fa985c5cbd764fa67ab83f441a30b0971ed415a8f057c34692dcee35d8`; `.env` and `.env.example` hashes matched the preceding baseline. Scoped whitespace checks passed, apart from existing Git line-ending notices.

Acceptance is still open: initial fresh generation failed the normal workflow, the guided retry was not a successful API resume, and independent critique remains semantically unreliable about labelled proposals. These local guards do not establish reliable fresh generation or production readiness. Do not change models, expand features or move to Unity to bypass these failures. The next acceptance run requires fresh, explicit hosted-request authorization and must exercise the normal generation/review workflow, not promote the hand-written reference into success evidence.

### Critic field semantics clarification — 2026-10-11

Inspection found that the saved critic acknowledged existing proposal labels; missing assumptions were not established as the cause of its false positives. Reconstructing the input through the current normal critic adapter showed all eleven pending assumptions, the NPC and quest association disclaimers, and `runtime: null`. This reconstruction is not the exact historical request prompt, which was not saved in the sanitized request records.

The focused change adds fixed application-owned `review_context.field_contracts` for dialogue mappings, quest dialogue hooks, assumptions and source claims. Quest dialogue hooks are spoken-line drafts, not a quest-giver assignment; mappings are unapproved proposals, not active bindings. Actual names, traits, mechanics, rewards and explicit quest-giver assertions still need source checking. The instruction now asks the critic to identify the exact assertion and read existing assumptions before alleging missing labels. No artifact rewriting, finding filtering, automatic approval, schema changes or model changes were introduced.

Verification:

- Two new input/preservation cases first failed because the field contracts were absent. They now cover the observed quest-giver inference and retention of a substantive reward-contradiction finding. These are mocked contract tests, not semantic evaluation of a live model.
- The same safe offline selection passed **288 tests, 5 database-dependent cases deselected in 7.82s**. This is not a full-suite or coverage result.
- One mock completion replayed the actual saved independent critique under `SET TRANSACTION READ ONLY`. All three original findings remained verbatim; the two local transition findings remained, giving five findings and `needs_revision`. The projected quest, NPC assumptions, saved run/configuration and frozen evidence snapshot were unchanged. No NVIDIA request was made. Environment hashes remained at the preceding baseline; scoped tracked-file whitespace checks passed with the existing line-ending notice.

This improves the critic's input contract; it does **not** prove that its proposal-label false positives are fixed. Do not add automatic semantic filtering to make the historical critic pass. The next meaningful verification is a newly authorized, hard-capped normal workflow run in a new isolated QA workspace, retaining all failures and without runtime approval. The preceding hosted allowance remains exhausted.
