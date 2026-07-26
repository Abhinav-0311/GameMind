# CyberRakshak Product Audit

Date: 2026-07-22

## Purpose

This audit tests whether GameMind turns the real CyberRakshak source set into
useful, trustworthy work for a student or indie game developer. It separates
technical success from product usefulness. An HTTP 200 response or a populated
screen is not treated as proof that the generated game-design output is good.

## Test context

- Workspace: `cyberrakshak-acceptance-20260721-142146`
- GDD: `cyberrakshak_gdd.md` (17 chunks)
- Technical brief: `cyberrakshak_technical_brief.md` (5 chunks)
- Runtime extension: `cyberrakshak_runtime_extension.md` (5 chunks)
- Reviewed blueprint: `b2c3e19b-8256-46a9-a531-54b497d2e18d`
- Materialized blueprint: `b03760a4-3474-4cb3-a485-106cde587b6b`
- Runtime mode: local demo, mock LLM, offline lexical embeddings

## Executive verdict

GameMind is a strong engineering prototype, but it is not yet a trustworthy
indie-development assistant. Source storage, project scoping, citations,
blueprint persistence, exports, materialization, and the runtime test are wired
together. The remaining blocker is semantic product quality: several screens
declare success when the content is incomplete, contradictory, or unusable.

The correct current label is **private technical beta**, not production-ready
MVP.

## Source-to-output trace

| Design area | CyberRakshak source truth | Current GameMind output | Verdict |
| --- | --- | --- | --- |
| Game identity | Story-driven low-poly 3D ethical-cybersecurity platformer starring Adi | Blueprint title is the runtime-extension filename and summary describes only the early runtime slice | Partial |
| Narrative | Adi is manipulated by Jay, discovers the breach in level 9, then works with cyber police in level 10 | A duplicated fragment from the Phishing Office quest table is shown as the lore background with High confidence | Blocker |
| Art direction | Low-poly digital sandbox direction is explicit; palette and detailed visual language are not | No art direction detected | Incorrect extraction; missing-detail warning is only partly valid |
| NPCs | Adi, Jay, and PATCH have distinct roles and character arcs | All three are detected, but Adi's profile ends with `His` and Jay's betrayal arc is absent | Blocker |
| NPC memory | PATCH should react to Jay, story events, repeated mistakes, routes, and player condition | No memory nodes are created | Missing capability |
| Levels | Ten named levels with a cyber threat and story purpose per level | All ten levels are extracted in order and their focus text is accurate | Extraction pass; production detail missing |
| Gameplay loop | Nine-step mission loop and four player approaches | Core loop and approaches are extracted correctly | Pass |
| MVP scope | Technical brief resolves MVP to a Windows PC vertical slice; AR, VR, PowerRush, and online systems are deferred | Delivery priorities still show PowerRush and Android AR as Must ship because GDD labels override the resolved technical decision | Blocker |
| Quests | Three concrete early quests with objectives and unlock rewards | Quest records exist, but a materialized objective becomes a generic `retrieve key`; dynamic generation turns `Training Sandbox Orientation` into a collectible supply item | Blocker |
| Lore retrieval | Direct questions should return the relevant fact and evidence | Jay and MVP questions retrieve useful chunks; level 9 and PATCH behavior retrieve weak or unrelated chunks | Partial |
| Readiness | Missing narrative, art, memory, or truncated NPC output should prevent normal approval | Blueprint reports `runtime_ready`, no missing requirements, and no advisories | Blocker |
| Exports | Brief and runtime data should be usable outside the dashboard | Markdown and JSON endpoints return 200, but they export the same malformed or incomplete content | Mechanical pass only |

## Browser journey findings

### Home

- The selected workspace contains 3 documents, 5 blueprints, and 1 materialized
  runtime snapshot.
- The recommended action is to playtest runtime even though the newest blueprint
  is still a draft and contains blocking content defects.
- Dashboard mode and integration mode are explained, but the page does not show
  the quality problems that should be resolved before runtime testing.

### Sources

- All three CyberRakshak sources are present, classified, indexed, and scoped to
  the active workspace.
- Source cards expose chunk counts and revisions clearly.
- `Delete latest` is more prominent than revision-management or archive actions.

### Decisions

- The three important decisions are present and source-backed: delivery scope,
  online boundary, and accessibility.
- The header says `0 open decisions`, while each resolved card still displays
  `open decision`. The `Reopen` action proves the records are resolved, so the
  status language is internally inconsistent.
- Resolved decisions are not given sufficient precedence during blueprint
  synthesis.

### Blueprints

- Five similarly named snapshots create unnecessary history noise.
- The newest draft is correctly selected first.
- Narrative is malformed but labeled High confidence with 13 citations.
- NPC output is truncated but labeled High confidence.
- Art and memory correctly show low-confidence empty states, but readiness still
  reports `runtime_ready`.
