# Live Gemini draft-quality advisories

Execution date: **2026-10-29** (including the Pacific quota date). The filename retains the date requested for this report. `<QA_DIR>` is the author's local, unpublished QA evidence folder; screenshots and exported content are not committed.

## Verdict and scope

**PASS for the narrow non-blocking-advisory → approval/export → documented-integrity-policy check, on one real Gemini draft.** One correct objective-copy advisory remained visible while ordinary proposal confirmations enabled approval. The browser approved once, exported the brief without advisory records, and reloaded the completed state. The verifier's first recorded live application invocation returned **EQUAL_EXCEPT_DOCUMENTED_METADATA**, not strict byte equality.

**Not a content-quality or full-MVP acceptance.** The clean model critique missed the copied dialogue and unsupported assumptions. Only objective-copy had a live positive example; quest-label mismatch and warning-in-rules had no applicable positive examples in this draft. IDs and compared values are persisted/API-visible but **not displayed in the advisory panel**. That UI limitation remains unfixed.

One of the two permitted attempts was used. Attempt 2 was unnecessary because the first run cleared the critic gate and completed. No rejection, revision, finding-resolution write, manual workflow retry, runtime export/materialization or Unity action occurred. All browser mutations targeted the new workspace; B3, B4b and earlier QA runs were not modified.

## Setup, launch and migration

- Branch: `feature/quality-advisories`; running source: **`2eb1880bbbb02fc24e7c86fddb0de1e017830429`**. Working tree initially contained only untracked `docs/audit/`.
- Existing `gamemind_backend` used cached `gamemind-revise-tests:local`, backend source bind-mounted at `/app`, restart policy **no**. Mounted and checkout workflow SHA-256 both equalled `c29ad2f1a5366ead862564351d7488e935ea388da4c6e278ba826a1255caabf9`.
- Effective backend settings: `LLM_PROFILE=dev`, `GEMINI_DEV_MODEL=gemini-3.5-flash-lite`, `GEMINI_TIMEOUT_SECONDS=180`, `PYTHONPATH=/app`, `DESIGN_AGENT_FALLBACK_TO_MOCK=true`, `DESIGN_AGENT_FALLBACK_DISABLED_NODES=["revise"]`, execution mode `inline`, per-run request cap **12**. Production retries were not overridden.
- Before startup, ran `python -B gemini_usage.py` in a one-off SDK container attached to the application network, with the same process configuration. This CLI reads PostgreSQL without calling Google. Flash-Lite: **0 used / 500 remaining**, limits **5 RPM / 500 RPD**; Flash: **0 used / 20 remaining**, limits **3 RPM / 20 RPD**. The required remaining-budget threshold of 20 passed.
- Started the existing backend with `docker start gamemind_backend`. Its normal command is `alembic upgrade head && exec uvicorn main:app --host 0.0.0.0 --port 8000 --reload`. Both `alembic current` and `alembic heads` reported **`f4a6b8c0d123`**; **no pending migration or upgrade step** was applied. Health and readiness returned healthy, effective provider `gemini`, lexical retrieval. Restart count remained **0**.
- Startup model verification made **one GET**, HTTP 200, counted against Flash-Lite: **0 → 1**. Known Chroma telemetry signature noise was non-fatal; startup completed normally.
- Frontend: `npm run dev` with process-only telemetry disabled and npm offline, serving `http://localhost:3000`. No code, `.env`, dependencies or provider settings were changed.
- Real installed Playwright Chromium **149.0.7827.55** was driven through Playwright over a loopback CDP connection, using a fresh QA-only browser context/profile. **No request interception, fixtures or response substitution.** The browser bridge timed out, and sandbox process/loopback restrictions initially prevented direct control. Moving Chromium, its driver and the frontend outside that restriction established live access. One early navigation timeout and two incorrect-selector waits were driver/setup errors, not workflow failures; no design-start or approval request was repeated.

QA root: `<QA_DIR>/quality-advisories-live-20261029-01/`. Root evidence includes `browser-evidence.json`, `backend.log` (stdout), `backend-stderr.log` (timestamped provider logs) and `usage-after.json`. CLI starting/post-startup counts above were recorded from actual command output, not separate saved CLI-output files.

## Attempt 1 — browser setup and generation

