# GameMind MVP — scope, phases and acceptance checklist

Last updated: 2026-10-29
Last scoped verification: 2026-10-29 (separate E70 advisories/consent and E71 field-correction baselines; merged verification is separate).
Release status: **NOT ACCEPTED**  
Current priority: verify the merged E70/E71 result before any live field-correction check. The results below are pre-merge baselines, not a combined-suite claim.

Advisories baseline (pre-merge): **E70 fixes ADV01/ADV02/ADV05 offline: shared effective-provider consent, visible advisory comparisons/short IDs, and an evaluation-presence flag that avoids expected 404 requests. All 1,197 backend tests pass on disposable storage, including load and existing integrity/hash regressions; frontend lint, build and 20 API/rendering checks pass. The new UI changes are not browser-verified. Critique, scores, approval, consent records and finalization remain unchanged; reliable correction (LIVE01), critic accuracy and content usefulness remain open. Existing runs/artifacts are not repaired. Unity stays last; NOT ACCEPTED is unchanged.**

Field-corrections baseline (pre-merge): **E71 implements a non-binding Request correction action for one or two exact quest dialogue hooks or NPC situation labels. Failed corrections retain the original approval path; explicit rejection and LIVE02 are unchanged. All 1,227 backend tests pass on disposable storage, including load and existing integrity/hash regressions; frontend lint, build and nine API/rendering tests pass. This is offline implementation proof, not real Gemini correction quality or browser acceptance. Next: a separately authorized bounded live field-correction check. Existing runs/artifacts, environment and finalization policy are untouched. Unity stays last; NOT ACCEPTED is unchanged.**

This is the single source of truth for current product scope, phase acceptance,
the next work item and MVP readiness. Read it before every GameMind task.
Historical reports describe what happened; they do not override this checklist.

## 1. The product we are finishing

A game developer uploads a GDD, understands its missing/conflicting decisions,
chooses whether to send selected excerpts to the configured hosted provider, and receives cited,
reviewable game-design content. They can request a focused revision, review its
quality, explicitly approve the design and export a useful implementation brief.

The dashboard MVP must work without a Unity editor or a developer manually
constructing the output. It is an assisted design tool, not an autonomous game
builder or a guarantee that generated content is correct.

### In scope

- One ordinary dashboard flow: **GDD → local review → explicit hosted consent →
  generation → critique → human review/revision → design approval → brief export**.
- One active project/workspace and selected GDD sources per run; data remains
  project-scoped even when the user has multiple workspaces.
- A deliberately small NPC/quest slice within the current generation limits
  (up to two NPCs and two quests). Show the selected scope and any omitted source
  content; do not claim a complete game design from a limited slice.
- Source-supported premise, lore, visual direction, levels and gameplay notes.
- Useful NPC profiles, spoken dialogue, quest objectives, rewards, dependencies,
  and source-backed or explicitly proposed failure/restart behavior.
- A readable technical brief with concrete integration steps and proposed checks.
- Honest separation of sourced facts, creative proposals, unresolved decisions,
  local checks, model judgments and actual executed verification.
- Existing local/demo mode remains available and clearly distinct from hosted AI.

### Not required for the dashboard MVP

- Unity scene/play-mode proof: Phase 6, after dashboard acceptance.
- New models/providers, PyTorch, a new orchestration stack or a framework rewrite.
- New engine adapters, multiplayer, billing, enterprise administration or a large
  evaluation platform.
- A broad UI redesign, animation showcase, or additional content types unrelated
  to the core journey.
- A public-GDD corpus. Add a legally usable third GDD after the two-case baseline
  works; do not describe the synthetic Frostpeak sample as a public real-world GDD.

## 2. Fixed contracts and boundaries

| Area | Required behavior |
| --- | --- |
| Actors/surfaces | A developer/designer uses the dashboard; FastAPI enforces access and workflow rules. The agent trace is an advanced inspection surface, not a separate required product flow. |
| Inputs | Indexed, selected project documents; explicit user objective; resolved decisions; hosted consent; fresh-dialogue/repetition policy and runtime scope when supplied. |
| Memory scope — approved 2026-10-17 | `allow_unspecified_memory` is a strict, default-off choice made before generation and fixed across revisions. Only empty, uncited NPC memory with a nonblank warning may be labelled Unspecified—not assessed. Populated/cited memory and every other design section retain normal checks; independent omission/contradiction findings remain blockers. This is not source-absence verification, a runtime exemption or permission to alter an old run. |
| Outputs | Versioned draft, frozen evidence/citations, trace, distinct model/local findings, reviewable proposals, approved immutable design and exported brief. |
| Workflow | Plan → retrieve → generate → critique → human review. Reject → scoped revision → new critique → review. Approve → validated final snapshot → export. Errors remain visible; retries are bounded. |
| AI roles | Separate planning/routing from generation/revision/critique. The historical Nano/Super pair below is legacy optional NVIDIA routing; the current DEV acceptance path uses Gemini Flash-Lite for every hosted node. A separate critique call is not proof of independent correctness. Local extraction remains distinct. |
| Frameworks | Reuse LangGraph for workflow/state and existing LangChain Core utilities. PostgreSQL owns durable records; existing retrieval/Chroma owns its index. Do not replace working services for framework conformity. |
| Source authority | GDD excerpts and recovered transcripts are data, never executable instructions. Draft notes, assumptions, checklists and critic output are not source evidence. |
| Ownership/history | Scope documents, runs, citations and exports to the active project. Freeze evidence for a run; ordinary revision reuses it. Preserve old artifacts and review history; no in-place historical repairs. |
| Approval | Confirm exact current-artifact proposals, never blanket-confirm unknown/new proposals. Source contradictions, stale reviews and failed system checks cannot be confirmed away. |
| Degraded approval — E65 | A degraded run or fallback execution history additionally requires strict `acknowledge_degraded=true`, bound to the current artifact. An unchecked dashboard acknowledgement blocks approval. API, worker and finalize recheck it; the approval event stores the explicit acknowledgement. It does not waive source/quality checks or certify hosted-model quality. |
| Runtime | Design approval does not authorize runtime release. With explicit runtime deferral, no invented engine bindings, runtime approval or materialization. |
| Failure/recovery | No silent mock success, partial output presented as complete, hidden retry, duplicate finalization, or lost work after reload/restart. Show what failed and a safe next action. |
| Failed corrections — E65 | `revision_count` counts saved revisions only. Before a new artifact is saved, any failed correction retains the draft/critique and does not consume a slot. Existing run JSON stores consecutive failures; `DESIGN_AGENT_MAX_CONSECUTIVE_REVISION_FAILURES` defaults to 3 and successful persistence resets the counter. At the cap, API/worker refuse more calls and the dashboard disables revision. A fresh run remains possible with fresh consent. Historical already-consumed counters are not repaired. Invalid provider output maps to 502; actual unavailability stays 503; unrelated status mappings remain unchanged. |

This document does **not** authorize external data transfers, unlimited hosted
requests, environment changes, destructive database operations, commits or pushes.
Respect the user's current authorization and any narrower task boundaries.

### Chunk 1 execution contract — decided 2026-10-18

The user approved the proposed Chunk 1 after the cleanup. This fixes delivery
rules for P1.3–P1.5, P2.1–P2.6, P3.2–P3.4 and P4.1–P4.2; it does not accept
those features or change running approval policy. Keep the existing Phase 0–6 IDs.

**Model decision:** freeze this target pair for the next implementation chunk:

| Role | Selected target |
| --- | --- |
| Planning, text only | `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` |
| Generation, focused revision and separate advisory critique | `nvidia/nemotron-3-super-120b-a12b` |

**Authorized routing amendment — 2026-10-20, E51:** after the original Super
endpoint returned account/function HTTP 404, the user authorized replacement.
The deployed artifact model is now `nvidia/nemotron-3.5-super-vl-120b-a12b`;
Nano Omni and key selectors/values are unchanged. The existing
`NVIDIA_GUIDED_JSON_ENABLED=false` compatibility mode is configured for the
provider (including planning): schema instructions plus the same strict local
validation, not weaker evidence/revision/approval policy. A small native probe
passed but the full native request returned HTTP 500 three times; prompt-schema
mode produced a valid draft. This establishes generation access, not reliable
review, focused correction or release acceptance. No new production code.

E31/E32 support this choice over repeated Lightning timeouts, not a reliability
guarantee. Omni's long/drifting queries remain failures to address, not waived
product requirements. E35 applies the chosen planner in `.env`/`.env.example`
after affected checks and reloads the backend; keys, global limits, providers and
fallback policy are unchanged. This is configured routing, not hosted acceptance.
Chunk 1 itself made no configuration changes or hosted requests. Do not silently
substitute another model on failure.

**Authorized opt-in transport extension — 2026-10-23, E59:** the user requested
Gemini behind the existing completion boundary. `LLM_PROFILE=test` is offline;
dev/showcase use environment-selected Gemini IDs. Unset profile preserves explicit
legacy NVIDIA selection. No saved `.env`, keys, deployed models or graph shape
were changed. This is transport/configuration work, not a new hosted allowance,
accepted generation, or permission to bypass the remaining content gates.

**Current documentation clarification — 2026-10-29:** the pair and deployment
statements above are historical NVIDIA evidence, not the current quickstart.
DEV acceptance uses `GEMINI_DEV_MODEL=gemini-3.5-flash-lite`; Run C records one
browser generation → approval → brief export and completed reload, with the E68
documented metadata exception, not strict byte equality or whole-MVP acceptance.
NVIDIA remains legacy optional. Provider-neutral naming/cleanup is planned after
the MVP; this wording change renames no code and closes no acceptance gate.

**Fixed acceptance inputs and output:**

- Primary: unchanged `docs/demo/sample_gdd_frostpeak.md`; Eldrin and Kaelen,
  Ash Pass and five-chunk sky-iron quests. Preserve both independent Ash Pass
  actions, exact quantities/rewards, factions and level order. Speaker-to-quest
  links and concrete failure/restart rules are explicitly labelled proposals.
- Secondary: unchanged `docs/demo/cyberrakshak_gdd.md`; PATCH and Jay, with
  Phishing Office/Malware Warehouse mission proposals grounded in those levels.
  PATCH is brief/helpful/funny, not lecture-like; preserve Jay's story timing,
  ethical framing and scripted/rule-based-first design. Do not invent canonical
  mission rewards, engine events or new game systems.
- Each NPC gets fresh, distinct greeting/progress/completion speech that fits
  every eligible state. Frostpeak checks both Ash Pass action orders and mining
  at zero/four/five chunks. Greeting once per playthrough; stage speech once per
  eligible stage per attempt, reset only on explicit player-confirmed restart.
  CyberRakshak warnings are once per object/barrier per mission attempt, reset
  only on mission restart, never scanner bypass. These are scoped design choices.
- Preserve supported summary/lore/art/levels/gameplay. Optional improvements are
  proposals, never source facts. Unknown fields stay visibly unknown; only the
  existing pre-run memory choice and runtime deferral permit their narrow exemptions.
- A focused correction must materially fix its selected targets, preserve other
  sections and frozen evidence, and produce a new separately reviewed version.
  A copied/partial correction fails visibly without replacing the old artifact.
- The approved brief must include citations, proposal labels and engine-neutral
  inputs/state, actions, outcomes and proposed manual integration checks. No
  approval/export acceptance until the real dashboard journey proves it.

**Review decision:** the semantic critic is advisory, not an automated quality
authority. Keep its raw findings, misses and false positives visible. A clean
verdict is not verified correctness; a defect claim needs human adjudication.
Confirmed defects must be corrected. Disputing a false positive must record a
reason bound to the exact current artifact/critique/frozen evidence, not hide it.
Authentication, project/source scope, provenance, schema, material-change,
stale-review, proposal-confirmation and runtime gates remain mandatory. Human
judgment cannot override system blockers or certify source absence. Failed or
incomplete review is not a clean review. Existing enforcement stays unchanged
until this policy is implemented and verified; no historical run is reclassified.

**Handoff — ready for Chunk 2:** first reproduce E32's ignored correction and
audit the existing generation/revision and review-policy callers. Reuse the
current adapter, contracts, finding-review records and shared approval gate;
no new review framework, prompt-exception stack or evaluation platform. Prove
correction preservation and rejection of known defects before another bounded
live attempt. All previous request allowances remain closed. Final human
content acceptance is still required, not supplied by approval of this plan.

## 3. How to use this document every time

### Before work

1. Read this file and the applicable `AGENTS.md` instructions.
2. Check the current priority, open blockers and evidence below. Refresh only the
   repository/runtime facts needed for this task; do not repeat completed audits.
3. Select the smallest coherent unchecked item(s) by ID. State the target, success
   condition and verification scope before implementation.
4. Reproduce the actual failure where possible. Check existing helpers/callers;
   prefer correcting shared behavior to adding another special-case layer.
5. Establish a safe test target and any required external-request allowance.
   **`backend/conftest.py` drops/recreates its target schema.** A name containing
   `gamemind_test` is not proof that a database is disposable. Never point it at
   the app database or a retained QA database. Use a confirmed fresh disposable
   test database, or guarded offline `--noconftest` tests that block PostgreSQL and
   external HTTP. `--noconftest` alone does not make every test safe.

### After authorized implementation or QA

1. Update the affected checklist item(s), current blocker/next action and evidence
   row here. Link an existing report or concise reproducible result; a new report
   is not required for every small fix.
2. Mark an acceptance box `[x]` only when its entire stated outcome has evidence.
   Code presence, more tests, valid JSON and a hand-authored fixture are not live
   acceptance. Add the evidence ID beside each checked item.
3. Record failures and skipped checks. Reopen an affected box after a regression;
   preserve the earlier evidence as history instead of rewriting it as a success.
4. Report: target IDs, user-visible result, checks actually run, remaining blocker.
   Do not create another numbered phase system or claim MVP readiness prematurely.

For discussion/read-only tasks, consult the document but do not edit it merely
to log activity. Documentation-only work does not satisfy a product acceptance gate.

## 4. Current phase standing

Checkboxes below mean **accepted behavior**, not “some code exists.” Historical
implementation can be substantial while acceptance remains open.

| Phase | Implementation/evidence standing | Acceptance |
| --- | --- | --- |
| 0 — Stabilize | E24/E26 verify the stack/authenticated upload/local review. E29 verifies frontend build/state/recovery. E41 revalidates the standard backend suite after field-level revision: 985 passed, one load test excluded; one focused boundary regression added. | Accepted local baseline |
| 1 — Integrated GDD intelligence | E29 fixes failed-run recovery. E35 configures Omni; E40 runs the current Omni/Super pair through the real dashboard on isolated QA storage, reaching a draft and revision/critique. Earlier query-quality warnings and general reliability remain. | QA hosted flow demonstrated; production reliability open |
| 2 — Useful developer artifacts | E32 restores named-field revision schema and consolidates active v2 guidance. Fresh draft improves lore/art/proposals, but still omits summary/gameplay; focused hosted correction ignores three target sections and is rejected. | Failing quality gate |
| 3 — Review and evaluation | E19/E20 failed hosted review; V4 remains QA-only and parked. E22 fixes human-resolution field binding. E25 implements the approved pre-run memory-only scope choice with explicit unassessed labels; hosted source judgment and fresh normal-flow acceptance remain open. | Failing quality gate |
| 4 — Approved blueprint/export contract | E36 fixes frozen brief/preview exports and dashboard revision-version binding; local/mock and live negative checks pass. Successful real normal-flow acceptance not established. | Open |
| 5 — Dashboard and portfolio | UI and documentation work exists; coherent, truthful, repeatable MVP demo not signed off. | Open |
| 6 — Unity vertical slice | Adapter/scene code exists; current engine acceptance unverified. | Deferred until dashboard MVP |

Older documents use other Phase 1–8 labels. They are historical implementation
milestones, not a replacement for the Phase 0–6 roadmap here.

## 5. Phase checklists and exit criteria

### Phase 0 — Reliable baseline

Exit: the existing application can be started and verified safely and reproducibly.

- [x] **P0.1** Backend, PostgreSQL, retrieval and frontend start with the existing
  documented configuration; health and actual UI access are verified. Record the
  AI/retrieval mode rather than expecting obsolete health field values. **Evidence: E24.**
  Backend/database/Chroma healthy; actual UI works at `http://localhost:3000`.
  Health reports `local_demo`, `local_lexical`, collection
  `lore_chunks_local_lexical_v1`, dimension 384. The effective design-agent provider
  used NVIDIA in E24; E66 reports the profile-selected provider rather than that
  legacy setting. Green local health is not hosted-generation proof.
- [x] **P0.2** Current backend suite passes on a confirmed disposable database;
  frontend lint/build and relevant existing browser regressions pass. Record exact
  selection, exclusions and failures; no interrupted run counted as a pass. **E29:**
  971 passed, one marked load test excluded, zero skipped; 125 intercepted browser
  state checks, frontend lint and final production build/TypeScript passed.
  **E59:** 1,021 passed including load, zero exclusions/skips; 18 new mocked-SDK
  Gemini cases, frontend lint/build passed. No fresh browser or hosted acceptance.
  **E66:** 1,150 passed including load, zero failures/errors/skips/exclusions;
  four mocked frontend API tests and lint/build passed with external sockets blocked.
- [x] **P0.3** Login/access, project selection, GDD upload/indexing and persistence
  after reload work; unauthenticated and cross-project access are rejected. **E26:**
  real authentication-required QA backend and production UI; browser-only API-base
  override, unmocked backend responses. Registration/logout/login, four indexed
  Frostpeak chunks, local review, reload and workspace switching passed; anonymous
  401, nonmember 403 and wrong-project document 404 verified. No hosted inference.
- [x] **P0.4** Baseline commands, test isolation and remaining reproducible defects
  are recorded. Unity/editor issues are separate and do not block dashboard work.
  **E26:** reproduction below; B1/B2/B3/B5 and E23 focus issue remain separate.

### Phase 1 — GDD intelligence in the ordinary flow