- Level presentation is readable and contains all ten chapters, but each level
  lacks objective, mechanic, player choice, hazards, required assets, narrative
  beat, reward, dependencies, and acceptance criteria.
- Gameplay presentation is visually organized, but it repeats GDD priority labels
  instead of applying the approved MVP decision.

### Lore Search

- Suggested and recent questions are Frostpeak examples (`King Arven`, `Eldrin`)
  inside the CyberRakshak workspace.
- `What happens in level 9?` returns a low-confidence chunk ending around level 6
  rather than the level 9 answer.
- The page presents retrieved fragments, not a concise grounded answer.

### Runtime Test

- The dialogue, quest, acceptance, and hint calls complete without transport
  errors.
- Jay responds with a retrieval disclaimer rather than a calm in-character answer
  to the player's question.
- Dynamic quest generation produces `Acquire Training Sandbox Orientation` and
  asks the player to collect the quest title as a supply item.
- The progressive hint is generic and unrelated to the generated objective.
- The five-minute cooldown is unsuitable for a developer test surface.

### NPC and Hint studios

- The hidden NPC route loads Jay, PATCH, and Adi after asynchronous fetch.
- Jay is shown as `Untitled character`, faction `Solo`, with no voice or memory
  policy. These defaults do not represent the GDD well.
- Hint Studio lists the three materialized quests plus the invalid dynamically
  generated quest, allowing bad runtime data to spread into another tool.

### Collaboration

- The automated owner/editor/viewer acceptance test passes.
- That test uses a small synthetic CyberRakshak text, not the real GDD.
- With local authentication disabled, the Workspace page performs member calls
  that return 401 errors and leaves the user at a dead end without a direct sign-in
  action.

### Responsive behavior

- No horizontal overflow was found at 390 px.
- On the mobile Blueprint page, useful blueprint content starts roughly 1,600 px
  below the top because the hero, actions, four progress cards, and source panel
  all stack before the review area.
- The layout is technically responsive but not efficient for repeated mobile use.

## Automated verification

- Backend default suite: **187 passed, 1 intentionally deselected load test**.
- Private-beta collaboration acceptance: passed inside the default suite.
- Frontend lint: passed.
- Frontend production build: passed; 18 static routes generated.
- Load benchmark: did not complete after 413 seconds and was interrupted. Its
  shared threaded `TestClient` strategy can hang and should not be treated as a
  reliable production-load result.

## Priority action plan

### P0: Stop false success

1. Make readiness fail on malformed required sections, truncated records, empty
   required output, and unresolved source conflicts.
2. Prevent normal approval unless the user explicitly acknowledges every blocking
   deficiency.
3. Distinguish `Extracted`, `Proposed`, and `Developer confirmed` content.

### P1: Correct CyberRakshak synthesis

1. Make resolved design decisions override older GDD priority labels.
2. Replace broad chunk concatenation with section-aware extraction and
   deduplication.
3. Preserve complete NPC sentences and extract character arcs.
4. Treat missing art and memory detail as decisions to resolve, not silent empty
   runtime sections.
5. Add CyberRakshak golden-output regression tests for narrative, scope, NPCs,
   levels, quests, and readiness.

### P2: Turn blueprint into a build plan

1. Add a per-level matrix: learning goal, mechanic, objective, hazards, PATCH/Jay
   beat, reward, dependencies, assets, and acceptance check.
2. Add an MVP milestone plan for the Training Sandbox and Password Vault slice.
3. Add a system dependency map and discipline-specific task list.
4. Show missing decisions and risks before long extracted detail.

### P3: Repair runtime semantics

1. Materialize quest objective types from source meaning rather than defaulting to
   generic `retrieve key` data.
2. Constrain dynamic quests to approved templates and runtime entities.
3. Make dialogue answer the question in the NPC's style while retaining citation
   metadata separately.
4. Generate quest-specific hints and provide a developer cooldown override.

### P4: Simplify the journey

1. Use one guided path: Sources -> Decisions -> Build plan -> Validate -> Export.
2. Recommend the next quality action, not merely the next available API action.
3. Make sample lore prompts workspace-specific.
4. Collapse mobile progress into one compact status row or stepper.
5. Archive or group superseded blueprint snapshots.

### P5: Production gates

1. Replace or time-bound the hanging load benchmark.
2. Run the real GDD through authenticated owner/editor/viewer UI flows.
3. Add deployment health, backups, SMTP, HTTPS, and persistent production data
   only after the CyberRakshak golden-output tests pass.

## MVP completion criteria

GameMind should not be called MVP-complete until:

1. The CyberRakshak blueprint represents the real story and resolved MVP scope.
2. Readiness blocks malformed narrative, truncated NPCs, and unusable runtime data.
3. A new developer can identify the next action without external explanation.
4. The exported brief provides an actionable vertical-slice plan.
5. Materialized quests and hints remain faithful to the approved blueprint.
6. Standard, collaboration, browser, and bounded load checks all complete reliably.