| Item | Recorded identity/value |
| --- | --- |
| Workspace | `quality-advisories-frostpeak-dev-20261029-attempt-1` |
| Source | `01116964-ee8e-49f6-ad12-e6889b349d9f`, bundled Frostpeak GDD, four indexed chunks |
| Resolved decision | `274e2bc0-de7b-4232-85d5-21de43cea2bb` |
| Decision text | `unity_runtime_preview.content.target_platform must be "Windows PC".` |
| Run | `253552bb-00ea-4cfd-a56e-e28662018f84` |
| Reviewed draft | `f179e6d1-bfc3-4ee7-a547-08e4ad7846dc`, version 1 |
| Frozen evidence snapshot | `36a38426-f88a-4dd1-81cb-f4e0891d23b2` |

Through the browser: created a new project, loaded **only** Frostpeak, opened its local review, saved and resolved Platform and controls, reopened governed review, disabled runtime deferral and enabled explicit unspecified-memory scope. The decisions-page start request omitted `max_revisions`; its normal API default produced **2**, verified in the response/database. `defer_runtime=false` kept runtime preview enabled; it contained `target_platform="Windows PC"`.

The consent dialog actually displayed:

> Add a cited AI review to this GDD?
>
> GameMind will use the configured AI provider to review selected source evidence, prepare a cited draft, and run an independent critique. Your local source review and decisions stay available either way.

It also displayed the fixed runtime/memory scope explanations. Clicking **Start governed review once** submitted `hosted_provider_consent=true` through the ordinary UI/API. This decisions-page dialog did **not** name Google/Gemini or explicitly describe third-party transfer/data use; no second provider-specific consent dialog was shown on this route. This is recorded as a UX limitation, not silently substituted with wording from another page.

| Browser mutation | HTTP status |
| --- | ---: |
| POST `/api/v1/projects/` | 201 |
| POST `/api/v1/documents/demo/frostpeak` | 201 |
| POST `/api/v1/decisions/sync`, twice for the two local-review openings | 200 each |
| PUT decision text; PUT mark resolved | 200 each |
| POST `/api/v1/design-agent/runs`, once | 201 |
| POST this run's `/review`, approve once | 200 |

The run reached **awaiting_review**, revision **0/2**, not degraded. The Summary was the exact cited Section 1 premise, not the art paragraph. The adapter marks that Summary as locally extracted; this does not mean generation fell back to mock.

### Actual providers, latency and counted attempts

Timestamped transport logs show HTTP **200** for the one startup verification GET and all **three inference POSTs**. No node was served by mock. All hosted trace entries say `degraded=false`, `request_attempts=1`, `retry_count=0`, `repair_attempts=0`, `truncation_retries=0`, `independent_review_retries=0`. No corrective re-ask fired.

| Node | Actual provider/model | Degraded | Latency | Input/output tokens | Google attempts / ledger position |
| --- | --- | --- | ---: | ---: | --- |
| Plan | Gemini / `gemini-3.5-flash-lite` | false | 3,573 ms | 373 / 170 | 1; 1 → 2 |
| Retrieve | local retrieval / `chroma-local-lexical-v1` | not a hosted fallback | 252 ms | 0 / 0 | 0; stays 2 |
| Generate | Gemini / `gemini-3.5-flash-lite` | false | 7,940 ms | 3,369 / 2,173 | 1; 2 → 3 |
| Critique | Gemini / `gemini-3.5-flash-lite` | false | 3,350 ms | 6,041 / 198 | 1; 3 → 4 |
| Human review, resumed approval | local | no fallback | 40 ms | 0 / 0 | 0 |
| Finalize | local | no fallback | 64 ms | 0 / 0 | 0 |

Plan/retrieval/generation/critique recorded **15,115 ms combined node latency**; this is not a separately timed browser end-to-end measurement. Reported inference tokens total **9,783 input + 2,541 output = 12,324**; cost is unavailable, not measured zero. Full wire schema sizes in logs: plan **2,364**, generation **20,525**, critique **14,310 bytes**. No revision schema was sent.

Intermediate ledger positions are reconstructed from ordered transport calls and node attempt counts, not separate CLI invocations between nodes. CLI readings were **1 after startup**, **4 after generation/critique**, and **4 after approval/export**. They reconcile exactly.

