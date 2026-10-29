# Current-draft review and content-quality chunk — 2026-10-16

## Outcome

Three focused production fixes are implemented. Hosted content quality is still not acceptable as automatic approval evidence. No QA draft was approved or exported.

1. **Stale critique in the dashboard/API response.** `DesignAgentService._response` selected the newest critique by run timestamp, independently of the selected artifact. A revised draft could therefore show the previous draft's proposals. This reproduced as an intermittent 409 after confirming the visible proposals. The response now selects the exact draft's critique; an unreviewed new draft returns no critique. Final snapshots display the review of their preceding approved draft. Timestamp ties use the same ID ordering as the approval policy. Approval rules were not loosened.
2. **Oversized critic output.** Fresh contract-v2 critics now return canonical artifact paths and evidence references, not copied artifact values. The existing JSON-pointer resolver attaches a detached exact value from the original artifact afterward. Existing paths, section scope, quoted-source validation, omission findings, provenance and approval gates remain. Stored canonical/legacy reviews retain their previous shape. Metadata identifies the value attachment as server-derived, not semantic model verification.
3. **Per-character coverage.** The existing bounded request check treated stages as workflow-wide even for explicit “each/every NPC” requests. A complete first NPC could hide missing progress/completion for a second NPC. Such requests now check each returned NPC; workflow-wide requests remain workflow-wide. This is a bounded English/structural check, not a general intent parser or dialogue-quality judge.

## Verification

- Host Python 3.12: **602 passed, 5 PostgreSQL-fixture cases deselected**, 16.96s, selected 23-module offline regression set.
- Backend container Python 3.11: **171 passed**, 6.84s, contract/critic/content-revision/Phase-3 subset.
- Previously intermittent controlled API consent → generation → rejection/revision → confirmation → design approval → brief export test: three additional independent runs passed. NVIDIA is mocked and SQLite is disposable in this test; this is not hosted acceptance.
- New regressions failed before their fixes: three stale-review cases, path-only critic schema/assembly, and per-NPC coverage.
- Scoped Git whitespace check passed. Environment file hashes unchanged. No packages installed, migrations applied to an existing database, commits or pushes.
- **273 table fingerprints across seven preserved databases unchanged.** Pre-existing application telemetry is compared at the recorded pre-QA cutoff; later background telemetry is excluded. Original saved source/draft/closed accounting also verified.
- No live browser walkthrough, full PostgreSQL-backed suite, type/lint/coverage run, runtime approval or real generation → approval → export acceptance was performed.

## Six-request NVIDIA check

Saved Frostpeak excerpts were copied only into a new isolated QA database and collection. The current configured Super model was used unchanged. The Nano configuration was not changed or called.

| Request | Purpose | Latency | Output tokens | Result |
| --- | --- | ---: | ---: | --- |
| 1 | Explicit-slot Eldrin generation | 10.560s | 442 | Valid JSON, but progress assumed guards already defeated; notes restricted eligibility to one partial state. |
| 2 | Explicit-slot Kaelen generation | 13.342s | 406 | Valid JSON, but progress assumed some ore already collected. |
| 3 | Known-bad control critique | 14.119s | 208 | False clean review: missed greeting-only dialogue, missing failure/restart and wrong mining quantity. Local checks blocked it. |
| 4 | Generated candidate critique | 22.469s | 485 | One style finding, but quoted a generated note as GDD evidence and pointed at an unrelated note. Reference validation blocked it. Missed the concrete progress defects. |
| 5 | Focused progress/notes correction | 8.248s | 371 | Removed explicit “guards defeated” / “some sky-iron gathered” claims. Still repetitive, uneven dialogue; not quality acceptance. |
| 6 | Corrected candidate critique | 5.779s | 250 | False coverage: called empty source-backed sections covered. Local completeness checks blocked it. |

All responses ended with `stop`; none needed retry/repair. Both accounting rows are closed at **6/6 aggregate requests**.

### What this experiment does and does not establish

The existing `backend/tools/content_only_qa.py` helper was reused, not promoted into production. Greeting/progress/completion eligibility, quest objectives, rewards and proposed failure/restart scaffolds were explicitly supplied by the reviewer. The model generated speech, action descriptions and integration notes. This is **not fresh normal-flow quest generation**, nor proof the dashboard can produce the scaffolding independently.

The known-bad and initial candidate controls used identical manually source-grounded summary/lore/art/gameplay context to isolate the selected NPC/quest changes. The final correction critique retained the original failed draft's unselected sections, which were empty. It therefore also checks omission handling, but is **not a like-for-like before/after critic comparison**. No historical failed draft was repaired in place.

## Next coherent chunk

Freeze these controls and fix the independent semantic review boundary before expanding features or changing models. Use focused per-record/state review contracts and verify detection of the known-bad control, correct handling of a manually valid control, and rejection of draft-note-as-source citations. Do not promote a new review/generation path merely because it returns valid JSON. After those controls pass, perform fresh normal-dashboard generation, actual designer review, then design-only approval and brief export in an isolated workspace.

Private machine-readable evidence: `<QA_DIR>/qa-frostpeak-slots-20261016-3938242c\\results.json`, `final-results.json`, `baseline.json`, `isolation-verification.json`. Full requests/responses remain in the isolated QA accounting rows.