Exit: a developer reaches a reviewable draft and understands its evidence/status
through the normal dashboard, not a hidden QA runner.

- [ ] **P1.1** Upload/select a GDD; show indexed evidence and relevant missing or
  conflicting decisions without requiring hosted inference.
- [ ] **P1.2** Hosted review requires explicit consent for selected documents.
  Declining consent continues locally without any NVIDIA request.
  E24 verifies the actual consent modal and decline path on a newly uploaded
  Frostpeak source, with no agent-start request/run created. A live negative API
  start probe was safety-blocked before execution because a faulty gate could
  send data externally; no API rejection result is claimed from that attempt.
- [ ] **P1.3** Plan, retrieval, generation and separate critique execute with a
  visible bounded trace; errors/retries/provider mode are not disguised as success.
  E28 stops at planning: three approximately 90-second timeouts, HTTP 503, no
  draft/critique. E29 fixes immediate recovery and unknown token-usage presentation
  on both start surfaces with isolated forced-failure API/browser evidence;
  E31 completes hosted execution with QA-only Nano Omni planning and unchanged
  Super, including one disclosed truncation retry. E35 configures Omni in the
  normal backend after local checks; reliable hosted operation remains open (B6).
- [ ] **P1.4** Review shows the exact current draft's critique, evidence, blockers
  and proposals. Reload/restart preserves the run and review state.
  **E67 (offline):** recorded rejection on the current unchanged artifact disables
  approval through a read-only API reason and an early 409, without consuming or
  faulting the checkpoint. Another same-decision correction remains bounded and
  available; a successfully revised artifact can still be approved. No browser
  acceptance or repair of an already faulted historical checkpoint is claimed.
- [x] **P1.5** Rejection revises only the authorized scope, preserves unrelated
  content/source facts, reuses frozen evidence and obtains a new critique.
  **E54:** real Frostpeak UI revision changes Kaelen's two spoken lines and one
  proposal label using typed replacements. Eldrin, all eight unrelated sections,
  identities/eligibility/policy and frozen evidence stay unchanged; version 2
  receives a new hosted critique. This accepts the demonstrated workflow, not
  model compliance/repeatability on both GDDs or the whole phase.
  **E57:** a failed Frostpeak critique resumes its exact checkpoint with fresh
  consent, without planning/retrieval/generation. Two scoped UI corrections retain
  frozen evidence and source/state fields, each followed by a separate critique.
  **E71 (offline):** the separate `request_correction` action permits one/two exact
  quest hook or NPC situation fields, with typed patches and full-content scope
  validation. It records execution/job audit, never a rejection event. Failure
  preserves draft/critique and saved revision count, with the existing bounded
  failure counter; normal approval gates still apply. Successful persistence
  consumes one revision and re-critiques. Explicit reject/LIVE02 remain unchanged.
  No live field-correction or browser acceptance is claimed.

### Phase 2 — Genuinely useful design content

Exit: manually reviewed fresh output from the normal flow is useful to implement,
not just structurally valid. A designer may reject creative choices; the system
must support a focused correction without destroying unrelated work.

- [ ] **P2.1** Selected NPC profiles retain source identity, voice and faction;
  creative speaker/quest associations are explicit proposals, not invented facts.
- [ ] **P2.2** When requested for each NPC, fresh greeting/progress/completion
  speech is distinct, natural and voice-appropriate. Every line fits its actual
  eligibility. Shared progress fits zero and all partial states; failed/completed
  attempts do not trigger active-only lines. Repetition/reset rules are coherent.
- [ ] **P2.3** Selected quests retain every required source action, quantity,
  reward and explicit dependency/order. Independent actions remain independent;
  quantity completion requires the full total. Failure is a concrete terminating
  cause, not ordinary incomplete progress; restart requires the intended explicit
  player action. Unsupported mechanics are absent or scoped proposals.
- [ ] **P2.4** Supported premise/lore/art/levels/gameplay are preserved, including
  source level order. Missing memory/economy/progression/enemy details remain
  honestly unknown, not invented to fill a scorecard. Extra recommendations are
  clearly optional proposals and do not silently alter source-defined mechanics.
- [ ] **P2.5** Each selected artifact has relevant citations and specific,
  engine-neutral integration steps: required input/state, triggering actions,
  expected outcomes and proposed manual checks. Notes/checklists are not presented
  as executed tests or runtime bindings.
- [x] **P2.6** A bounded normal-flow revision fixes an observed content defect
  while preserving approved scope, identities, source constraints and useful
  unaffected content. No hand-built scaffold or hidden output replacement needed.
  E27 fixes a local legacy dialogue-only state-preservation gap; the current v2
  path remains separate. Neither mocked correction nor preserved eligibility
  establishes fresh hosted dialogue usefulness or this acceptance outcome.
  **E54 supersedes that verification limit:** the actual dashboard correction
  removes Kaelen's unsupported return instruction, preserves required five-chunk
  mining and source rewards, and reaches conditional design approval/export.
  Second fresh draft repeats the same defect and remains unapproved (P3.5 open).
  **E57:** recovered E56 draft now has spoken quest hooks rather than policy text
  and state-neutral Eldrin progress; two ordinary UI revisions preserve unrelated
  content. Some quest hooks reuse NPC wording; no claim of uniformly novel prose.

### Phase 3 — Trustworthy review and a small evaluation baseline

Exit: advisory review and human adjudication distinguish real defects from
acceptable proposals on fixed controls and fresh drafts. Known failures cannot
acquire approval through a false clean model review; system gates remain mandatory.

- [x] **P3.1** Freeze a small, source-backed evaluation set: CyberRakshak, the
  synthetic Frostpeak sample, known-bad examples and manually reviewed valid
  controls. Record expected findings and eligible-state counterexamples before
  changing prompts/models; keep comparable before/after inputs. **Evidence: E04, E06.**
  These are assistant-authored/source-reviewed controls, not human release approval
  or fresh model output; their valid scope and limitations are explicit.
- [ ] **P3.2** Evaluate advisory critique on the agreed source, quantity,
  dialogue-state, omission and valid-proposal controls; retain/report every miss
  and false positive by case. The dashboard makes its advisory limits explicit.
  Human review checks these defects independently; confirmed defects require
  correction and model-only false positives require bound adjudication. Neither
  a clean verdict nor a recorded dispute bypasses system checks. This target-policy
  change does not make the current failing critic accepted or rewrite the controls.
- [ ] **P3.3** Findings reference the relevant draft field and authentic frozen
  evidence; generated notes cannot masquerade as GDD quotes. Model findings,
  server-derived values and local findings remain distinguishable.
  **E53:** fresh wire selects an existing field and frozen excerpt index; the
  server attaches the exact current value, section, source ID and full excerpt.
  Historical stored reviews are unchanged. Whole-record references now work
  without abbreviated model copies. This fixes identity/quote fabrication, not
  relevant evidence selection, semantic correctness or general acceptance.
- [ ] **P3.4** The scorecard shows grounding, completeness, contradiction and
  implementation-readiness limits honestly. Source-unknown areas are not falsely
  certified as covered or forced into invented content. Unresolved real blockers
  prevent approval; accepting proposals does not bypass them.
  E25 implements only the approved memory scope contract. It preserves independent
  findings, stale-review rejection, normal populated-memory checks and runtime
  gates; it does not establish general source absence or hosted review quality.
- [ ] **P3.5** Run at least two independent fresh normal-flow acceptance attempts
  for each baseline GDD. Retain first responses, bounded retries/revisions and
  failures; review usefulness manually. Record requests, latency and token usage
  where available. Mock tests and directed QA experiments do not substitute.

### Phase 4 — Approved blueprint/export contract

Exit: approved design is stable and useful to export; runtime restrictions are
enforced without requiring a Unity scene to prove the dashboard MVP.

- [ ] **P4.1** Approval acts on the exact current draft, critique and frozen
  evidence; stale confirmations/reviews fail. Approved snapshots are immutable,
  project-scoped and survive reload; repeated actions do not duplicate finalization.
  **E64:** offline B4b-shaped finalization now preserves the exact reviewed v2
  content hash. Finalization uses the saved contract version and compares canonical
  JSON digests before creating either output. Explicit final-only exceptions:
  when frozen `defer_runtime=true`, set `unity_runtime_preview.runtime_deferred=true`
  and retain the existing de-duplicated warnings plus the exact server deferral
  warning; when `memory_is_unspecified` accepts the reviewed empty/uncited/warned
  section and frozen opt-in, set `npc_memory_design.memory_unspecified=true`.
  Those extra section fields are discarded by typed normalization; moving them
  into review would require changing the existing content/provenance contract.
  No other field/section is exempt. A mismatch records a failed finalize node,
  saves no blueprint/final artifact, retains draft/critique/approval audit and
  revision count, and returns to a real human-review interrupt. Inline API: 409;
  queued job: failed, no automatic retry. Retrying the same approval after the
  fault is removed is tested. The existing one-decision-per-artifact audit rule
  still prevents changing that saved approval to a rejection on the same draft;
  no approval event is deleted or rewritten. No historical final is repaired.
  This is offline contract proof, not fresh browser/hosted acceptance or strict
  byte identity for the two documented metadata exceptions; P4.1 remains open.
  **E68:** the standalone verifier derives only the allowed metadata from reviewed
  content and frozen settings. Run C's saved pair meets that policy, not strict
  byte equality; its browser approval/export and immutable final are recorded in
  the acceptance report. This does not close correction/quality or broader MVP
  acceptance. Moving both flags before human review is planned after the MVP.
  **E65:** fallback output returned successfully but then rejected locally now
  retains `degraded=true` in the failed execution and run. Approval also reads
  execution history, so a stale false run flag cannot bypass acknowledgement.
  A normal hosted failure with no mock result is not falsely marked as fallback.
  Audit event `details` has a prepared Alembic migration; it was applied/tested
  only on disposable storage, not the application DB. Explicit acknowledgement
  is separate from proposal confirmations and does not change critique hashes.
- [x] **P4.2** The technical brief exports through the normal UI after valid
  design approval and preserves source references, NPC speech, quest conditions,
  proposals and practical integration steps without manual repair.
  E36 verifies immutable content, frozen source/decision provenance and version IDs
  in controlled mock exports; it does not establish fresh useful hosted export.
  **E54:** one real hosted Frostpeak draft is corrected/reviewed, approved through
  the actual UI, and exported without editing the document. Repeated UI download
  is byte-identical and includes frozen IDs/excerpts, speech/conditions, proposal
  labels and integration/manual checks. Final artifact version 3 is immutable;
  runtime remains deferred. The 36,364-character brief is verbose; presentation
  polish, CyberRakshak and broader repeatability remain open.
  **E57:** recovered Frostpeak final version 4 exports a reviewed 37,225-character
  brief; repeated UI download is identical at 375/768/1440 px. Source/state data,
  speech, proposal labels and integration checks are intact; runtime stays blocked.
- [ ] **P4.3** Approved-design and runtime-bundle schemas/endpoints are documented
  and contract-tested. Version/project boundaries are explicit; clients cannot
  consume another project's data or unpublished/unapproved runtime content.
- [ ] **P4.4** Design-only approval leaves runtime release/materialization blocked.
  Runtime export requires its separately validated bindings and approval; never
  invent engine IDs to make a design-only GDD exportable as executable content.

### Phase 5 — Dashboard usability and an honest portfolio demo

Exit: another developer can follow the product journey without developer-only
instructions, hidden edits or misleading readiness claims.

- [ ] **P5.1** First-run/onboarding, active project/source, next action and
  local-versus-hosted mode are clear throughout the complete journey.
- [ ] **P5.2** Review the core screens using the parent design rules and
  `emil-design-eng`; use `ui-ux-pro-max` where useful. Verify readable hierarchy,
  light/dark modes, keyboard focus, responsive layouts and essential empty,
  loading, error, success and disabled-action states. No cosmetic rewrite before
  the generation/review gates pass; motion must serve comprehension.
- [ ] **P5.3** Browser-walk the real backend journey, including declined consent,
  provider failure, blocked approval/export and successful design-only export.
  No intercepted/mock responses counted as live acceptance.
- [ ] **P5.4** README/setup/demo instructions match verified behavior and explain
  model roles, LangGraph/LangChain usage, grounding, consent, evaluation and
  limitations. A short CyberRakshak demo shows genuine normal-flow output and
  human review; no claim of production or Unity readiness without its proof.

### Phase 6 — Unity proof, last

Start only after the dashboard MVP release checklist below passes.

- [ ] **P6.1** Revalidate the existing Unity package/scene; record editor version
  and fix actual compile/play-mode issues without broad rewrites.
- [ ] **P6.2** Consume only appropriately approved, project-scoped backend runtime
  data; no hardcoded content substituted for the approved export.
- [ ] **P6.3** One scene demonstrates one NPC conversation, one quest and
  progressive hints, including state changes and invalid/failed actions.
- [ ] **P6.4** Record the GDD → review → design/runtime approval → Unity slice,
  explicitly separating design intent, contract tests and actual engine execution.

## 6. Dashboard MVP release checklist

Phase 6 is not a dashboard release requirement. Finishing a later phase's code
does not compensate for a failed earlier acceptance gate.

- [x] **MVP.1** Phase 0 accepted on the release candidate, with safe reproducible
  verification and no unresolved critical/high auth or data-integrity defects.
  **E24/E26/E29:** local dirty-tree baseline only; not public-deployment/SMTP sign-off
  or acceptance of generated content, semantic review, approval/export or Unity.
- [ ] **MVP.2** Phases 1–3 accepted for the two baseline GDDs through the normal
  flow: useful content, real review, bounded correction and honest evidence.
- [ ] **MVP.3** Phase 4 accepted: explicit approval and successful useful brief
  export; unsafe/unapproved runtime release remains blocked.
- [ ] **MVP.4** Phase 5 accepted: actual browser walkthrough, usable essential
  states, clear onboarding and a reproducible honest demo.
- [ ] **MVP.5** No unresolved critical/high defect in the core journey. Remaining
  lower-severity limitations have impact, workaround and explicit acceptance.
- [ ] **MVP.6** Acceptance record identifies revision/dirty-tree scope, inputs,
  mode/models, run/artifact IDs, exact checks/results, requests and limitations.
  Re-run affected gates after subsequent relevant changes.
- [ ] **MVP.7** Final human review of the actual exported content and dashboard
  journey is recorded. Only then change Release status to ACCEPTED.

## 7. Current blockers and next work

| ID | Confirmed blocker | Checklist affected | Next focused action |
| --- | --- | --- | --- |
| B1 — E57, retained Frostpeak recovery completed | Exact failed critique resumes with fresh consent, durable attempt/job fencing and no regeneration. Two real UI corrections replace non-spoken quest hooks and fix shared-state Eldrin speech; source/state fields and seven unrelated sections remain exact. Full suite 998 passed/one load deselected. | P1.5/P2.6/P4.2 demonstrated again through recovery; fresh repeatability open | Do not reimplement recovery. Retain the approved brief and verify the remaining CyberRakshak generation/content gate, then fresh two-case acceptance. Some hook wording repeats NPC speech; the existing two-revision limit was respected, not enlarged. |
| B2 — E57, semantic critique unresolved | Critic detects Eldrin's initial defect but misses non-spoken quest hooks, invents ordering/per-item requirements, and flags permitted unspecified memory. Final five false/no-op findings are individually QA-adjudicated with exact frozen references; raw reviews remain intact. | P3.2–P3.4 | Keep explicit reviewer judgment and deterministic checks. This is assisted review, not a clean/correct AI verdict. No more prompt layers or heuristic suppression as a substitute for measuring actual defects and false positives. |
| B3 — E54 fresh journey plus E57 recovered journey verified | E54's normal Frostpeak generation/correction/approval/export remains historical. E57 additionally recovers E56's retained draft, corrects it through the UI and exports immutable final version 4 without injected content or edited output. | P1.5/P2.6/P4.2 demonstrated; P3.5 and whole phases remain open | Retain both audits. E57 is not a second fresh-generation success; CyberRakshak remains unaccepted. Complete the two-case baseline before whole-phase/MVP claims. |
| B4 — baseline closed, E26 | Full standard backend suite, final frontend build/lint/state checks and real authenticated upload/local-review/access baseline pass on fresh isolated QA storage. Trusted current-draft finding recording and fresh hosted generation remain separate unverified journeys. | P0.2–P0.4, MVP.1 accepted | Re-run affected baseline checks after relevant changes; do not repeat broad baseline work as a substitute for B1/B2 quality progress. Use the documented localhost dashboard origin. |
| B5 — locally fixed, E22 | New and replayed resolutions now use one shared exact-reference path/value validator. Referenced UI fields are fixed, wrapping/read-only, and support object values. Invalid old records remain immutable/readable but cannot affect approval; legacy unreferenced findings keep their prior handling. 66 backend regressions and 19 intercepted browser checks pass; production build passes. | P3.4, P4.1 | Verify the real backend/dashboard journey separately. Local API tests use fresh in-memory SQLite, and browser responses are mocked; neither establishes PostgreSQL or hosted normal-flow acceptance. Affected old records require a new critique, not silent repair. |
| B6 — E58, fresh generation still blocked | First Cyber output is complete only after truncation/larger-output retry, then fails seven copied UUID references. Short-label wire selection is locally fixed and validated labels appear in fresh Frostpeak; canonical restoration is offline-tested, not accepted hosted output. Second Cyber start fails planning after three HTTP 503s. Frostpeak planning recovers from one 503, but its complete response wrongly cites an empty deferred-runtime section and contains real partial-state/return dialogue defects. No accepted draft or critique is created. | P1.3, P2.1–P2.5, P3.2–P3.5 | Fix the actual empty-runtime generation contract and speech semantics without stripping model claims, changing models or weakening validation. E58 closed 11/16: all three allowed fresh starts used, zero corrections. Do not start a fourth run with the five unused requests or reuse any closed allowance. Retain the raw failures; fresh normal-flow verification remains required. |
| B7 — fixed, E29 | HTTP 503 now returns safe message/persisted run ID. Advanced start closes consent, selects the failed run/URL and opens its trace; GDD review exposes the trace link alongside the error. Unknown/partial usage is labelled honestly, measured zero remains zero, and no-draft failure copy is explicit. Failed follow-up reads preserve setup/recoverable URL; no auto-retry. | P1.3–P1.4, P5.2 — recovery only | Verified with local failure injection on fresh PostgreSQL and real API/browser at 375/1440 px; no hosted call. Keep the broader phase gates open: successful generation, trusted review, approval/export and B6 remain separate. |
| B8 — E47 fixed; E48 hosted recovery verified | Recovery returns known revision failures to human review, preserves draft/critique/failed trace, charges one budget slot and never automatically retries. Inline 409 and queued failure handling are aligned; queued attempt keys include revision count. E48 actual NVIDIA corrections fail citation/material checks; both return 409 and preserve the version-1 draft/critique in awaiting_review across real dashboard reload. | P1.5, P2.6, P4.2, P5.2 | Recovery is verified for these two hosted failures, not useful correction or approval/export. Do not retroactively alter the closed E47 run. Keep B1/B2 and positive release acceptance open. |
| B9 — LIVE02, E67 offline containment | The real DEV browser run exposed reject → failed revision → approve on the same artifact returning 500. New conflicting requests now stop at 409 before resume/enqueue; the UI disables Approve and offers the bounded correction/new-isolated-run path. Unexpected review exceptions receive a failed trace entry and a redacted server traceback. | P1.4/P1.5/P4.2/P5.2 | Keep one recorded decision per artifact. No supersession or existing-checkpoint repair. LIVE01 is unchanged and still prevents the demonstrated quest-dialogue correction; no fresh live approval/export or final-hash proof is claimed. |