## Review, advisories and approval state

Critique: **`ready_for_review`**, **findings `[]`**. Thus there are no finding IDs, severities, paths or evidence indexes to enumerate. Coverage: `covered` for all eight assessed sections, `not_specified` for NPC memory. The critic asserted that platform and inputs were specified and no conflicts/missing implementation existed; that assertion is too strong for this content.

The current system scorecard showed grounding **1**, completeness **1**, consistency **1**, integration readiness **0**, overall **0.75**, `passed=false`, **Integration readiness only** as blocker, with **16 unconfirmed proposals**. Read-only finding policy returned `critique_blocked=false`.

### Exactly what the advisory panel displayed

```text
Advisories (non-blocking)

Exact local checks only. These do not affect approval and never change the draft.

medium · objective text copied as dialogue

Dialogue exactly repeats an objective after text normalization. Review whether this is useful spoken dialogue.

/quest_hooks/content/quests/1/dialogue_hooks/0
/quest_hooks/content/quests/1/objective
```

**ID and compared values were not rendered.** They were available in the ordinary run response and persisted snapshot, not secretly present in the visible panel:

```json
{
  "id": "68b345478b3b18ea2393f313a00803b3617eac5b16a22ff385d244d4c2b61060",
  "check": "objective_text_copied_as_dialogue",
  "severity": "medium",
  "paths": [
    "/quest_hooks/content/quests/1/dialogue_hooks/0",
    "/quest_hooks/content/quests/1/objective"
  ],
  "values": {
    "dialogue": "Mine 5 chunks of raw sky-iron ore from the cliffside veins.",
    "objectives": [{
      "path": "/quest_hooks/content/quests/1/objective",
      "value": "Mine 5 chunks of raw sky-iron ore from the cliffside veins."
    }]
  }
}
```

### True positives, false positives and omissions

- **One true positive:** Quest 2's entire hook equals its objective verbatim. It is an objective instruction, not useful character dialogue. This advisory is accurate even though the model critic returned no findings.
- **Zero false positives among the one emitted advisory.** This single example does not establish general precision or reliability.
- **No missed applicable exact-match case found.** NPC situations contain no exact `Quest <digits>` labels, so quest-label checking correctly abstains. Their topic/eligibility associations are Ash Pass → `quest_1`, ore → `quest_2`. Memory `rules=[]`; metadata warnings are correctly in `warnings`, so warning-in-rules correctly emits nothing.
- **One broader semantic false negative / deliberate exact-rule limitation:** Quest 1's hook, `Clear guards and raise the Northern flag.`, combines its two objectives. It equals neither the complete objective (`Reclaim the Ash Pass border post. Players must clear guards and raise the Northern flag.`) nor either single objective (`Clear guards`, `Raise the Northern flag`). It is still poor dialogue, but the requested exact matcher deliberately misses it. This is not a failed implementation of the specified rule, and no fuzzy rule was added.

### Non-blocking behavior, actually exercised

Initially the disabled control read **Approval blocked**. With current critique/system policy and zero proposal selections, the real frontend derivation returned:

```text
needsRevision=false, confirmationReady=false, approvalBlocked=true
```

Executed the current `deriveReviewGate` offline on the captured live inputs, once with the advisory payload and once with only that payload removed from an in-memory copy. Results matched. No live data was edited for this comparison.

Reviewed and checked the **16 proposal checkboxes** through the browser. The button became **Approve run**, enabled, while the medium advisory remained displayed. Both derivations then returned:

```text
needsRevision=false, confirmationReady=true, approvalBlocked=false
```

The advisory region had **zero buttons** and no review controls. No degraded acknowledgement appeared; no fallback node existed. Approval submitted the current artifact ID and sixteen exact confirmations, `acknowledge_degraded=false`, once, and returned **200/completed**. This was a bounded QA approval with known content weaknesses, not a declaration that all assertions were source-supported or implementation-ready.

## Export and real-data integrity verification

Clicked **Download technical brief** through the dashboard. The governed final-artifact brief endpoint returned a real download, `gamemind-agent-brief.md`, **23,977 UTF-8 bytes**, saved at `<QA_DIR>/quality-advisories-live-20261029-01/attempt-1/technical-brief.md`.

The brief contains approved status, `planning_only` runtime readiness, project/run/final artifact version 2, frozen snapshot/source identities, the resolved Windows PC decision, all design sections and citations/proposed integration checks. It contains **none** of the advisory ID, check identifier, advisory message, `draft_quality_evaluation` key or `Advisories (non-blocking)` heading. The underlying copied dialogue remains, intentionally: advisories do not auto-fix content.

After reload the completed/locked state and the saved advisory still rendered. The screenshot labelled brief-exported shows the dashboard after download, **not an inline brief viewer**.

### READ ONLY persistence and provenance

Captured before and after approval in PostgreSQL transactions with `SHOW transaction_read_only = on`, then rolled back:

- `model_config.draft_quality_evaluation` exists in both snapshots, bound to reviewed artifact `f179e6d1-bfc3-4ee7-a547-08e4ad7846dc`, containing the same advisory. The API continues to expose this reviewed-draft evaluation after finalization.
- **Every model_config key/value compared equal before and after approval.** Specifically: `allow_unspecified_memory=true`, `defer_runtime=false`, `fresh_dialogue=false`, `dialogue_policy=null`, contract version **2**, frozen resolved decisions, consented document IDs and hosted consent were unchanged.
- Independently canonicalized the saved review request using the real `canonical_review_request`, with and without `draft_quality_evaluation`. Both SHA-256 values equal the stored critique provenance request hash:

```text
7a888cf6ef9b8d7d2eddc4a51d493d3120baf4a0c2f040b18974cd2b9b50156e
```

The whitelist ignores advisory metadata; no prompt, critique or provenance record was rewritten to make the check pass.

### First recorded live verifier CLI execution

Ran only the read-only CLI, with no provider initialization:

```text
docker exec gamemind_backend python -B verify_final_integrity.py 253552bb-00ea-4cfd-a56e-e28662018f84
```

Exit **0**. Saved complete output in `attempt-1/verifier-live.json`:

```text
Reviewed: fec5db7b1c75984c97854466d54713377d8c863bf22a5d3ef9d995a2b6e91330
Final:    41622b8750a8d8538f55112edded6538ffc972f51a6ee609d2a63a03d37fd18e
Verdict:  EQUAL_EXCEPT_DOCUMENTED_METADATA
Differing paths: ["/npc_memory_design/memory_unspecified"]
Permitted addition: /npc_memory_design/memory_unspecified = true
Offending paths: []
```

Runtime deferral did not apply. Final artifact **`205a8232-9ab3-4071-b4ce-14d51312086d`**, version **2**, is **immutable=true**; its GameBlueprint ID is **`76c16f93-9005-4119-8d6a-fadc3aab7ffc`**. Run status is **completed**, saved revisions **0/2**. This passes the documented exception policy and does **not** establish raw reviewed/final hash equality.

## Plain assessment of the draft and brief

- **Good:** exact Section 1 premise and core lore/art/level direction; two recognizable NPCs; separate Ash Pass objective flags; correct source rewards **100 gold/250 XP** and **150 gold/sky-iron gear**, and **5 chunks**. No additional reward/quantity/timer/difficulty number was found. Windows PC is correctly recorded as frozen human direction. NPC memory is empty, uncited and visibly unassessed rather than fabricated.
- **Bad dialogue remains:** Quest 2 is a verbatim objective; Quest 1 combines objectives into an instruction. The advisory caught only the first. NPC speech is more character-like than those hooks, but remains shallow, unbranched scaffolding.
- **Unsupported input claim:** `Standard keyboard and mouse setup for tactical movement and interaction.` is not in the GDD or the resolved platform-only decision. It appears as cited runtime content without an assumption warning. The critic's claim that inputs were specified is wrong. This is outside the three implemented checks.
- **Faction/assignment design is unresolved:** Kaelen gives mining orders and rewards to the resistance-aligned protagonist. Source faction choice makes such a branch possible, not established. Eldrin as the quest giver is explicitly proposed; the Watchtower location is inferred from his title. The brief is not a settled faction/quest design.
- **Ordering overclaim:** `Source ordering requires clearing guards before raising the flag.` overstates a source that lists both actions without an explicit ordering rule. The generated contract checks both action orders. An implementer must decide the rule rather than treating the note as sourced instruction.
- **Reset policy remains thin:** all six NPC triggers use `no reset`, with generic suppression checks, but no concrete frequency contract. This is not runtime-tested dialogue behavior.
- **No off-by-one label or misplaced memory warning found here.** That is absence of applicable live examples, not positive live validation of those recognizers.
- **Bottom line:** useful cited discussion scaffold, not an implementation-ready design brief. The critic's no-findings verdict is not credible semantic proof; the one deterministic advisory added genuine value without pretending to solve the remaining design problems. No draft was edited after generation.