**Recovery chunk 1 — complete as diagnosis, E39:** traced the saved request,
both NVIDIA envelopes, frozen evidence, schema, assembly, material gate and
persistence. The final model response itself is incomplete; the current pipeline
does not discard a valid correction. No new production patch was justified.
E35's existing prompt correction remains unverified by a fresh completion.
**E40 executes that fresh journey but fails quality:** six sends complete;
revision improves three targeted areas but leaves summary/quantity defects, and
the revised critic misses both. No approval/export. The newly exposed empty
summary/citation-only material-change loophole is fixed locally, not patched into
the historical QA artifact. E40's allowance is closed 6/6; E37/E38 remain closed.
**E41 implements the requested narrower correction path locally:** the existing
dashboard scope/reason now drives field replacements, not full-section rewrites.
Omitted fields and objective state keys are preserved; full assembly, frozen
citations, material-change and approval gates remain. No new model/env/API option.
**E42 executes changed-flow verification and fails acceptance:** four HTTP 200
sends; revision uses the new field wire but invalid action objects fail assembly.
Requested NPC/quantity corrections remain unchanged and lore citation is wrong.
Old draft/critique survive browser reload, approval unavailable; no export.
**E43 completes the local type fix:** same field-patch wire now reuses existing
revision annotations/constraints, grouping paths by type. Saved E42 action objects
fail before assembly; valid null/empty action replacement controls pass. Full
standard suite 985 passed, one load test excluded; no backend test-count growth.
**E44 completes a fresh typed-schema check, not useful correction:** same first
revision prompt, frozen E42 draft/evidence; one HTTP 200 response passes native
JSON Schema but fails local readability because failure causes are JSON pointers.
Requested dialogue/mining edits and source citations remain uncorrected. No valid
candidate/new critique, database write or approval/export. Closed at 1/3 used;
unused slots and all older allowances remain closed. Next diagnose semantic
correction/useful action/citation reliability on frozen inputs, not another
schema-only patch, blind batch, model change or gate relaxation. B1/B2 stay open.

**E45 tests the one-field hypothesis before product integration:** 666-character
schema, explicit three-state context and unchanged Super. One line changes in
2.188 s, with exact preservation outside the line/derived mirrors. Manual review
does not accept its flag-awaiting-resolve ambiguity; critic misses it and emits
an already-satisfied memory recommendation. Three sends consumed, including the
existing critique truncation retry. Closed 3/3; not promoted into production.
The chunk stop rule applies: semantic correction is not fixed. No new broad
implementation or hosted batch justified by this result alone.

**E46 follows the renewed implementation/iteration request:** reused the existing
compact dialogue helper in the normal v2 provider, preserving governed-schema
failure, citation, identity, eligibility and final review gates. Full suite remains
985 passing with no test-count growth. In the newly authorized two-iteration
batch, first reply fails; concrete counterexample/identity feedback yields a
state-neutral line on iteration two, then a separate critique. Scope postcheck
passes; creative Watchtower motivation still needs designer review. Other quest/
citation and critic no-op defects remain. Closed 3/6; no DB/approval/export.
New disposable test resources auto-remove; no additional retained Docker clutter.

**E47 follows the request to fix critic/source/quantity and verify real export:**
v2 critic had lost the existing no-op instruction and received memory-authoring
instructions. Corrected the task boundary without suppressing raw findings or
inventing model accuracy. Existing explicit quest parser now also checks source
amounts when generated objective/action fields all omit them; exact identity/
format limits remain. Fresh normal-flow hosted output preserves 5 chunks but
omits four sourced sections and requested failure/restart proposals. The critic
emits no memory no-op in this one response but misses omissions/delivery defects.
The attempted correction changes NPC speech and labels, not quest behavior, and
is rejected before persistence. Closed 5/8 including one planner 503 retry; no
approval/export. That exposed B8, fixed locally across workflow/API/queue/UI with
bounded human-driven recovery. Standard backend suite remains 985 passing, no
new cases; build/TypeScript, lint and all 125 intercepted dashboard-state checks
pass, including rejection/budget recovery at desktop/mobile. Live positive export remains open;
no phase/acceptance checkbox closes from these results. See E47 assessment.

**E48 complete-check outcome:** the authorized 16 sends are exhausted and closed,
with two fresh normal dashboard runs and two explicit corrections in one new
isolated QA workspace. Lore/art/gameplay and concrete failure/restart proposals
are present this time; both drafts still omit the source-backed summary, narrow
progress situations incorrectly and add incompatible quest ordering. Both raw
critics falsely claim no evidence was provided. Corrections copy unchanged fields
and omit quest/system edits; citation/material gates reject, and E47 recovery now
preserves the current draft/critique in actual hosted/browser checks. Supplying
the native schema additionally as prompt text did not reach the quality bar and
increased prompt size; that experiment and temporary test assertion were removed
byte-for-byte. No net production/test-code, dependency, model or env change this
turn. Full suite during experiment: 985 passed/one marked load deselected, 101.41 s;
final restored-code affected checks: 163 passed, 12.57 s. No approval/export or
phase acceptance. Preserve frozen failures for a smaller contract/task design,
not another unstructured prompt-growth or model-switch batch.

**E49 compact-contract outcome:** reused typed section revisions and reduced the
critic's duplicated schema branches without relaxing source/path/material gates.
Frozen quest correction is partial; summary/NPC corrections are rejected no-ops,
and raw critique still misreports evidence. Fresh dashboard Frostpeak generation
has more usable state-neutral dialogue but loses the mining objective quantity;
its critic misses that and a wrong summary selected by the initial local parser.
The final local fix seeds only an explicitly headed, exact single-source premise;
actual saved evidence replays correctly offline. Independent code review also
exposed wording-only edits reallocating state keys, now fixed for unique unchanged
completion behavior. Final standard suite: 985 passed, one load test deselected,
100.77 s; existing cases extended, no test-count growth. Closed 11/12 sends,
including two planner 503 retries; one remaining send cannot cover correction and
required critique. No approval/export/CyberRakshak acceptance. Application counts,
models and environment unchanged. QA DB archived, own temporary services removed;
Docker returns to its 120-container baseline. Next remains useful source-complete
correction and honest critique, then positive dashboard approval/export—not Unity.

The user also requested Chunk 3. E36 completes two confirmed flow-integrity fixes
without approving an existing draft: frozen exports and version-bound dashboard
revisions. Its successful mock journey and real negative checks do not replace
Chunk 2's pending live quality gate or the eventual positive dashboard journey.

E31 resolves the bounded comparison, not production availability or product
acceptance. At E31, Omni had run only in QA; E35 now applies the chosen route in
the normal backend. E37/E38 now probe that deployment but do not establish
reliable operation. Super stays unchanged; Omni is
not an accepted planner. Its long/drifting queries remain recorded failures.
No further planner roulette, global limit increases or bypasses. The E31
**eight-request allowance is closed at 8/8**:
four synthetic comparisons plus plan, generation and two critique sends (one
existing truncation retry). No revision, approval or export occurred. E30 is closed
2/2; E28 is closed at three used, and no unused historical allowance is reusable.
E32's fresh six-request verification is **closed at 5/6 used**: plan, generation,
critique, revision and its existing truncation retry. Revision rejected before a
new critique/artifact; unused request is not reusable. No approval/export, model
promotion or environment change. Any new hosted transfer requires a fresh bounded
allowance. No new phase/checklist acceptance follows; E32's full-suite result is
fresh local baseline evidence, not content proof.

**Baseline reproduction, E26:** QA runner and retained logs/screenshots (`<QA_DIR>/qa-baseline-20261017/`).
The backend runner must execute only in a newly created internal Docker QA network
with fresh PostgreSQL 15 (`qa-db`, empty `gamemind_test_baseline`) and Chroma 0.5.23
(`qa-chroma`). Mount `backend` at `/app` and `docs` at `/docs` read-only, and the QA
folder at `/qa`; reuse the installed `bot-backend:latest` image. Container command:
`python -u -B /qa/run.py`. It asserts the empty target, uses explicit CI-style
test settings instead of the local `.env.test`, selects mock providers and enables
the installed AnyIO plugin while disabling unrelated plugin autoload. Never run
the schema-resetting suite in the application container or a retained QA database.
From `Bot/frontend`, run `npm run lint`, then `npm run build` with the agent-owned
server stopped, restart with `npm run start -- --hostname 127.0.0.1 --port 3000`,
and run the existing dashboard checks in installed Edge:

```powershell
node -e "const {chromium}=require('playwright'); const launch=chromium.launch.bind(chromium); chromium.launch=(options)=>launch({...options,channel:'msedge'}); import('./tests/dashboard-states.mjs');"
```

The real auth walkthrough uses `auth-browser.cjs` and `proxy.py` in that QA folder:
a fresh separate auth database, QA-only `AUTH_REQUIRED=true`, loopback ingress on
8097, browser-only API-base configuration, disabled mail and no outbound backend
access. It does not establish production email delivery or deployability. All
temporary QA services were stopped after verification; test databases were
disposable, and logs/screenshots remain. The normal application stack/frontend
remain running, with their original environment/provider settings.
B5 is locally fixed in E22: record creation and replay
require the finding's exact referenced path/current value; immutable bad records
do not acquire effect. The UI fixes that field and renders structured values.
Auth, stale/unknown/recovered-review checks, deterministic blockers, proposal
confirmation and explicit approval remain intact in the selected regressions.
Do not introduce an automatic text-based no-op classifier or pretend quote
membership proves entailment. A trusted source/scope policy needs explicit design
before implementation; do not invent missing game content to satisfy a score.

E23 confirmed the original source/scope action was missing, not merely hidden in the UI:
`grounding.py::assess_artifact_quality` requires all non-runtime-deferred sections;
`complete_design_critique` recommends recording a human scope decision, but the
finding-resolution contract can only dispute model findings and cannot remove
system checks. A future scoped-deferral design must bind the human decision to
the current artifact/evidence, distinguish deliberate scope from proven source
absence, and leave core NPC/quest requirements and contradictions enforced. This
was the original policy proposal. The user subsequently approved E25's narrower
memory-only option at run creation; other source/scope exemptions remain unimplemented.
Separately, E23
reproduced keyboard focus loss to BODY after unavailable-workspace Retry:
`frontend/src/components/DashboardLayout.tsx` replaces the error/action with its
loading state and remounts it without restoring focus. Track this small P5.2
accessibility fix; it does not justify a redesign.

E24 also reproduced and narrowly fixed a local-review false positive: Frostpeak's
"seize control" narrative was marked as an explicit platform/control decision.
`GddReviewService.REQUIRED_DECISIONS` now requires an input/control context instead
of bare control/controls; existing platform/input-device signals remain. New QA
review now has four open decisions rather than three. Existing persisted decisions
were not silently resynchronized. This remains lexical triage, not a general
semantic completeness guarantee. The authenticated B5 form/recording, source-scope
decision policy beyond the E25 memory-only choice, and E23 Retry focus issue remain open.

E21 inspected the existing flow without changing policy: authenticated workspace
owners/editors can record evidence-linked judgments; recording does not resume or
finalize the run. Trusted normal-adapter provenance is required for a resolution
to affect approval; QA-only/recovered/unknown reviews cannot be promoted. System
checks are recomputed after projection. A human's semantic judgment is not
automatically verified, and these local checks do not cover every possible source
contradiction. E22's scoped binding is necessary, not sufficient for trusted review.

V4 is parked after E19/E20, not integrated. E19's 1024-token cap failed both
Frostpeak responses; E20's small outputs fit but reproduced the false positive
under both schemas. A union-only explanation is not supported by that pair;
NVIDIA internal decoding/field-order causality remains unproven. Do not repeat
these batches, raise limits, switch models or stack prompt exceptions as a remedy.
All E19/E20 requests and earlier allowances are closed/exhausted. Any future
hosted experiment requires a fresh bounded allowance and a discriminating goal.

P3.4 still needs trustworthy source judgment and live verification of its narrow
memory-only policy; unknown content outside that choice remains blocked. Preserve
E04/E06 expectations and every historical response/runner. No broad rescan or
evaluation-platform growth. After review/content gates actually pass, close
P2.2/P2.6 and verify the full normal dashboard journey, alongside relevant P0
baseline checks. No checklist box closes from this local fix or tracker update.

**Decided:** Chunk 1 fixes the model pair and advisory semantic-review role.
E35 applies routing and clarifies the existing bound adjudication UI; real hosted
content/review acceptance remains pending. See the execution contract.
**Open decisions:** game-specific missing facts that change output semantics and
final human acceptance of actual content/known limitations. These are per-run
designer choices, not permission for the model to invent facts or for an agent to
approve the release. No new product-policy choice blocks starting Chunk 2.

**Handoff:** scope is ready for Chunk 2 diagnosis/implementation against the fixed
contract and existing IDs. A broader architecture/scope change needs discussion.
No fresh hosted-call allowance is supplied by this document; all retained live
QA ledgers are closed, including E19/E20's separate four-request allowances.

## 8. Evidence ledger

Keep this concise. Test subsets overlap; do not add their counts together. Link
new evidence and date it; do not infer acceptance from old implementation claims.