## Screenshots and UX findings

All screenshot paths below start with `<QA_DIR>/quality-advisories-live-20261029-01/attempt-1/`:

1. `01-source-loaded.png` — fresh workspace, one Frostpeak source/four chunks.
2. `02-platform-resolved.png` — frozen human-direction setup.
3. `03-run-setup.png` — actual consent wording and runtime/memory scope before start.
4. `04-review-before-confirmations.png` — review, advisory and initially blocked approval.
5. `05-advisory-detail.png` — region-only screenshot, visually inspected; distinct non-blocking heading, medium label, message and wrapped paths, no controls.
6. `06-quests-and-advisory.png` — quest content alongside the advisory.
7. `07-confirmed-approval-enabled.png` — same advisory with approval enabled after confirmations.
8. `08-after-approval.png` — completed, immutable final state.
9. `09-brief-exported.png` — dashboard after real download.
10. `10-completed-reloaded.png` — completed state/advisory survives reload.

| ID | Rating | Finding |
| --- | --- | --- |
| ADV01 | annoying | Advisory ID and exact compared values are absent from the panel. Only severity/check/message/paths are displayed; reproducing the comparison requires inspecting draft fields or the API. |
| ADV02 | annoying | The decisions-page consent uses generic configured-provider wording; it does not name Google/Gemini or explicitly describe hosted transfer/data use on this route. The normal request nevertheless records hosted consent. |
| ADV03 | annoying | Sixteen repetitive proposal confirmations and long raw quest/state data occupy a tall sidebar/page. The non-blocking advisory is clear, but source/proposal distinctions and useful content remain laborious to review. |
| ADV04 | annoying | The model critic clears copied objective dialogue and unsupported keyboard/mouse input while claiming all requirements are covered. Human inspection and local hints remain essential. |
| ADV05 | cosmetic/log noise | Two GETs to this run's `/evaluation` returned 404 because no separate human evaluation exists. The UI continued normally, but the browser console recorded two resource errors. No browser JavaScript exception or failed mutation was observed. |

No blocker was observed in the scoped advisory → approve/export flow. These are findings, not changes; nothing was implemented during this check.

## Final quota, cleanup and remaining limits

| CLI checkpoint, Pacific day 2026-10-29 | Flash-Lite used / remaining | Flash used |
| --- | ---: | ---: |
| Before backend startup | 0 / 500 | 0 |
| After startup model GET | 1 / 499 | 0 |
| After generation/critique | 4 / 496 | 0 |
| After approval/export and final read-only verification | 4 / 496 | 0 |

**Total: four new real Google attempts: startup GET 1 + plan 1 + generate 1 + critique 1.** The run used **3/12** of its request cap. Approval, export, advisory rendering, policy/hash comparison, verifier, reload and usage CLI used zero Google requests. No retry, backoff, corrective re-ask, repair, truncation resend, mock fallback, quota/auth error or blocking workflow failure occurred.

Stopped the frontend with Ctrl+C and backend with `docker stop gamemind_backend`: backend exit **0**, restart count **0**, policy **no**. Closed the QA browser context; CDP disconnect initially left Chromium running, so sent its graceful `Browser.close` command, then exited the driver. Verified no listeners remained on **3000, 8000 or 9224**. PostgreSQL/Chroma and all saved runs were left intact.

Attempt 2 was **not run**. No positive live quest-label/warning-in-rules example, degraded-run interaction, revision, mobile/keyboard accessibility sweep or general statistical quality evaluation was attempted. Existing offline tests cover separate controls; they are not recounted as live proof. Only this acceptance document is committed; code, `.env`, README/MVP claims and untracked `docs/audit/` remain unchanged. No push.