| ID/date | Evidence | What it establishes | What it does not establish |
| --- | --- | --- | --- |
| E01 — 2026-10-16 | [Current-draft review/content-quality report](docs/validation/current-draft-review-content-quality-2026-10-16.md) | 602 selected offline regressions passed, five PostgreSQL-fixture cases excluded; 171 overlapping container tests passed. Stale-critique, compact-reference and per-NPC coverage fixes tested. Controlled mock API approval/export passed. | Full backend suite, real browser acceptance, hosted generation quality or production readiness. |
| E02 — 2026-10-16 | [Same report: six-request QA](docs/validation/current-draft-review-content-quality-2026-10-16.md#six-request-nvidia-check) | Six real NVIDIA requests; preserved existing data; concrete generation and critic failures retained. Local gates blocked unsafe acceptance. | Successful normal-flow generation, independently useful full quest generation, reliable critic, approval/export or Unity proof. |
| E03 — 2026-10-16 | This document and repository `AGENTS.md` | One canonical scope/checklist and mandatory before/after task workflow established. | Any product phase accepted; no runtime/model tests performed for this documentation task. |
| E04 — 2026-10-16 | [Frozen critic controls/protocol](backend/tests/fixtures/critic_review_controls.md), [dataset](backend/tests/fixtures/critic_review_controls.json), `backend/test_critic_controls.py` | Two bundled GDDs, two valid controls and four bad contrasts; exact source hashes/excerpts, five agreed defect expectations with current-field paths and failing states. Invalid draft-note-as-source quote replay is rejected. V1 passed host checks but final container adapter checks exposed evidence-budget overflow (118 passed, two failed, one deselected); corrected in E06 without changing expectations. | Hosted critic accuracy, full retrieval/generation, human approval or runtime proof. Valid controls do not bypass the unresolved unknown-section scorecard blocker. |
| E05 — 2026-10-16 | `backend/app/design_agent/nvidia_provider.py`, projection regressions in `backend/test_independent_critic_boundary.py` and `backend/test_design_prompt_usability.py` | Reproduced shifted note-index failure before fix. Compact note objects retain original list positions; response paths are limited to visible input; original-value/provenance binding and saved/API arrays remain unchanged. 610 selected offline tests passed (five DB-fixture cases excluded); 120 overlapping container tests passed (one host-only source-hash check excluded). Environment hashes unchanged; zero hosted requests. | P3.2/P3.3 semantic or hosted acceptance, full backend suite, browser flow, approval/export or production readiness. |
| E06 — 2026-10-16 | Same frozen controls/protocol and adapter tests | P3.1 complete: V1 archived; V2 groups only contiguous CyberRakshak level evidence and remaps citation IDs. Seven excerpts fit the existing 10-item/1200-character limit and survive the normal adapter unchanged. Artifact content, case expectations, source hashes and Frostpeak baseline are unchanged. Current rerun: 610 selected host checks passed (five DB-fixture cases excluded); 120 overlapping container checks passed (one host-only source-hash check excluded). Environment hashes unchanged; no database/network access or NVIDIA calls. | Hosted critic sensitivity/false positives, complete backend suite, browser journey, approval/export or MVP readiness. |
| E07 — 2026-10-16 | Isolated frozen-case live comparison (`<QA_DIR>/qa-critic-controls-20261016-b672e8f4/README.md`), raw responses/outcomes and closed ledger beside it | Six authorized NVIDIA critique requests, no retry/repair/recovery; all cases completed. Model caught two of five agreed defects and missed three; one valid control falsely required failure rules, plus an extra conditional memory no-op. Four references structurally valid; no answer leakage, exact evidence retained. Reproduced local future-conditional false positive and source-unknown memory blocker. Mean critique 11.013 s; 23,505 input/1,904 output tokens. No database access or model/environment changes. | Reliable critic, general accuracy, sparse-note-index hosted proof, fresh generation, browser/full suite, approval/export or MVP readiness. P3.2–P3.4 remain open; allowance exhausted. |
| E08 — 2026-10-16 | `backend/app/design_agent/grounding.py`; regressions in `backend/test_critic_controls.py` and `backend/test_phase3_generation_contract.py` | Reproduced seven failures before fixing shared local behavior. Bounded English check distinguishes tested return/come-back/wait conditions from current-state assertions, including claims before a conditional; frozen bad progress line now flagged. Governed uncited empty sections with warnings receive pending source-review triage, not an invented-content demand; scorecard and approval remain blocked. Cited omissions stay high-severity; independent findings/inputs remain unchanged. 632 selected host tests passed (E06 selection plus multilingual checks; five DB-fixture cases excluded); 201 overlapping container checks passed (independent critic, contract-v2, content revision, frozen controls, phase3 contracts, runtime deferral; one host-only source-hash check excluded). Frozen dataset/environment hashes unchanged; zero hosted calls. | General English semantic correctness, trusted source-absence resolution/approval, hosted critic improvement, complete backend suite, browser journey or export. Unknown-section approval remains unresolved; P3.2–P3.4 stay unchecked. |
| E09 — 2026-10-16 | `backend/app/design_agent/contracts.py::section_critique_response_model`; existing contract/adapter/transport tests and frozen control adapter fixtures | Three reproducing failures before fix. Fresh contract-2 wire schema reuses the existing design-presence check to disallow covered for null/blank/nested-empty/metadata-only sections; explicit zero/false remain content, not semantic proof. Missing requires cited findings; unknown/deferred labels retain existing limits. Invalid covered-empty response is rejected without repair. Local replay of all six saved E07 responses rejects only the omission response; no historical response rewritten. 634 selected host tests passed (five DB-fixture cases excluded); 203 overlapping container checks passed (one host-only source-hash check excluded), same selections as E08. Frozen controls/environment unchanged; no prompt/model/API storage changes or hosted calls. | Better hosted detection, truthful not_specified claims, source entailment, accepted unknown scope, full backend suite, browser/generation/approval/export or MVP readiness. P3.2–P3.4 remain unchecked. |
| E10 — 2026-10-16 | Isolated repeated frozen-case comparison (`<QA_DIR>/qa-critic-controls-20261016-d9a348e1/README.md`), raw responses/outcomes and closed ledger beside it | Six newly authorized critique requests, one per case; no retry/repair/recovery or schema rejection. Caught one of five planted defects (quantity); missed four, including both omissions now labelled not_specified. One valid control received a no-op finding. Two references structurally valid, not both relevant. Draft/evidence/input files identical to E07; transport bodies differ only in response schema. Mean critique 6.597 s, 23,505 input/1,577 output tokens. No DB, product-code, prompt/model/environment or approval/export changes. Allowance exhausted. | Improved critic judgment, general accuracy/causal regression proof, truthful source absence, sparse-note hosted proof, generation/full-suite/browser/approval/export or MVP readiness. P3.2–P3.4 remain unchecked. |
| E11 — 2026-10-16 | Isolated targeted-review prototype and protocol (`<QA_DIR>/qa-targeted-review-prototype-20261016/README.md`), `targeted_review.py`, `test_targeted_review.py` beside it | User approved QA-only two-pass design and baseline call increase. Separate source/quest and dialogue/state inputs; mandatory per-check compatible/defect/uncertain outputs; authentic quotes/scoped paths/real typed-state IDs checked; partial failures retained, repair-capable providers rejected, originals unchanged. Explicit provider identity and permanent QA blocker prevent approval even for all-compatible mocks. 15 prototype checks plus existing boundary selection: 106 host passed, 105 overlapping container passed (one host-only source-hash check excluded). Scripted response sizes measured; actual 1024-token fit unverified. Application/frozen-input/environment hashes unchanged; zero NVIDIA calls, no dashboard integration. | Hosted defect detection, token-fit proof, full design coverage, source absence resolution, production/full-suite/browser/generation/approval/export or MVP acceptance. Future hosted comparison needs separately bounded consent; P3.2–P3.4 remain unchecked. |

| E12 — 2026-10-16 | Isolated bounded runner/preflight (`<QA_DIR>/qa-targeted-live-20261016/README.md`), `run.py` beside it | Six frozen inputs passed two-pass offline preflight in the existing container; mandatory comparisons, immutable inputs, QA approval block, 12-request cap and unrelated HTTP/DB denial checked. Fixture/five app-source hashes still match E10. Safety reviewer blocked proposed live command before execution for insufficiently explicit payload/destination/cap consent; zero hosted requests or live ledger/results at that checkpoint. No application integration, model/environment change, restart or approval/export. | Hosted comparison, model usefulness/token fit, full suite/browser/normal-flow acceptance or any new checklist acceptance. Later explicitly authorized execution recorded separately in E13. |
| E13 — 2026-10-16 | Targeted hosted comparison (`<QA_DIR>/qa-targeted-live-20261016/README.md`), six original responses, inputs, outcomes and closed ledger beside it | User confirmed explicit twelve-request scope; six requests actually used, no retry/repair/recovery/truncation. All HTTP 200/schema-valid/stop; all six source passes failed quote membership (18/22 invalid), all dialogue passes not_started. Raw quantity/premise/art detections retained but no accepted referenced defects. Source outputs 310–567 tokens at unchanged 1024 limit; 22,315 input/2,435 output total; mean HTTP 15.855 s. Six input files byte-identical E10, app/fixture/env hashes unchanged. No DB, approval/export or dashboard integration; ledger closed with six unused slots not reusable implicitly. | Accepted critic sensitivity/false-positive rate, dialogue detection or budget fit, source entailment, normal generation/browser/full suite/approval/export, any phase acceptance. P3.2–P3.4 remain unchecked. |
| E14 — 2026-10-16 | QA prototype V2 (`<QA_DIR>/qa-targeted-review-prototype-20261016/README.md`), current source/tests; archived V1 beside E13 outputs | Six reproducing test failures before fix. Model selects closed source-span IDs; server attaches exact frozen text/offsets and original field values. Invalid/missing source output no longer hides independent dialogue diagnostics; cap/auth errors still stop requests, any failed pass stays non-passing, permanent QA approval blocker remains. 20 prototype checks; 32 host passed with controls, 110 overlapping container passed with contract/critic selection (one host-only hash check excluded), matching V2 hashes. Broader host run interrupted without final result. Saved E13 freehand responses still rejected, historical source archived with matching hash, app/fixture/env unchanged; zero NVIDIA/DB calls or integration. | Hosted correctness, relevant evidence selection/entailment, V2 output-token/cost proof, full suite/browser/generation/approval/export, production integration or any new accepted phase. Catalog increases input size; P3.2–P3.4 remain unchecked. |
| E15 — 2026-10-16 | Isolated V2 hosted comparison (`<QA_DIR>/qa-targeted-v2-live-20261016/README.md`), frozen prototype, twelve responses and closed ledger beside it | New bounded twelve-request QA authorization used exactly twelve; six source/dialogue pairs complete, all HTTP 200/schema-valid/stop, no retry/repair/recovery. All five planted defects recognized, but eight incorrect/no-op/unsupported findings and 23 uncertain dialogue checks; both valid controls lack a clean dialogue judgment. 29 exact server-bound source spans, 13 structurally valid finding references, not all semantically relevant. Outputs 122–684 tokens at unchanged 1024 cap; 66,640 input/3,969 output tokens, mean HTTP 9.942 s. Inputs byte-identical E13/E10; app/fixture/env unchanged; no DB, generation, integration or approval/export. Allowance closed/exhausted. | Reliable judgment, clean false-positive/uncertainty performance, general accuracy/causal representation proof, source entailment/unknown resolution, full suite/browser/normal generation/approval/export or phase acceptance. P3.2–P3.4 remain unchecked. |
| E16 — 2026-10-16 | QA prototype V3 (`<QA_DIR>/qa-targeted-review-prototype-20261016/README.md`), current source/tests; frozen E15 V2 unchanged | Five reproducing failures before fix. Check/lifecycle-unique state IDs and explicit review basis; source/situation-only checks have no fake quest states. Per-check schemas reject foreign/legacy IDs; diagnostics bind actual selected lifecycle/flags and preserve false model allegations unchanged. 26 external prototype checks, 38 host passed with frozen controls, 116 overlapping container passed with contract/critic selection (one host-only hash check excluded), matching final source/test hashes. E15 source prompts byte-identical and source responses parse; ambiguous old dialogue aliases rejected, not reinterpreted. App/fixture/env/historical snapshot unchanged, zero NVIDIA/DB calls or integration. | Hosted semantic improvement, fixed source-equivalence/no-op findings, cost/output-budget proof, full suite/browser/generation/approval/export, any new phase acceptance. P3.2–P3.4 remain unchecked; four-dialogue hypothesis check needs fresh bounded consent. |
| E17 — reviewed 2026-10-17 | Four-dialogue V3 check (`<QA_DIR>/qa-dialogue-v3-live-20261016/README.md`), frozen V3, four original responses and closed ledger beside it | Four newly authorized dialogue-only NVIDIA requests, no retry/repair/recovery, all HTTP 200/schema-valid/stop. One of two agreed defects recognized (file/link), Frostpeak progress defect missed despite supplied states; two no-op findings and 15/18 uncertain comparisons, neither valid control clean. Three exact source bindings, no selected states. 21,105 input/1,006 output tokens, mean HTTP 5.743 s; outputs 162–420 within 1024. Inputs byte-identical E15, app/fixture/env unchanged. Preparation mocked only to capture existing request; no mock source review counted as hosted, no DB/integration/generation/approval/export. Allowance closed/exhausted. | Useful/reliable review, causal schema diagnosis, general accuracy, source judgment/unknown resolution, full suite/browser/normal generation/approval/export or phase acceptance. P3.2–P3.4 remain unchecked; pause repeated hosted runs pending local diagnosis. |
| E18 — 2026-10-17 | QA prototype V4 (`<QA_DIR>/qa-targeted-review-prototype-20261016/README.md#v4e18--independent-dialogue-judgments-2026-10-17`), current external source/tests; frozen V3/E17 unchanged | Read-only replay confirmed the aggregated-verdict gap; five split-verdict cases failed before fix. QA-only dialogue checks now require independent source/state judgments with defect-first aggregation, dimension-specific witnesses and explicit questless null state fit. Both raw judgments/findings and uncertainty retained; permanent QA approval blocker unchanged. 48 focused guarded host checks passed (36 external prototype plus 12 frozen-control checks); all four E17 unsplit responses rejected without reinterpretation. Source-pass messages unchanged from E15; in-memory syntax passed. Hash check: 172 protected source/fixture/env/E15/E17 files unchanged. Zero NVIDIA/DB calls, production integration or new backend tests. Broader contract/critic selection interrupted without final summary, not a pass; lint/type/coverage tools unavailable, nothing installed. | Hosted semantic improvement, resolution of no-op/uncertainty/source-absence errors, causal field-order proof, 1024-token fit, full-suite/container/browser/generation/approval/export or phase acceptance. P3.2–P3.4 remain unchecked; all existing hosted ledgers closed. |
| E19 — 2026-10-17, reconciled in E21 | V4 four-dialogue comparison (`<QA_DIR>/qa-dialogue-v4-live-20261017/README.md`), frozen source, first responses and closed ledger | Four explicitly authorized NVIDIA requests, no retry/repair/recovery. All HTTP 200; both Frostpeak outputs truncated at 1024 and remained invalid/incomplete. Two CyberRakshak comparisons completed: one correct file/link finding plus five false/no-op findings, six exact source bindings. 21,269 input/2,828 output tokens, mean HTTP 21.848 s. Inputs byte-identical E17; model/wire settings unchanged. Host execution because Docker was off, not a container comparison. 172 protected files unchanged at run end. No DB, production integration, generation or approval/export. Results initially confined to the new QA folder; allowance exhausted/closed. | Useful full review, a complete two-defect detection rate, full-scope token fit, causal decoder proof, normal flow or any acceptance. V4 is parked; original truncated outputs are not repaired. |
| E20 — 2026-10-17, reconciled in E21 | Single-line union/flat diagnostic (`<QA_DIR>/qa-schema-ablation-20261017/README.md`), preregistered protocol, paired requests and closed ledger | Four newly authorized NVIDIA requests, no retry/repair; all HTTP 200/stop/schema-valid, no truncation. Per-case requests differ only in response schema. Valid file warning falsely labelled defect with no-change text under both schemas; valid raw model outputs identical. Both detect bad URL/file subject, but flat suggests changing the fixed interaction rather than correcting the selected text. 18,588 input/640 output tokens, mean HTTP 5.023 s. Offline cap/reference checks passed; 191 protected files unchanged at run end, including then-current MVP. No DB, environment/model/production changes or approval. Allowance exhausted/closed. | Flat-shape remedy, general decoder causality, reliable correction, Frostpeak/state reasoning, full generation/browser/approval/export or any acceptance. Only one response per cell; no silent label repair. |
| E21 — 2026-10-17 | `backend/app/design_agent/finding_reviews.py::create`, `review_policy.py::_resolved_indexes/_approval_projection`, existing frontend finding-review component and audit/approval tests | Local inspection plus guarded in-memory reproduction: a record selecting NPC name removed a model finding whose reference selected dialogue text. Replay used a synthetic server-provenance envelope only in memory; historical QA reviews were not promoted/persisted. Remaining system finding and Grounding/Completeness/Integration readiness blockers still present; QA provider origin rejected. No PostgreSQL, NVIDIA, persistent disputes or approval/finalization. Existing auth/stale/system/worker tests inspected; the guarded two-file regression run returned no summary and was interrupted, not a pass. Only MVP.md updated to reconcile E19/E20 and record B5; source/env/QA history unchanged. | Full approval bypass, semantic correctness of human judgments, a B5 fix, a passing regression suite, browser behavior or any acceptance. Next is the narrow field-binding fix; no critic authority change implemented. |
| E22 — 2026-10-17 | `backend/app/design_agent/finding_reviews.py::_finding_artifact_value/create`, `review_policy.py::_resolved_indexes`, existing approval regressions, frontend finding form/types/dashboard-state tests; QA screenshots (`<QA_DIR>/qa-b5-field-binding-20261017/`) | Three reproducing failures before fix. One validator enforces exact referenced field/current canonical JSON value at recording and replay; unrelated fields/stale references rejected, old mismatched records preserved but ineffective, legacy unreferenced handling preserved. UI locks valid reference paths in a wrapping read-only field and renders object JSON; malformed/missing targets fail closed. 66 guarded backend regressions passed on fresh in-memory SQLite; Windows sandbox socket-pair stall diagnosed, identical guard passed outside sandbox. 19 intercepted finding-review browser checks passed using installed headless Edge: legacy/scalar/object forms, mobile/desktop, light/dark, focus, auth/stale/system/proposal/evidence and invalid-reference boundaries. Final screenshots visually inspected; mobile path wrapping improved after inspection. TypeScript, targeted ESLint/JS syntax and production frontend build passed. Five backend cases and four browser cases added to existing suites; no new dependency, model/env change, NVIDIA call or real approval. Test-only dev server stopped. | Full backend suite/coverage, live PostgreSQL or normal backend/browser acceptance, hosted quality/source-scope resolution, actual generation/approval/export or any phase acceptance. Human judgment remains unverified semantically; old mismatched audits require a fresh critique. |

| E23 — 2026-10-17 | Actual frontend `/` and `/design-agent`; unavailable-backend screenshots (`<QA_DIR>/qa-backend-unavailable-20261017/`); `DashboardLayout.tsx`, `grounding.py`, finding-review schemas/policy/routes | Docker Linux engine pipe missing; no backend listener. Started the existing frontend on 127.0.0.1:3000 and inspected it with installed headless Edge, without intercepted responses. Both pages show workspace-unavailable rather than game data or false success; backend health/session GETs fail with connection refused and no page exceptions were observed. Error state has no horizontal overflow at 1440/768/375; light/dark screenshots visually inspected. Retry preserves the error and makes only health/session GETs. Keyboard Enter reproduction confirms focus returns to BODY after Retry; recorded as a P5.2 issue, not fixed. Browser MCP bridge was unavailable; CLI Edge used instead. Initial CLI theme lookup used visible text instead of the actual accessible label and timed out; corrected-label run passed. Source inspection confirms no source/scope decision action, while system completeness/grounding gates remain enforced. Only MVP and new QA screenshots changed this turn; frontend dev server left running for inspection. No NVIDIA calls, database changes, installs, approval/export or production-code changes. | Backend-up review/B5 verification, authentication/project persistence, fresh generation, full suite, hosted quality, approval/export, source/scope-policy implementation or any phase acceptance. Docker must be available before the isolated live journey can continue. |

| E24 — 2026-10-17 | Real Docker/API/dashboard; `backend/app/services/gdd_review_service.py`, `backend/test_gdd_reviews.py`; QA screenshots (`<QA_DIR>/qa-live-local-review-20261017-mvc5ylnm/`) | P0.1 accepted: backend/PostgreSQL/Chroma healthy, real dashboard accessible at documented localhost origin. 127.0.0.1 fails CORS as an unconfigured origin; no environment changes. Created only new workspace `qa-live-local-review-20261017-mvc5ylnm`; uploaded bundled Frostpeak through UI (document `ff78d212-22a6-416a-a8c3-451f6e99be84`, four chunks). Actual local review/consent modal/decline and reload persistence verified without mocked responses or agent-start requests; database confirms zero runs in new workspace. Found bare control/controls false coverage; two reproducing failures before narrowing the shared matcher. Six guarded source-review regressions passed, ten DB-fixture cases deselected; syntax/diff checks passed, lint/type/coverage tools unavailable and not installed. Actual API and UI re-review now show four open decisions, including Platform and controls, surviving reload; screenshots checked at desktop/768/375 without horizontal overflow. Read-only retained run `99845472-a8cb-42e4-8216-0c0a5f3af37e` loads draft/current system checks/raw critique/frozen evidence and preserves selected IDs after reload; invalid historical references stay unknown/stale, approval disabled, no review-record controls in anonymous local mode. Cross-workspace finding catalog returns 404; unapproved technical brief returns 409. Counts and row fingerprints unchanged for all 90 runs/63 artifacts/48 critiques/72 evidence snapshots/one finding audit before and after. Local mode has AUTH_REQUIRED=false; no authenticated claim. Direct negative-consent API probe was rejected by safety review before execution, not bypassed or counted as a pass. No NVIDIA calls, approval, successful export, installs, environment changes, commit/push or historical-data rewriting. | Full backend suite/auth baseline, complete P1.2 API-boundary proof, fresh hosted generation/critique, authenticated B5 recording/happy-path reference form, source/scope-policy implementation, semantic review reliability, successful approval/export, or MVP/other phase acceptance. Frontend and Docker stack remain running; missing-scope and Retry-focus issues remain open. |

| E25 — 2026-10-17 | Approved memory-only policy; existing run schema/config, provenance, workflow/provider/quality helpers, briefing service and dashboard forms; QA screenshots (`<QA_DIR>/qa-memory-scope-20261017-mvcd1z7e/`) | Added strict default-off `allow_unspecified_memory`, fixed at run creation and passed through generation/critique/revision and response/provenance. Only empty, uncited memory with a nonblank warning is unassessed; populated memory retains normal checks, other sections/recovery/independent findings still block, and runtime behavior is unchanged. Canonical requests omit false/missing flags to preserve legacy fingerprints. Final snapshots receive a server-owned memory marker only when eligible; brief and scorecard disclose Unspecified—not assessed, not verified source absence or complete memory design. New-run forms reset the option off. Three initial reproducing failures; v2 test fixture corrected to use its required empty rules list, and an older stale-reference audit expectation aligned with E22's existing 422 rejection (no production validator weakened). Final affected backend selection: 267 passed, three DB-fixture cases deselected, one pre-existing Starlette/AnyIO deprecation warning; PostgreSQL/external HTTP denied. Includes two fully mocked consent→generation→critique→revision→simulated design approval→brief flows, both contract versions, immutable old drafts, scope fingerprints and blocked runtime export. Full existing frontend state suite: 116 passed against final production build using intercepted backend responses/offline fonts; semantic-text contrast minimum 5.11:1 in that suite. Production build, TypeScript, targeted ESLint, JS/Python syntax and whitespace checks passed; no Python lint/type/coverage tool installed. Real production dashboard/API check created only new project `qa-memory-scope-20261017-mvcd7c19`, uploaded Frostpeak document `3fa8eca5-ad8a-4915-b475-6b28c6f49432` (four chunks), and verified default-off/reset/keyboard/decline/mobile fit with unmodified backend responses. New QA has four local decisions and zero agent runs; live API schema exposes boolean default false. Counts/row fingerprints unchanged for all 90 existing runs, 63 artifacts, 48 critiques, 72 evidence snapshots and one finding audit. Screenshots visually inspected. No NVIDIA request, actual approval/export, migration, environment/provider change, install, commit/push or historical QA rewrite. Production frontend remains running at documented localhost origin. | Full backend/PostgreSQL/auth baseline, fresh hosted generation/critique or memory-policy compliance, general source-absence/semantic-review accuracy, authenticated B5 recording, real approval/export, Unity or any new phase/MVP acceptance. Memory-only scope permission is not evidence that the GDD lacks memory rules. |

| E26 — 2026-10-17 | Isolated baseline evidence (`<QA_DIR>/qa-baseline-20261017/`), current dirty source at HEAD `9cea92a` (129 working-tree entries), fresh final production UI | First full run: 959 passed, six failed and one skipped; five missing GDD-fixture mounts corrected in QA, and the queue failure reproduced with two tests in order. Moved the existing queue-cleanup fixture from its test module into shared conftest; no application queue behavior or test count added. Enabled the installed AnyIO plugin; cleanup test now executes. Final complete default selection: 966 passed, one marked load test excluded, zero failures/skips, 92.58 seconds, exit 0, JUnit retained. Fresh internal-only PostgreSQL/Chroma, read-only source/docs, mock providers and verified outbound TCP denial; application/retained QA databases never used for resets or migrations. Browser investigation exposed noncanonical frontend decisions GET; one shared API URL now matches `/api/v1/decisions/`, and existing state fixtures reject the wrong path. Existing regression failed before the fix; final production build/TypeScript, full lint, syntax/whitespace and all 116 intercepted dashboard checks pass, minimum measured semantic-text contrast 5.11:1. Real authenticated production-UI walkthrough against QA backend passes registration/logout/login, workspace creation/switch/reload, actual Frostpeak upload (document `703aed8b-2cc9-41ed-b536-7a6c05a2cacf`, four chunks), local review/declined consent and persisted decisions; anonymous 401, nonmember 403 and cross-project document 404 verified. Browser-only API-base override and offline font stub; backend responses unmocked. Desktop/mobile screenshots inspected; zero page errors or unexpected external requests. Auth QA has zero agent runs, review events or blueprints; application history counts remain 90 runs/63 artifacts/48 critiques/72 evidence snapshots/one finding audit. Temporary QA services stopped, normal app/frontend still healthy/running. Ponytail reused existing fixtures/checks with no new feature/dependency/test case. | Fresh NVIDIA generation or memory-policy compliance, content usefulness/state-fit, trustworthy semantic critique, authenticated B5 current-draft recording, real approval/export, public deployment/SMTP, load benchmark, Python lint/type/coverage tools or Unity. No hosted requests, persistent environment/model changes, install, commit/push or historical QA rewrite. Only Phase 0/local baseline accepted; MVP remains NOT ACCEPTED. |

| E27 — 2026-10-17 | `nvidia_provider.py::_revise_dialogue`, existing `test_dialogue_revision_flow.py`; full-suite logs/JUnit (`<QA_DIR>/qa-dialogue-state-20261017/`), guarded regression JUnit (`<QA_DIR>/qa-dialogue-state-20261017-offline.xml`) | The retained Frostpeak progress assertion already fails existing local quality checks; no new classifier or model/prompt experiment added for it. Related legacy defect reproduced: dialogue-only input omitted stored eligibility, and rebuilding its compact response discarded that eligibility; renamed/omitted state-bound triggers were accepted. Three meaningful reproducing failures before fix. Existing predicates now enter read-only model context, are restored server-side by exact trigger ID, and cannot disappear through renamed/omitted bound triggers. Compact response schema remains unchanged; legacy untyped shape, quests, profiles, unrelated sections, proposal labels and approval gates retain their handling. Current v2 dispatch/assembly unchanged. Reused two existing regression functions with three additional parameter cases, no new module/dependency. Overlapping guarded host selection: 255 passed, three DB-fixture cases deselected, one existing Starlette/AnyIO deprecation warning; PostgreSQL/external network forbidden. Final complete standard backend suite on new internal-only PostgreSQL/Chroma with read-only source/docs: 969 passed, one marked load test excluded, zero failures/skips, 95.38 seconds, exit 0. Includes final manual-check/schema assertions and existing v2/workflow/auth/approval regressions. Syntax/whitespace checks pass. Existing app health remains healthy/local_demo with configured NVIDIA provider unchanged; no hosted request, environment/model change, persistent design update, install, approval/export or commit/push. Temporary QA services stopped; logs/JUnit retained. Ponytail limited production work to the existing legacy helper and reused the existing safe test runner. | Fresh current-v2 generation/revision usefulness, voice quality, hosted critic accuracy, real dashboard revision/approval/export, production deployment, load benchmark, Python lint/type/coverage or Unity. No frontend changes or new browser/build run this turn; E26 evidence retained. Phases 2–3 and MVP remain unaccepted. |

| E28 — 2026-10-17 | Fresh dashboard QA assessment (`<QA_DIR>/qa-frostpeak-normal-20261017/assessment.md`), closed ledger, raw requests, failed run/trace and desktop/mobile screenshots beside it | Real production UI with browser-only QA API-base override, unmocked backend responses and offline fonts. New isolated PostgreSQL/Chroma only; actual Frostpeak upload indexed four chunks. Local review and declined consent made zero NVIDIA calls. Standard form requested two NPCs/two quests, fresh three-stage speech, design-only deferral and pre-run memory-unspecified choice; no injected draft. Run `d2a3ce3f-050f-45d5-b358-976264eb7b01` failed at plan: configured `nvidia/nemotron-3.5-lightning-30b-a3b` made three attempts, each ReadTimeout (90,241/90,178/90,159 ms), 272,119 ms plan duration, HTTP 503. No HTTP response or token/cost usage available. Configured generation tier `nvidia/nemotron-3-super-120b-a12b` never called; mock fallback disabled, original limits unchanged. Six-request allowance closed at 3/6 used; unused requests not reusable. Failed run/trace survives reload; no approval available, zero page errors/no horizontal overflow. Initial consent remains open over error and saved run is absent from history until reload; trace renders unknown usage as zero (B7). QA has one run and zero artifacts/critiques/evidence snapshots/review events/blueprints; existing app counts unchanged (90/63/48/72/one finding resolution), nine protected source/config hashes unchanged. Temporary QA services stopped with named volumes/evidence retained; normal app/frontend remain running. No production code, model/environment, historical workspace, install, approval/export or commit/push change. | Root cause of provider timeout or key validity; any generated content, critique quality, memory-policy compliance, revision, real approval/export, new full-suite/build proof, public deployment or Unity. B1/B2 remain unresolved; Phase 1 hosted start blocked and MVP NOT ACCEPTED. |

| E29 — 2026-10-18 | Failed-start recovery verification (`<QA_DIR>/qa-failed-start-20261017/README.md`), regression JUnit/logs, browser result and final screenshots beside it | B7 reproduced before fix: two backend cases lacked a persisted run ID; browser consent stayed open. HTTP 503 now retains failure semantics and returns safe message/run_id. Both internal start callers close consent and expose the scoped failed run; the advanced page selects its URL/history/trace and focuses the error. No automatic generation retry. Failed follow-up reads preserve setup and recovery URL; no-draft copy and unavailable/partial/measured-zero usage are honest. Reused ApiRequestError and existing test modules; no new production module/dependency. Overlapping targeted backend selection: 68 passed (21 existing Chroma/Pydantic warnings). Complete standard suite: 971 passed, one marked load test deselected, zero failures/skips, 116.79 seconds, exit 0, on verified empty disposable PostgreSQL with read-only source/docs and outbound-blocked network. Final frontend lint/build/TypeScript and all 125 intercepted dashboard checks pass. Separate actual Frostpeak upload (four chunks) and real API/browser walkthrough: both start surfaces at 375/1440 px, four forced-local planner failures, authoritative failed IDs, reload/trace/no duplicate start, zero page errors/overflow; final production UI inspected read-only. QA has four failed runs, zero artifacts/review events/hosted requests. App counts remain 90 runs/63 artifacts/48 critiques/72 evidence snapshots/one finding resolution; original .env hash unchanged. QA services stopped with containers/data/evidence retained; normal app/final production frontend running. | NVIDIA availability or cause of E28 timeouts; useful generated content, reliable semantic critique, live approval/export, authenticated B5 finding recording, production deployment/SMTP, excluded load benchmark, Python lint/type/coverage or Unity. QA API uses a deliberate local failure provider, not NVIDIA. External consumers assuming string-only 503 detail were not exercised. B6 and broader phase/MVP gates remain open; MVP NOT ACCEPTED. |

| E30 — 2026-10-18 | Planner availability diagnosis (`<QA_DIR>/qa-planner-diagnosis-20261018/README.md`), connectivity summary, two-send runner and closed raw ledger beside it | B6 diagnosed without production changes: Windows/backend/fresh E28-network container pass DNS/TLS 1.3 and nine catalogue GETs (all HTTP 200, 105–184 ms), both configured models listed. Catalogue is also public, so those GETs alone prove no key validity. Backend keys match current .env with no whitespace/control characters; original environment hash unchanged. Fresh user-approved two-inference allowance enforced one send per synthetic probe, no database access, retry, repair or fallback. Configured Lightning planner returns exactly OK in 63,023 ms, HTTP 200, 21 input/2 output/zero reported reasoning tokens. Normal existing planner adapter with synthetic objective/source still times out at 90,102 ms with no HTTP response; its normal retry is stopped locally by DiagnosticLimit, not mistaken for the original ReadTimeout. Allowance closed 2/2 used. No GDD transfer, artifact, approval/export, model/environment-file or production-code change. NVIDIA's official AI-Q guidance documents hosted Lightning elevated latency/timeouts under high demand; upstream availability is a supported hypothesis, not incident proof. Backend healthy; stopped frontend's existing production build restarted outside the restricted sandbox, HTTP 200 at localhost and 127.0.0.1. Diagnostic containers exited; evidence retained. | Exact endpoint-side cause, general network reliability, Super inference/key validity, normal GDD generation, useful content, critique, approval/export, fresh full suite/build/browser acceptance or Unity. Earlier E29 baseline remains historical; no phase acceptance added. B6 remains open, MVP NOT ACCEPTED. |

| E31 — 2026-10-18 | Planner comparison and fresh Frostpeak assessment (`<QA_DIR>/qa-planner-comparison-20261018/assessment.md`), original/continuation closed ledgers, saved run/trace/evidence and browser screenshots beside it | Eight authorized sends: two Lightning synthetic ReadTimeouts at 90.161/90.140 s; two Nano Omni valid nine-query plans at 1.931/5.847 s, strict eight-word failures retained. User explicitly waived only that QA continuation check. Process-only Nano Omni normal plan 5.654 s, unchanged Super generation 38.342 s; critique truncates at 1024 then existing doubled-cap retry completes in 7.770 s with zero findings. Ordinary production form/real QA API, unchanged Frostpeak upload/four chunks, pre-run scope/consent, no injected draft. Run `e9f7f107-ceb4-45c8-b730-8e87de920615`, artifact `5916da56-19da-4321-9c22-c84b9536543f`, awaiting_review in 78.43 s. Four source-supported sections omitted despite full evidence/objective input; requested failure/restart absent; Eldrin progress false when flag raised first. Pure local helper replay confirms phrase miss; final critic misses it and omissions. Mining full-five completion retained but objective numeral missing. Local enrichment needs_revision, score 0.4643, approval disabled. Saved IDs/status survive browser reload; real API GETs, offline fonts/browser-only API-base override, only closed-harness CORS preflight stubbed on read-only revisit, zero page errors/mobile overflow. New QA one run/draft/critique/snapshot, zero reviews/blueprints. Existing app counts 90/63/48/72/one resolution unchanged; .env hash unchanged, 129 dirty entries preserved. QA services stopped with data retained, app/frontend healthy. | Production planner promotion/reliability, general retrieval accuracy (normal candidate queries drift/overrun), useful content or reliable critic, successful revision/approval/export, authenticated finding recording, fresh full suite/build, deployment or Unity. Model/environment and production code unchanged; only MVP updated in repo. Six responding sends total 17,496 input/3,521 output tokens; timeout usage and all costs unknown. Allowance closed 8/8; no phase accepted, MVP NOT ACCEPTED. |

| E32 — 2026-10-18 | Content-first correction assessment (`<QA_DIR>/qa-content-first-fix-20261018/assessment.md`), red/green/full-suite JUnit, closed ledger, original/revised traces and browser screenshots beside it | Two deterministic gaps fixed in existing code: consolidate the active v2 rubric (coverage/explicit proposal permission/state-fit) and reuse named generation section types for non-record revision. Two existing regression functions extended, both red before fix; final 343 affected checks pass, three DB-fixture cases excluded. Complete standard suite 971 passed/one marked load test excluded/zero failures-skips, 120.14 s, fresh disposable internal-only PostgreSQL/Chroma; no count/module/dependency growth. Fresh six-send authorization uses five: Nano Omni plan 4.581 s, unchanged Super generation 38.376 s/critique 7.450 s; revision 24.219 s truncates at 2048, existing 4096 retry 33.472 s. Ordinary dashboard form/consent, no injected artifact; run `e4f63653-1949-48b8-b8dc-366e67c17e8e`, draft `65767c4a-d19b-4368-8291-106e7077c6b4`. Lore/art/proposals improve, summary/gameplay still omitted; critic emits two no-ops/misses defects. Revision leaves summary/NPC/quest material unchanged; existing gate returns HTTP 500 and rejects partial candidate, no new draft/critique. Original draft/critique preserved exactly after real GET/browser reload; failure visible, approval unavailable, zero page errors/mobile overflow; only closed-harness OPTIONS preflight/offline fonts stubbed. QA one run/draft/critique/snapshot/rejection, zero blueprints; app counts 90/63/48/72/one resolution and .env hash unchanged. QA stopped/data retained; app/frontend healthy. | General generation/revision/critic reliability, successful correction/approval/export, production candidate promotion, semantic coverage from schema or causality from one sample, fresh frontend build/full accessibility/CORS/auth/Web Vitals, unavailable Python lint/type/coverage, deployment or Unity. 22,911 input/7,413 output tokens, cost unknown; ledger closed 5/6, unused send not reusable. Model/environment unchanged; no phase accepted, MVP NOT ACCEPTED. |

| E33 — 2026-10-18 | Cleanup regression JUnit and pre-edit backups (`<QA_DIR>/qa-repo-cleanup-20261018/`) | Ponytail cleanup removed two unused helpers, merged the redundant NVIDIA completion wrapper and removed one duplicate import: 39 fewer Python lines, no new tests/dependencies. Three root docs shortened by 457 lines; unsafe app-container pytest instructions replaced. Local virtual environments/debug log ignored, not deleted. Complete standard suite: 971 passed, one marked load test excluded, zero failures/skips, 118.88 s on fresh disposable internal-only PostgreSQL/Chroma; QA services stopped/data retained. Documentation links and whitespace checks pass; .env hash unchanged, existing dirty work preserved, API healthy. No hosted request, model/environment change, approval/export, commit or push. | Generated-content quality, reliable critique/correction, real approval/export, frontend/browser acceptance (localhost:3000 unavailable at final check), Python lint/type/coverage or Unity. B1/B2 and phase gates remain open; MVP NOT ACCEPTED. |

| E34 — 2026-10-18 | Chunk 1 execution contract in this document; E31/E32 retained evidence and current review-policy/config inspection | Fixed baseline cases, output/revision expectations, Omni/Super target pair, advisory critic/human-adjudication boundaries and Chunk 2 handoff. Existing phase/checklist IDs retained; no product box closed. Documentation links/policy assertions/whitespace checked; existing .env unchanged. No application code, tests, dependencies, provider calls, database, runtime approval, commit or push changes. | Deployed routing, implemented advisory policy, improved generated content, correction, browser journey or approval/export. These remain implementation/acceptance work; MVP NOT ACCEPTED. |

| E35 — 2026-10-18 | Chunk 2 local QA: pre-edit backups, red/green/full-suite JUnit and UI screenshots (`<QA_DIR>/qa-chunk2-20261018/`) | Reproduced lost v2 revision-task guidance; restored correction/unchanged-field/rejected-prerequisite instructions in the existing rubric. Saved E32 response still rejected for unchanged NPC/quest/summary; old artifact preserved. Existing bound human adjudication reused; advisory/system-check distinction clarified in one UI paragraph, no approval-policy relaxation. One existing regression extended: 249 affected passed/three DB-fixture cases excluded; full standard suite 971 passed/one marked load test excluded/zero failures-skips, 113.36 s, fresh internal-only disposable DB/index. Lint/build/TypeScript and all 125 intercepted dashboard checks pass; mobile panel inspected, minimum tested semantic-text contrast 5.11:1. Omni applied to planner only, duplicate planner entry removed; running backend model IDs verified, all non-model .env content unchanged. App counts remain 90/63/48/72/one resolution; health healthy, frontend HTTP 200. QA services stopped/data retained. No new test functions/modules/dependencies, NVIDIA calls, runtime approval/export, commit or push. | Fresh generation/correction usefulness, hosted query/review reliability, real human finding adjudication/approval/export, Python lint/type/coverage, production deployment or Unity. Six-request live check requested but not yet authorized/executed this turn; previous allowances remain closed. Chunk 2 is not complete; B1/B2 and MVP remain unaccepted. |

| E36 — 2026-10-18 | Chunk 3 QA: pre-edit backups, reproduced export failure, targeted/full-suite JUnit and revision-scope screenshots (`<QA_DIR>/qa-chunk3-20261018/`) | Reproduced live decision/source-label drift in an approved mock brief. Agent brief now reads immutable final content, scoped frozen excerpts and recorded run decisions, includes artifact/snapshot IDs and source quotes; absent snapshot returns 409. Preview export also reads final content; ordinary local briefs unchanged. Existing regression proves later source/decision/blueprint edits cannot replace approved design or preview content. Reproduced dashboard reject payload missing artifact ID; both review actions now send the displayed ID and reject absent drafts, reusing existing stale-version enforcement. Final full standard backend suite 971 passed/one marked load test excluded/zero failures-skips, 117.41 s; earlier overlapping selection 97 passed. Fresh disposable internal QA services stopped/data retained. Frontend lint/build/TypeScript and four focused intercepted revision-scope checks pass at 375/1440 px; no new test functions/dependencies. Reloaded normal API: failed-run brief/runtime GETs 409, cross-project brief GET 404; app counts 90/63/48/72/one resolution and .env hash unchanged; health healthy/frontend 200. No NVIDIA, existing-workspace approval/revision, runtime materialization, commit or push. | Useful hosted generation/correction, real positive generation → review → approval → export journey, full 125-case frontend rerun this turn, Python lint/type/coverage, production/Unity or MVP acceptance. Chunk 3 live acceptance remains blocked by Chunk 2; no phase box closes. Briefs now include frozen GDD excerpts and should be reviewed before external sharing. |

| E37 — 2026-10-18 | Fresh Chunk 2 normal-flow check (`<QA_DIR>/qa-frostpeak-chunk2-live-20261018/assessment.md`), raw closed ledger and browser evidence beside it | Real isolated upload/local review/decline/explicit consent/start using unchanged Frostpeak, production dashboard and selected Omni/Super pair. Planner initial attempt plus two configured retries return HTTP 503 (698/4713/312 ms). Failed run 76e74852-0548-40df-97aa-dca0d5c3b367 persists; reload at 375/1440 px retains safe failure/trace with no page error/overflow. No artifact, critique, snapshot, revision, approval or export; Super never called. Planning sends no GDD excerpts. Allowance closed 3/6, unused three not reusable. Application counts and ten protected hashes unchanged; isolated services stopped/data retained. | Original 503 bodies were not retained; no incident cause inferred retrospectively. No content-quality, key/Super reliability, useful correction or phase acceptance. |

| E38 — 2026-10-18 | Two-send capacity diagnosis and focused client fix (`<QA_DIR>/qa-omni-503-diagnosis-20261018/assessment.md`), closed raw ledger, pre-edit backups and regression JUnit beside it | Fresh authorized synthetic-only diagnosis, one send per probe/no DB/retry/repair: Omni tiny prompt HTTP 200/654 ms; normal planner HTTP 503/512 ms with ResourceExhausted worker local request-limit error (202/16), no Retry-After. Full sanitized response retained privately in QA, not public traces. Allowance closed 2/2; no GDD transfer, model/environment change or approval/export. Existing provider now preserves safe HTTP status, honors short Retry-After and stops retrying when server cooldown exceeds existing two-second wait cap; no added dependency/config/fallback or response-body exposure. Red regression reproduced ten failures; 75 affected tests pass offline with DB/network denied. Full-suite result recorded in the linked assessment after completion. | Client handling cannot repair hosted capacity. Successful generation/critique/correction and positive approval/export remain unproved; load benchmark, Python lint/type/coverage, frontend/browser rerun and Unity not checked this turn. MVP NOT ACCEPTED. |

| E39 — 2026-10-18 | Recovery chunk 1: exact saved-revision diagnosis (`<QA_DIR>/qa-revision-root-cause-20261018/assessment.md`), guarded replay/result, affected and integration JUnit beside it | Full rejection reason reaches both original revision sends exactly; payload/schema unchanged through 2048→4096 truncation retry. Four frozen chunks preserve explicit premise/quantity evidence. Final stop response is schema-valid but summary/NPC/quest design remains unchanged (quest assumption labels only); narrative/gameplay changes retained by current replay. Material gate intentionally rejects partial correction and saved artifact stays exact. Hypothetical summary-only positive control survives pipeline, explicitly not hosted/acceptance output. 65 offline checks pass/three DB-fixture exclusions; five existing PostgreSQL integration cases pass on verified-empty internal-only QA storage (10.30 s), covering partial rejection and valid mocked persistence/re-critique/restart/scope. QA stopped/data retained. Ponytail: zero production/test-suite/config/model/env changes or added backend tests/dependencies; only tracker and external QA evidence updated. No NVIDIA calls or approvals. | Why the model ignored instructions, fresh effect of E35 guidance, general model/RAG/content reliability, browser/full-suite/static Python checks, positive hosted approval/export or Unity. Recovery diagnosis is complete, not the correction feature or MVP; B1/B2/B6 remain open. |

| E40 — 2026-10-18 | Fresh useful-flow attempt and empty-citation material-change fix (`<QA_DIR>/qa-frostpeak-recovery-live-20261018/assessment.md`), closed ledger, original/revised content/traces, red/green/full-suite JUnit and browser screenshots beside it | Real normal dashboard upload/local review/decline/consent on fresh QA storage; current Omni/Super pair, six HTTP 200 sends including one revision truncation retry, no JSON repair/fallback/model/env change. Fresh version 2 improves lore, Kaelen progress and restart prerequisites but still has empty summary/missing mining numeral. Raw revised critic misses both; server blocks approval. Citation-only repair of empty summary incorrectly counted as material change; reused existing content-presence check to fix it in one condition, extending one existing test without backend test-count growth. Exact saved response red before/green after, 135 affected offline passed/three DB-fixture exclusions. Full-suite result in linked assessment after completion. Real desktop/mobile reload preserves unapproved version 2, zero page errors/overflow; no approval/export/runtime action. Ledger closed 6/6, 29,475 input/7,985 output tokens, cost unknown. Historical artifacts unchanged; no claim of content acceptance. | Useful complete correction, reliable critic/source coverage, fresh post-fix hosted rejection, positive approval/export, general reliability/deployment, Python lint/type/coverage or Unity. Further flow changes need a specific design decision, not another blind batch; MVP NOT ACCEPTED. |

| E41 — 2026-10-18 | Field-level revision implementation and local checks (`<QA_DIR>/qa-field-revision-20261018/assessment.md`), pre-edit backups, full-suite/control JUnit and saved-data control metrics beside it | User requested the narrower fix after E40. V2 revision emits bounded allowed-path replacements; applies atomically to a copy, rejects unknown/overlapping/direct identity/state edits, then reuses full assembly/frozen citations/runtime checks. Objective text edits preserve state keys; omitted fields unchanged. Legacy-v1/canonical/API contracts and all approval gates retained. Retired full-section v2 revision prompt branches removed; net 64 production lines across three existing files, no new dependency/module/model/env setting. One focused backend regression added and existing fixtures adapted. Full standard suite 985 passed/one marked load test excluded/zero failures-skips, 88.89 s, fresh internal-only disposable storage. Two final guarded controls pass (one overlaps full suite); authored Frostpeak correction 617 characters versus 4755 full-section payload, original data/other sections preserved. No NVIDIA/approval/export or historical repair. | Fresh NVIDIA grammar/compliance/latency, useful generation/correction/critic, positive real approval/export, frontend/browser rerun, Python lint/type/coverage, load benchmark, deployment or Unity. Smaller wire is implementation/local proof, not semantic acceptance; MVP NOT ACCEPTED. |

| E42 — 2026-10-19 | Fresh field-revision assessment (`<QA_DIR>/qa-field-revision-live-20261019/assessment.md`), closed raw ledger, exact saved replay/JUnit, traces and browser screenshots beside it | Real isolated Frostpeak upload/four chunks/local review/decline/consent; unchanged Omni/Super pair, four HTTP 200 sends, no retry/repair/truncation. Initial draft omits source-supported sections; raw critic falsely clean. New field reply fills prose but ignores NPC/quantity edits, cites wrong lore chunk, and returns four action objects instead of required strings. Existing post-merge validation rejects atomically; original version 1/critique retained, failed run visible, approval unavailable. Native Any replacement shape limitation confirmed offline. Fresh 37 affected regressions and one external saved-response replay pass; E41 recorded full-suite 985 pass read, not rerun. Desktop/mobile reload has zero page errors/overflow; no approval/export. App counts/env unchanged; QA stopped/data retained. Ledger closed 4/6; 15,120 input/3,232 output tokens, cost unknown. No production code/test-suite growth/model/env changes. | Useful correction, reliable generation/critic/citation entailment, positive approval/export, general availability, fresh full-suite/build, full a11y/CORS/auth/CWV, deployment or Unity. Type guidance is next local work, not an implemented semantic fix; no phase accepted, MVP NOT ACCEPTED. |

| E43 — 2026-10-19 | Typed field-replacement implementation/checks (`<QA_DIR>/qa-field-types-20261019/assessment.md`), red/green/full-suite JUnit, exact saved-response replay and pre-edit backups beside it | Existing scoped revision annotations/constraints now type path replacements, including null/empty values; same wire/scope/assembly/source/material/approval boundaries. One production file net 19 lines; one existing regression extended, no new backend cases/dependencies/modules/config/models/prompts. Exact E42 invalid objects rejected before assembly, mocked native transport one call/no repair, valid action assembly passes. 172 affected checks pass; final overlapping 38 pass; full standard suite 985 passed/one load test excluded/zero failures-skips, 108.66 s on fresh verified-empty internal-only storage. Zero hosted requests, no saved content repair/approval/export. | NVIDIA schema support/decoding latency, useful corrections/citation entailment, trustworthy critic, positive approval/export, browser/build/static Python/coverage/load benchmark, deployment or Unity. E42 schema grows 6240→26895 JSON characters/21 type groups; no inference-cost claim. MVP NOT ACCEPTED. |

| E44 — 2026-10-19 | Fresh typed-schema assessment (`<QA_DIR>/qa-typed-field-live-20261019/assessment.md`), closed raw ledger/schema, offline branch replay and outcome beside it | File-only current-adapter QA, exact E42 first revision messages/frozen draft/four excerpts, only schema changed; unchanged Super/cap. One HTTP 200/18.208 s/stop, 5186 input/809 output tokens, no retry/repair/truncation. Native JSON Schema conforms (installed Ajv); existing local readability rejects three JSON-pointer failure-action strings. Eldrin/mining edits unchanged, Kaelen edit omitted, new prose uncited; no assembled candidate/material acceptance/critic/approval/export. DB access denied, app counts/env unchanged; no production-code/backend-test growth. Allowance closed 1/3, unused slots not reusable. | Useful corrections, citation entailment, reliable critic, normal dashboard journey, general NVIDIA reliability/decoder causality, approval/export, fresh suite/build/browser or Unity. Structural compatibility for one response only; MVP NOT ACCEPTED. |

| E45 — 2026-10-19 | One-field correction/review experiment (`<QA_DIR>/qa-focused-correction-20261019/assessment.md`), offline controls/postcheck, closed ledger and actual candidate/critic beside it | QA-only exact one-field schema from existing types (666 characters), read-only voice/eligibility/quest context, three incomplete-state examples, same frozen Frostpeak inputs/Super. Correction 2.188 s; schema/assembly/material/scope pass. Only text and two derived mirrors change; unrelated data exact. Manual review does not accept flag awaiting resolve as clearly state-neutral; no universal-falsity claim. Critic misses ambiguity and emits a confirmed already-satisfied memory recommendation; existing truncation retry consumes third send. Closed 3/3; 13,759 input/1399 output tokens. No production-code/backend-test/dependency/model/env/DB/approval/export change; original app counts preserved. | Useful accepted correction, source/citation fixes, trustworthy critic, full dashboard journey, causal attribution to schema/context/model, full-suite/build/browser/Unity or phase acceptance. Failed hypothesis not promoted to production; MVP NOT ACCEPTED. |

| E46 — 2026-10-19 | Normal dialogue-route fix and reviewed iteration (`<QA_DIR>/qa-dialogue-flow-fix-20261019/assessment.md`), red/affected/full-suite JUnit, closed ledger and actual before/after/critic/postcheck beside it | Reused compact dialogue helper for eligible v2 corrections, kept task-specific rubric/read-only state/closed schema/governed no-repair and final gates. One production file net 7 lines; existing tests extended, count unchanged. Full standard suite 985 passed/one load excluded, 100.97 s. Actual provider first fails, reviewed feedback produces second state-neutral line; exact preservation outside speech/two derived mirrors. Separate critic completes but memory no-op/source coverage failures remain. Closed 3/6, 14,963 input/822 output tokens. App data/env unchanged, no approval/export. New disposable resources auto-remove; read-only Docker audit explains 109 old QA containers/20 networks, cleanup choice separate. | General correction/critic reliability, sourced Watchtower quest-beneficiary claim, quantity/citation fixes, final human design acceptance, positive full dashboard approval/export, browser/build/static Python/coverage/load/Unity. Focused state-fit proof only; MVP NOT ACCEPTED. |

| E47 — 2026-10-19 | Dashboard quality and recovery assessment (`<QA_DIR>/qa-dashboard-quality-20261019/assessment.md`), red/green/final JUnit, closed live ledger, saved run/trace/screenshots and isolated DB archive beside it | Critic no-op/task-boundary fix; source-derived amount guard reuses quest parser; bounded rejected-revision recovery across workflow/API/queue/UI. Existing tests extended, no backend case-count growth. Final standard suite 985 passed/one load excluded, zero failures/skips, 104.63 s; lint/build/TypeScript pass. Real browser upload/local review/consent, 503 planner retry then generation/critique/revision; source/quest correction still fails quality. Original draft preserved across desktop/mobile reload; no approval/export. Closed 5/8, 14,948 measured input/2,506 output tokens, failed-send usage/cost unknown. App counts/env unchanged; new temporary resources removed after SQL archive. | Reliable critic/source/correction quality, full positive hosted approval/export, current browser proof of the recovery patch against live NVIDIA, automatic repair of old failed runs, full accessibility/CWV/static Python/coverage/load/deployment/Unity. No phase accepted; MVP NOT ACCEPTED. |

| E48 — 2026-10-19 | Bounded Frostpeak completion-check assessment (`<QA_DIR>/qa-frostpeak-complete-20261019/assessment.md`), closed ledger, two actual runs, correction traces/screenshots, frozen replay, JUnit and isolated SQL archive beside it | Closed 16/16 including three timeouts/two planner 503s; two fresh normal dashboard runs/two explicit corrections in one isolated workspace, unchanged Nano Omni/Super pair. Reproduces source omission, critic false absence/false positives and ignored quest/system corrections. Actual citation/material rejections return 409 with original draft/critique preserved in awaiting_review; E47 recovery now live-verified. Schema-context hypothesis failed acceptance and was removed; zero net production/test-code or dependency growth. Suite during experiment 985 passed/one load deselected, 101.41 s; final restored affected checks 163 passed, 12.57 s. Measured usage 146,565 input/15,700 output tokens; failed-send usage/cost unknown. App counts/env unchanged; only new disposable resources removed after archive. | Required useful corrected content, critic reliability and positive approved/exported deliverable were NOT achieved. No approval, runtime action, new consent, phase acceptance, fresh frontend build/mobile/a11y/deployment/load/Unity claim. |

| E49 — 2026-10-19 | Compact-flow progress and actual outcomes (`<QA_DIR>/qa-compact-flow-20261019/progress.md`), closed ledger, frozen checks, actual dashboard run/evidence/trace/screenshot, regression/full-suite JUnit and SQL archive beside it | Smaller existing typed correction/critic contracts; source omission anchors remain mandatory. RED/GREEN fixes for wrongly seeded summary and stable objective identities; offline replay of actual generation evidence. Final full suite 985 passed/one load deselected, 100.77 s; case count unchanged. Fresh browser flow reaches real generation/critique but content fails; known-bad approval remains blocked. Closed 11/12 sends including two planner 503s; unchanged app counts/env/models. Own five temporary containers/two networks removed after DB archive; old Docker inventory untouched. | Complete semantic correction, reliable critic, fresh hosted proof of final summary fix, preserved quest quantities, useful approved/exported content, CyberRakshak acceptance or any phase/Unity completion. All four chunk acceptance gates remain open; MVP NOT ACCEPTED. |

| E50 — 2026-10-20 | Source-fact repair, review iterations and live blocker (`<QA_DIR>/qa-source-facts-20261020/progress.md`), RED/GREEN JUnit, final full suite, metered ledger, real failed dashboard run/trace/screenshot and isolated SQL archive beside it | Explicit quest objective/reward/source IDs constrained in native and local response contracts; conflicting rewards fail, invalid output is not silently rewritten. Review reproduced inferred-level missions becoming fixed facts; explicit-only parser mode fixes that and supports reordered table columns. Existing parser callers retain default behavior. Final suite 986 passed/one load deselected, 71.60 s; affected selection 161 passed, overlapping. Actual UI upload/local review/consent/plan/retrieval pass; generation receives provider 404 before content. Two requests used; ten remain under the same active batch. App records/env/models unchanged. | Fresh successful generation/correction/critique, action-threshold semantics, reliable critic or positive approval/export/CyberRakshak/Unity acceptance. No content/approval created. Local fixes cannot resolve external model/account access. |

| E51 — 2026-10-20 | Same QA batch continuation (`<QA_DIR>/qa-source-facts-20261020/progress.md`), closed 12-send ledger, replacement probe, second/third browser runs/traces, provider JUnit and final SQL archive | Authorized model replacement after Super 404. Nano unchanged; 3.5 Super native probe works, full native request fails 500 across three attempts. Existing prompt-schema mode produces a complete typed Frostpeak draft with correct source premise, independent Ash Pass actions, explicit five-chunk objective/action and exact source rewards. Separate critique truncates at its unchanged limit; hard meter prevents send 13. Saved `.env`/template artifact model and formatting flag only, all other environment values/keys verified unchanged; backend recreated and effective routes verified without inference. Existing provider/contract checks 120 passed, 7.96 s; no production-code/test-case additions this continuation. | Reliable critique or correction, accepted dialogue (Kaelen still says delivered), successful approval/export, CyberRakshak, general availability or Unity. Critic fragment has false-positive concerns, not a complete independent review. No approval/runtime/export occurred. Shared allowance closed 12/12; no further calls authorized. |

| E52 — 2026-10-21 | Bounded completion-check evidence (`<QA_DIR>/qa-complete-review-20261021/progress.md`), RED/GREEN/full-suite JUnit, two real browser run/trace/screenshots, closed ledger, saved correction replay and isolated SQL archive | Two small local fixes: mixed dialogue plus assumptions/eligibility/notes requests retain the full section contract; malformed review JSON gets one fresh original-input retry, never invented references or repaired findings. Failed prompt/schema-description experiment removed. Final suite 989 passed/one load deselected, 84.95 s; three case items added. Hosted send 12 corrects Kaelen speech; replay preserves Eldrin, eligibility and unrelated sections. Identical revision payload returns three 500s at 2,048 tokens, then 200 at 4,096; one comparison, not a proven minimum or saved configuration change. Closed 12/12, no approval/export. | Reliable critique, accepted quest failure rules, successful dashboard correction/approval/export, CyberRakshak or Unity. Raw reviews include false positives, draft-as-source quotes and a section/path mismatch. Final approval checks also reject the unchanged mining failure rule. The saved correction is not a reviewed/approved artifact. |
| E53 — 2026-10-21 | Four-gate evidence and adjudication (`<QA_DIR>/qa-four-gates-20261021/progress.md`), final backend/affected JUnit, two actual browser failures/traces/screenshots, original hosted responses, saved replay diagnostics, closed ledger and isolated SQL archive | Fresh critic selects existing fields/frozen excerpt indexes; server derives section/value/source ID/full excerpt, preserving raw findings and old stored reviews. A hosted whole-record path failure reproduced locally and fixed without relaxing exact binding; legacy revision paths unchanged. Final standard suite 990 passed/one load deselected, 88.24 s; affected 186 passed; only one backend test case added. New allowance closed at 10/24: four planning sends across two failed dashboard starts, two directed critiques and four revision/repair sends. Second directed critic is schema-valid but has eight false/no-op findings; no semantic success. Both directed corrections/repairs malformed and rejected. | Four requested gates, accepted quest correction, reliable source/coverage judgments, normal-flow correction/approval/export, CyberRakshak or Unity. No artifact/critique inserted into QA runs; two failed runs/zero artifacts/zero approvals. Saved environment/models/keys/token limits and application counts unchanged; temporary services removed after SQL archive. |
| E54 — 2026-10-21 | Revision/acceptance evidence (`<QA_DIR>/qa-revision-fix-20261021/progress.md`), approved technical brief (`<QA_DIR>/qa-revision-fix-20261021/frostpeak/technical-brief.md`), red/green/final JUnit, real UI run/revision/approval/export records, closed cumulative ledger and SQL archive | Reuses existing typed field assembler; repair must preserve all patch values. Source-fact constraints retained; known source-rule failures surface as server blockers before approval. Critic retains warning labels but not confidence; model findings are not censored. Two new backend cases, final 992 passed/one load deselected (101.97 s). Isolated frontend production build/lint, 125 intercepted state checks; actual approved reload/export at 375/768/1440, byte-identical brief, no uncaught page errors (optional absent-evaluation 404 retained). First real Frostpeak run corrected/approved/exported; six false/no-op model findings individually adjudicated in UI. Remaining fourteen sends used exactly, cumulative 24/24. After explicit restart/reindex consent, original backend alone recreated: healthy, 511-chunk backfill check complete, active caps 4,000/4,096, models/design counts unchanged. DB/Chroma/frontend not restarted; no new inference. | Semantic-critic accuracy, two-case repeatability, second Frostpeak approval, CyberRakshak acceptance, original-frontend deployment, whole MVP or Unity. Second draft has a real return defect; CyberRakshak generation violates mapping count. No existing design-record mutation, runtime approval, dependency install, commit or push; normal startup backfill was explicitly authorized. |

| E55 — 2026-10-21 | Quality/revision chunk (`<QA_DIR>/qa-quality-completion-20261021/progress.md`), closed ledger, actual browser runs/traces, RED/GREEN and final JUnit, saved-response replay and SQL archive | One production file: governed sparse speech patches preserve omissions/order/eligibility and reject new profile assumptions; legacy behavior retained. Existing guidance clarified and section-citation lookup exposed, strict gates unchanged. No new backend cases; final suite 992 passed/one load deselected, 106.743 s after independent code review and a nonempty citation-scope test follow-up. Affected 222 passed/five DB exclusions. Three real dashboard runs; two failed corrections retain old Frostpeak draft. CyberRakshak mapping count succeeds twice but whole drafts fail citation/type contracts. Failed Cyber runs survive mobile reload without approval/export. New allowance closed 16/16, no seventeenth send; original data/models/saved env unchanged, own QA archived/cleaned. | Hosted correction/critic reliability, two-case positive approval/export or MVP/Unity acceptance. Final file-only replay had empty evidence after a QA fixture lost section metadata; excluded from acceptance. Counterfactual offline sparse control is not fresh model proof. No new approval/export, installs, commits or pushes. |
| E56 — 2026-10-21 | Evidence preflight and fresh acceptance (`<QA_DIR>/qa-evidence-preflight-20261021/progress.md`), RED/final JUnit, closed ledger, real dashboard traces/reload screenshots and isolated SQL archive | Six-line production guard prevents nonempty evidence from becoming a zero-evidence revision call; uses the existing error with zero attempts. Extended existing tests, corrected three routing fixtures, independent review found no actionable issue. Full suite 992 passed/one load deselected, 114.155 s, no new cases. Frostpeak produces a source-preserving draft but quest hooks echo policy and critique returns HTTP 500 three times. QA-only fresh-evidence projection check corrected before Cyber retry; final generation truncates, larger retry blocked before send. Allowance closed 12/12. Three failed runs retain one draft/zero critiques; real reload/mobile keeps draft/history and blocks approval/export without inference. Original design counts/models/keys/saved env unchanged; QA archived and owned services cleaned up. | No fresh hosted correction, successful critique, approval/export, two-case quality, MVP or Unity acceptance. Five planning/four generation/three critique sends include two timeouts, three HTTP 500s and two HTTP 503s. Successful responses measured 32,495 input/8,000 output tokens; failed-send usage/cost unknown. E54's single accepted journey remains historical, not repeatability. |

| E57 — 2026-10-22 | Critique recovery evidence (`<QA_DIR>/qa-critique-recovery-20261022/progress.md`), approved brief (`<QA_DIR>/qa-critique-recovery-20261022/frostpeak/technical-brief.md`), post-review JUnit, production UI checks, closed meter, actual recovery/revision/review/export records and isolated SQL archive | Existing service/API/queue/LangGraph/dashboard now support exact consented failed-critique retry without regeneration, with frozen-data/provider binding, duplicate/active-job prevention and non-replayed expired paid leases. Three review P1s reproduced and fixed. Six backend cases added: full suite 998 passed/one load deselected, 117.996 s; build/lint and 127 intercepted production dashboard checks pass. Restored E56 Frostpeak run alone is recovered, corrected twice, separately critiqued, explicitly QA-adjudicated on five false/no-op findings, design-approved and exported as immutable version 4. Four spoken quest hooks replace policy text; Eldrin progress fits either partial state; protected fields remain exact. Repeated 37,225-character UI brief is byte-identical at 375/768/1440, with no page errors/overflow/inference and disabled runtime download. Allowance closed 9/12: seven critique sends (three HTTP 500s, one repair) and two revision sends; no planning/generation. Original models/keys/saved environment and counts 90/63/48/72/1 unchanged. | Fresh generation, two-GDD acceptance, accurate model critique, all-distinct/polished prose, production deployment, whole MVP or Unity. Optional evaluation GET remains 404; no uncaught page errors. A third prose refinement was blocked before send by the existing two-revision limit, which was not changed. Five finding dispositions are delegated QA judgments, not the user's personal review or AI-verified facts. Integration checks remain proposed, not engine/playtest evidence. |

| E58 — 2026-10-23 | Two-case evidence, scoped review and content findings (`<QA_DIR>/qa-two-case-20261023/progress.md`), baseline/RED/GREEN/final JUnit, real browser run/trace/screenshots, closed ledger and restore-verified SQL archive | Generation-only v2 citation labels replace UUID transcription on the wire; exact section validation precedes canonical restoration, with no prose rewrite or legacy/revision/storage change. One production file, 21 added lines; existing tests/fixtures extended, zero new test cases. Final standard suite 998 passed/one load deselected, 122.47 s; build/lint and 127 intercepted dashboard checks pass. Fresh-context five-file review finds no actionable issue. Three normal dashboard starts: Cyber fails UUIDs, Cyber retry fails planner HTTP 503, Frostpeak selects valid source labels but fails nonempty citations on deferred empty runtime. Closed 11/16, zero corrections/approvals/exports, no fourth start. All three failures survive reload and isolated backend restart at 375/768/1440 without uncaught page errors/overflow or approval/export actions. Original counts 90/63/48/72/1, models/keys/saved environment and GDD hashes unchanged. Two QA accounts revoked (old cookies 401); 332,871-byte SQL archive restored with matching 3 runs/0 artifacts/0 critiques/2 evidence snapshots. Owned QA services/volumes/networks/preview and revoked cookie files removed; original three containers retained. | Successful hosted canonical restoration, accepted fresh NPC/quest content, critique/correction, approval/export, two-GDD repeatability, critic accuracy, production deployment, whole MVP or Unity. Raw Frostpeak Eldrin progress asserts both independent actions remain; Kaelen adds return/stores claims; quest speech hooks are empty. Upstream 503 response reports worker request-limit exhaustion, but later planning succeeds; persistence/root cause not established. No model/env change, dependency install, commit or push. |

| E59 — 2026-10-23 | Full backend JUnit (`<QA_DIR>/qa-gemini-transport-20261023/backend.xml`), RED (`<QA_DIR>/qa-gemini-transport-20261023/red.xml`), focused GREEN (`<QA_DIR>/qa-gemini-transport-20261023/green.xml`), `backend/test_gemini_provider.py` | Stateless Google SDK Interactions transport reuses existing prompts, typed validation/repair, truncation and degraded fallback. Environment profiles, startup model checks, reasoning discard, explicit SDK retry disable, bounded adapter retries, consent/review gates and per-node provider/model trace tested offline. Two profile regressions failed before implementation; 18 new cases pass. All 1,021 backend tests including load pass on fresh disposable storage, 133.65 s; frontend lint/build pass. One non-failing pypdf cryptography deprecation warning. Real `.env` and original application services were not reconfigured/rebuilt; no hosted inference or manual smoke execution. | Actual Google model/key availability, hosted output quality/schema acceptance, real 429/quota behavior, fresh browser journey, approval/export repeatability, whole MVP and Unity remain unverified. The one-request synthetic dev smoke is for the user to run manually. |

| E60 — 2026-10-23 | Full backend JUnit (`<QA_DIR>/qa-gemini-budget-20261023/backend.xml`), initial harness errors (`<QA_DIR>/qa-gemini-budget-20261023/backend-harness-failure.xml`), `backend/test_gemini_budget.py`, `backend/test_gemini_provider.py` | Gemini HTTP-layer reservations now persist per-model Pacific-day counts before every attempt, including failed sends, retries, repair/truncation and startup GETs. Atomic daily and durable per-run caps, shared bounded process RPM, run-start preflight, one bounded 429 retry, persistent exhaustion/cheaper-model degraded fallback, sanitized auth mapping and process-cached model verification are covered with mocked HTTP/injectable clocks. Three auth cases and the exhausted-model extra-wait regression failed before their fixes. 25 added cases; 43 focused checks pass. Full backend suite including load: 1,046 passed, no deselections, 142.74 s, fresh disposable internal-only PostgreSQL/Chroma. Initial seven full-suite failures were test-container setup (missing demo docs/profile override), corrected without production fixes. One pre-existing non-failing pypdf warning. Migration upgrade/downgrade/upgrade and usage CLI verified on disposable storage; pinned timezone data also tested with system timezone paths disabled. Original `.env`, application database and running services unchanged; zero hosted model requests. | No fresh hosted quota/429 or content-quality acceptance, AI Studio counter reconciliation, browser walkthrough, approval/export or Unity. New counters are not retrospective. Apply the migration and deploy/restart deliberately before enabling this code against the application database. RPM is process-local, not distributed; reserved counts may conservatively exceed actual sends after a crash or model GET. All earlier MVP content/review gates remain open. |

| E61 — 2026-10-26 | Offline schema metrics and backend JUnit (`<QA_DIR>/qa-gemini-schema-20261026/`), `backend/test_gemini_provider.py` | One Gemini-only shared wire-schema reducer preserves types, structure, required fields and local contracts, stripping decoder constraints without changing prompts, repair, corrective re-ask, approval or NVIDIA transport. Run B's reconstructed field-replacement schema: 14,045 to 9,205 compact bytes, 19 enums/80 values to zero; nesting/union structure retained. Nine added mocked checks cover all four nodes plus speech patch, SDK JSONSchema shape/reference validity, keyword-named fields, strict local rejection/repair, NVIDIA schema preservation and a 10,000-byte/20-union-arm revision growth guard. Eight regressions fail before the fix; focused 27 pass. Full backend suite including load: 1,072 passed, no exclusions/skips, 149.49 s, fresh disposable internal-only PostgreSQL/Chroma and external socket guard. One pre-existing pypdf warning. No application DB, saved environment, dependency, runtime approval or hosted request changes. | Google compiler acceptance and useful live revision remain unverified. Mock revision still replaces `quest_1/quest_2` with `q_0/q_1`; Run B retains old v1 at review with its 1/1 revision budget exhausted. Critic accuracy, copied dialogue correction, fresh approval/export, whole MVP and Unity remain open. P1.5/P2.6/P3.2 are not accepted by this offline work. |

| E62 — 2026-10-26 | Saved-response comparison and offline JUnit (`<QA_DIR>/qa-gemini-node-schema-20261026/`), `backend/test_gemini_provider.py` | Archived c5a9db6 builder reproduces B2's six literal errors: active/incomplete/completed violate the removed stage enum. Retained A6 output passes the same full model; its unlogged generation wire schema reconstructs to 20,495 compact UTF-8 bytes. `GEMINI_SCHEMA_REDUCTION_NODES` defaults to revise only; other nodes send full original schemas. One shared reducer and revision 10,000-byte/20-arm guard retained; local validation, prompt/repair/re-ask/approval and NVIDIA behavior unchanged. Six pre-fix routing checks fail; focused 30 pass. Full suite including load: 1,075 passed, zero skips/exclusions, 144.71 s, fresh disposable internal-only PostgreSQL/Chroma plus external socket guard. Three new setting/context cases; existing node checks updated. `.env` and application data/services untouched; no external requests. | Mechanistic classification (a), not a controlled model ablation. No fresh Google acceptance, generation/revision quality, completed F04 cycle, fallback repair, dashboard approval/export, MVP or Unity acceptance. The new setting is documented in `.env.example`; real environment/model/key settings were not edited. |

| E63 — 2026-10-26 | Offline revision-policy evidence and JUnit (`<QA_DIR>/qa-revise-safety-20261026/`), `backend/test_gemini_revision_offline.py`, B3 patch fixture | Shared Gemini reducer accepts `keep_literals`; revision selects the literal-preserving candidate at or below `GEMINI_REVISE_KEEP_LITERALS_MAX_BYTES` (6,000 default), otherwise the existing full reduction. Each completion attempt logs only node/mode/compact UTF-8 bytes. Original local response models and the 10,000-byte/20-arm growth check remain intact. Gemini profiles default `DESIGN_AGENT_FALLBACK_DISABLED_NODES` to revise; legacy NVIDIA wrapper/routing stays unchanged. Provider/schema/assembly/post-repair/unexpected revision failures retain the prior artifact/critique, persist the failed trace and return to review with one consumed revision attempt. The 409 message reports actual attempts remaining or exhaustion; the unchanged dashboard disables revision at the existing cap. Four initial regressions and two unexpected-error cases failed before their fixes. Final SDK-backed whole suite including load: **1,101 passed**, zero failures/errors/skips/exclusions, 154.93 s; one existing non-failing pypdf/ARC4 warning. The 26 new focused checks overlap the full suite, not an additional total. | Initial cached runtime lacked the SDK (1,037 passed/nine import failures/two collection errors); JUnit retains that failed attempt and the corrected demo-doc mount. After explicit PyPI-only permission, pinned `google-genai==2.33.0` and its dependencies were downloaded into a retained 25-wheel wheelhouse; the test image was built with `--no-index` and build networking disabled, and `pip check` passed. Wheel hashes, downloaded and installed versions are recorded; `requirements.txt` and real `.env` are unchanged. Test PostgreSQL/Chroma were fresh and internal-only, with external sockets blocked. No Google API request, live design run, approval/export, schema-compiler acceptance or product sign-off. The pre-existing bind-mounted backend autoreloader observes source edits and performs ordinary local startup/backfill; it was not explicitly restarted and no hosted workflow was invoked. P1.5/P2.6/P3.2 remain unaccepted by this offline work. |

| E64 — 2026-10-27 | Offline finalization JUnit (`<QA_DIR>/qa-finalize-integrity-20261027/`), `backend/test_finalize_content_integrity.py`, `backend/tests/fixtures/frostpeak_b4c_reviewed.json` | Real saved B4c v2 content, evidence, critique/provenance and run context are a portable offline fixture, not mock-planner output. Before the fix on e8dabf7, the regression fails with B4c's exact wrong hash `767054f396211ea8552f1f92dbd1290fa646be4042ce66bb7bfce818dd20f8bd`; after the fix final content matches `8c6b049ab9793c5594de8e4be45248e6644541b7ed732b71957bfc6533955817`. Finalize passes the frozen contract version and uses the existing canonical digest helper; approval validation and critique-provenance code stay unchanged. Fourteen focused cases cover real v2 triggers, v1 behavior, key ordering, exact metadata exceptions, checkpoint/candidate tampering, narrow exception scope, inline/queued failure, retained artifact/critique/revision count, no saved outputs/automatic retries and same-approval recovery. Full backend including load: **1,115 passed**, zero failures/errors/skips/exclusions, 156.75 s; one pre-existing pypdf/ARC4 warning. | Initial focused session-cache setup failure was corrected; the first full run had 1,111 pass/two provider-factory failures because the external launcher forced LLM_PROFILE=test. Removing that launcher override, not changing application provider code/tests, produced the final green suite. PostgreSQL/Chroma were fresh/internal-only; external DNS/sockets blocked, cached SDK image reused without downloads. No application database connection, model call, live workflow, environment edit, new column/migration, or historical artifact rewrite. Application backend was deliberately stopped before edits to prevent autoreload/startup reindex and remains stopped; no restart was performed. Final-only metadata exceptions and retained approval-audit constraints are documented at P4.1. Live deployment/restart, dashboard acceptance, hosted quality, whole MVP and Unity remain unverified. |

| E65 — 2026-10-27 | Offline safety JUnit and runner (`<QA_DIR>/qa-design-safety-20261027/`), `backend/test_design_safety_guards.py`, `frontend/tests/design-agent-api.test.mjs` | Retained B2 evidence confirms fallback_result preceded failed persistence while stored degraded stayed false. Failed-result metadata now persists fallback provenance; shared approval checks run config and scoped execution history, requires strict per-artifact acknowledgement in API/worker/finalize, and records it in approval-event JSON details (one new migration, no historical acknowledgements fabricated). Failed revisions before artifact persistence preserve saved revision count and frozen work for provider, schema, local-validation and unexpected errors. Consecutive failures are separately bounded in existing run JSON (default/configurable 3); successful artifact persistence resets them, queued attempt keys include failures, exhausted runs no longer prevent a fresh consented run. Invalid output/envelopes map to 502; unavailable/timeouts map to 503. A final red/green regression scopes status lookup to the actual failing node, so an old upstream failure cannot relabel an unrelated human-review error. Dashboard adds a deliberate artifact-bound checkbox and distinct saved/failed counters, disables exhausted corrections, reloads after 502/503 and retains saved-run links. Final full backend including load: **1,139 passed**, zero failures/errors/skips/exclusions, 153.12 s; one existing pypdf/ARC4 warning. Twenty-four new backend cases are included in that total. Three mocked frontend API tests, ESLint and the standard Turbopack production build pass; no browser was opened. E64 real-v2 hash/finalization regressions remain green. | Clean pre-fix selection: seven failures/one pass. Initial broader suite exposed 66 obsolete HTTP/budget expectations or incomplete test scaffolds; those were corrected without weakening the guard. One partial rerun exposed an incomplete Gemini preflight double; a fake quota clock replaced real RPM sleeps in mocked tests. Initial Windows sandbox Turbopack/webpack builds failed on worker/file permissions; the unchanged normal build passed outside that sandbox with telemetry disabled, npm offline and an external DNS/socket guard. Backend tests used internal-only disposable PostgreSQL/Chroma and a cached SDK image with external sockets blocked. No model calls, package downloads, live run, application DB migration/data write, `.env`/README/dependency-pin change, or existing final-artifact repair. Application backend remains stopped. Apply the prepared review-details migration before using the changed application; production-volume migration timing was not tested. Browser checkbox interaction/visuals, live-provider behavior, hosted quality, useful fresh acceptance and whole MVP remain unverified; all broader phase gates stay open. |

| E66 — 2026-10-27 | Full backend JUnit (`<QA_DIR>/qa-walkthrough-fixes-20261027/backend-final.xml`), initial regressions (`<QA_DIR>/qa-walkthrough-fixes-20261027/red.xml`), frontend build (`<QA_DIR>/qa-walkthrough-fixes-20261027/frontend-build.log`), `backend/test_walkthrough_fixes.py` | Mock evidence is grouped in document/source order; local summary now prefers the same exact, heading-aware excerpt helper extracted unchanged from the hosted adapter, with legacy fallback and local metadata retained. Disabled approval has no primary/hover styling; mock consent states offline/no transfer while hosted wording is unchanged. Health shares provider selection with the factory, without constructing a transport. Wholly no-op mock corrections return an explicit capability message and 409, retaining the draft/critique, saved budget and bounded failure counter; partial invalid and hosted invalid corrections remain 502. README identifies synthetic Frostpeak, local limitations, opt-in dev Flash-Lite, free-tier data terms and the API-only approval/export evidence. Eleven new backend cases are included in **1,150 passing tests**, zero failures/errors/skips/exclusions, 178.95 s; four mocked frontend API tests, lint and normal production build pass. | Eight intended pre-fix regressions failed; an initial hosted-control citation/scope fixture error was corrected. First full run retained 16 failures: five missing demo-doc mounts, one unintended local-confidence change, one overbroad partial-revision status and nine diagnostic-double attribute errors. Corrected the runner mount and narrow code behavior, not the gates or unrelated tests. Cached images/internal-only disposable DB and Chroma plus external socket guards; no downloads, application DB access, models, browser, `.env` edit, migration, approval/export or historical artifact changes. Application backend/frontend were stopped before edits and remain stopped. Systems extraction, actionable content and browser verification remain open; NOT ACCEPTED and phase gates unchanged. |

| E67 — 2026-10-27 | Full backend JUnit (`<QA_DIR>/qa-live02-containment-20261027/backend-final.xml`), pre-fix regressions (`<QA_DIR>/qa-live02-containment-20261027/red.xml`), `backend/test_design_safety_guards.py` | Option (c) only: service checks the exact current artifact's review event before graph resume or queueing; different decisions return a clear 409, same decisions retain current behavior. A read-only `approval_blocked_reason` feeds the muted approval status/control; existing 409/502/503 reload handling is retained. Unexpected human-review resume exceptions record a failed execution and log the full stack without locals, redacting configured credentials. Five new backend cases plus the extended successful-revision control prove checkpoint identity/interrupts unchanged after conflict, no new review event, another bounded reject works, and a new artifact can be approved. All **1,155 backend tests pass**, zero failures/errors/skips/exclusions, 186.48 s, including load, finalize integrity and B4b's exact hash. The 43 focused passes overlap that total. Six mocked frontend API checks, lint and production build pass. | Six pre-fix checks failed; initial focused logging capture needed Alembic-disabled logger re-enabling in the test. Initial full run: 1,141 passed/14 failed from missing root demo mounts, incomplete SQLite review-event fixtures and unsupported fake-query chaining. Runner mounts/fixtures/query style corrected without weakening assertions. Sandboxed Turbopack child-process IPC failed; the same offline build outside that restriction passed without config changes. One existing non-failing pypdf/ARC4 warning. Cached runtime, isolated disposable PostgreSQL/Chroma and blocked external sockets; no downloads, model/browser calls, application DB access, `.env` edits, new migration, revision schema edits, supersession or old-run repair. NOT ACCEPTED; LIVE01 and end-to-end browser approval/export remain open. |

| E68 — 2026-10-29 | Offline verifier JUnit and guarded runner (`<QA_DIR>/qa-final-integrity-verifier-20261029/`), `backend/verify_final_integrity.py`, `backend/test_final_integrity_verifier.py`, minimal `frostpeak_run_c_integrity.json` and existing B4b fixture; [Run C browser evidence](docs/acceptance/2026-10-27-live-approval-export.md#fresh-run-approval-attempts) | Pure verifier reports raw canonical UTF-8 hashes, all changed JSON pointers, independently derived additions and every offending path; EXACT / EQUAL_EXCEPT_DOCUMENTED_METADATA / MISMATCH. Frozen strict opt-ins, reviewed empty/uncited/warned memory and the exact runtime deferral warning constrain exceptions; no whole-section ignoring or blind flag removal. Run C's only added `/npc_memory_design/memory_unspecified=true` meets this policy and did not meet strict byte equality. The CLI selects the recorded approved draft and immutable final in a PostgreSQL READ ONLY snapshot, without a provider. One explicit Run C regression failed before implementation; initial missing-module setup errors are also retained. Final 26 fixture/CLI checks pass; full disposable backend suite including load and existing finalization guards: **1,181 passed**, zero failures/errors/skips/exclusions, 175.82 s, one existing pypdf/ARC4 warning. | No finalization, schema, provider, migration or existing data changed. Cached image; new internal-only PostgreSQL/Chroma and external DNS/socket guards; no downloads, Google/model requests, browser, `.env` edit or application DB access. CLI SQL ordering/approval-link selection/error redaction are mocked offline; live application CLI execution was deliberately not attempted. This does not establish reliable corrections, semantic quality, runtime/Unity or full MVP readiness. Moving both flags before review is planned after the MVP. NOT ACCEPTED and broader phase gates remain unchanged. |

| E69 — 2026-10-29 | Full backend JUnit (`<QA_DIR>/qa-quality-advisories-20261029/backend-final.xml`), initial full-run result (`backend-full.xml` in the same QA folder), `backend/test_draft_quality_advisories.py`, frontend API/rendering tests | Exactly three typed, non-blocking checks: numeric Quest situation/linked-ID mismatch, normalized exact objective/dialogue copy, and explicit memory metadata warnings misplaced in rules. Ambiguous labels, unresolved/duplicate IDs and shared words abstain. New generated/revised drafts atomically persist an artifact-bound advisory evaluation in existing run JSON at `model_config.draft_quality_evaluation`; run responses expose `draft_evaluation`. The review panel renders a separate muted list without controls. Human evaluation rubric, scorecard scores, system findings, critique/provenance/identities, approval gates, artifact content and exports are unchanged. The frontend gate calculation was relocated verbatim for behavioral tests. B4b reports the warning; Run C reports none. Fifteen new backend cases are included in **1,196 passed**, zero failures/errors/skips/exclusions, 159.72 s, including load, finalize and golden-hash regressions. Nine mocked API/rendering checks, lint and the normal production build pass. | Thirteen initial pure controls failed before implementation; frontend tests initially failed on the missing helper. First full run: 1,195 passed/one failure from an old DB double assigning IDs only on refresh; corrected it to model flush-time identity without weakening assertions. Initial build hit Windows sandbox worker IPC restrictions; the unchanged guarded offline build passed outside that restriction. One existing pypdf/ARC4 warning. Cached images, fresh internal-only PostgreSQL/Chroma and blocked external sockets; no downloads, model/network-provider/browser calls, application DB access, `.env` edits or fixture changes. Old runs without a saved advisory evaluation remain unchanged and do not acquire advisories through reads. No fuzzy matching, automatic correction, new blockers or exported advisory content. Visual/browser behavior and live-provider usefulness remain unverified; NOT ACCEPTED and broader phase gates stay open. |

| E70 — 2026-10-29 | `frontend/tests/design-agent-api.test.mjs`, `backend/test_draft_quality_advisories.py`; full-suite JUnit `<QA_DIR>/qa-advisory-ui-fixes-20261029/backend-green.xml`; [live findings being addressed](docs/acceptance/2026-10-28-quality-advisories-live.md#screenshots-and-ux-findings) | Decisions and Design Agent now share one consent component, driven by the existing health `llm_provider` (saved run provider for critique recovery). Gemini text names Google and free-tier data use; mock explicitly stays offline; other hosted providers retain a transfer warning. Advisory-only rendering adds labelled compared text and eight-character IDs, no controls/animation or approval effect. A scoped, read-only `has_evaluation` response flag prevents absent human-evaluation requests without changing the evaluation endpoint; unexpected errors remain visible. Twenty mocked frontend API/rendering checks, lint and standard production build pass. Full disposable backend including load and integrity/hash regressions: **1,197 passed**, zero failures/errors/skips/exclusions, 149.79 s; one existing pypdf/ARC4 warning. | Initial frontend selection had eleven failures, including four missing shared-component setup errors; the backend presence regression failed before the field existed. First full run: 1,195 passed/two failures because an existing SQLite fixture omitted the already-existing evaluation table; completed that fixture without weakening assertions. Cached images, internal-only fresh PostgreSQL/Chroma, external sockets blocked. No model/external-network/browser calls, application DB access, `.env` changes, migration, fixture-content/hash changes or push. Consent request payloads, critique, scoring, approval derivation and finalization are unchanged. New wording/layout and absence of browser-console resource noise still require a later browser check; NOT ACCEPTED and broader phase gates remain open. |

| E71 — 2026-10-29 | Offline JUnit (`<QA_DIR>/field-corrections-offline-20261029/backend-final.xml`), `backend/test_field_corrections.py`, frontend API/rendering tests | Exact one/two-field allowlist, current mutable artifact binding, typed filtered schemas and assembly restriction, full canonical scope guard, and only enumerated manual-test/creative-proposal dependencies. A request execution records reviewer/reason/paths/original values and hash/dependent effects/outcome; queue payload/key and worker claim fence stale, altered or duplicate requests. Identical artifact/path/reason submissions are refused, including after failure; a changed reason is a new bounded attempt. Queued reservation/job commit is atomic; correction jobs are not automatically replayed, while provider retry/budget behavior stays unchanged. The chooser previews current text and conditional dependent effects; no approval-policy change. Mocked SDK wire schemas retain literals (558-byte hook, 572-byte situation). Full suite including load: **1,227 passed**, no failures/errors/skips/exclusions, 183.26 s, one existing pypdf/ARC4 warning; 46 new parametrized cases are included, not an additional total. Frontend ESLint, production build and all nine API/rendering cases pass. Existing golden fixtures, explicit-reject/LIVE02, v1/NVIDIA and finalize/hash regressions pass unchanged. | Initial action-contract regression failed before implementation. Iteration caught duplicate-request lock retention and a stale revision-failed flag after approval; both fixed and covered. First full run: 1,222 passed/two order-dependent log-capture assertion failures, corrected in test isolation; a subsequent full run passed, then final review added the stored NPC voice field to compact context and reran the entire suite. Fresh internal-only PostgreSQL/Chroma, cached SDK image and external socket guards only; no application DB access, model/network call, browser, environment edit, migration, fixture repair or push. No claim that a hosted model obeys the tiny schema or fixes semantics; an interrupted worker is not replayed automatically. Advisories from the separate quality-advisories branch were not imported onto this main-based branch. Broader phase/MVP gates remain open. |

The immutable final artifact preserves the reviewed design content, with explicitly enumerated deterministic server metadata additions (memory_unspecified and runtime_deferred plus its warning). Raw reviewed and final hashes may therefore differ; the verifier checks both hashes and rejects every other difference.

Update checked items with evidence IDs and update this ledger after meaningful
authorized verification. Do not create milestone percentages or mark all of a
phase complete from a single passing subset.
