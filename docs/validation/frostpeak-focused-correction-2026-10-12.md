# Frostpeak focused correction brief — 2026-10-12

Status: historical correction brief. The bounded hosted check and subsequent
local fix are recorded below. This document is not an approved artifact,
completed semantic evaluation, or authorization to call a provider.

## Baseline and scope

- Workspace: `qa-frostpeak-boundary-20261012-e5683a34`.
- Run: `97096313-ca20-4abf-96da-652a6b775e7e`.
- Artifact: `3ada9d3f-368d-4c8d-88a7-ba39c6770057`, version 1.
- Raw critique: `8aeb692b-a721-4942-8adb-b197c254483f`.
- The read-only refresh matched the previous saved artifact exactly.
- Allowed sections for a future revision: `npc_archetypes`,
  `npc_memory_design`, `quest_hooks`, `unity_runtime_preview`.
- No existing workspace, artifact, critique, environment, approval or runtime
  record was changed. No new QA workspace was created in this step.

## Four focused corrections

1. Greeting eligibility versus repetition:
   Replace `npc_memory_design.content.rules[5]` with:

   > Proposed dialogue eligibility: first_interaction requires a new encounter with Eldrin and is allowed at most once per attempt, independently of objective flags. Only explicit quest restart clears its suppression; restart does not automatically speak the greeting. ash_pass_reminder requires an active attempt with at least one objective incomplete. quest_complete requires both objective flags true and a completed attempt. Apply the NPC record's repeat policies after checking eligibility.

   This is an explicit implementation proposal, not a statement from the GDD.
   It clarifies suppression/reset without inventing an automatic greeting on
   restart. Trigger priority when multiple situations are simultaneously
   eligible remains a designer/integration decision, not proven engine behavior.

2. Unsupported scene/activation claims:
   Replace the first two runtime integration notes with:

   > Proposed scene placement: Eldrin in the Watchtower. This is not established by his title alone; confirm the placement before binding dialogue to a scene.

   > The cited GDD does not establish Ash Pass within Geothermal Vents or define a proximity activation event. Leave quest location and activation unbound pending an explicit design decision.

   The frozen GDD establishes the Geothermal Vents starting level and the
   Ash Pass quest separately; it does not place that quest in that level or
   specify its proximity activation. Eldrin's title does not establish an
   executable scene binding. Do not replace these gaps with new invented facts.

3. State-neutral incomplete-quest reminder:
   Proposed spoken line:

   > The Ash Pass awaits its reclaiming. Attend to what remains unfinished.

   It is applicable at zero progress and either partial state, without implying
   that both actions remain undone. Keep the exact same line in the NPC hook,
   trigger text/manual check, NPC integration note and quest hook. Preserve the
   greeting and completion lines. This is an assistant-authored narrative
   proposal, not fresh NVIDIA output or a source quote.

4. Unspecified quest-giver role, not a negative fact:
   Replace the quest's first assumption with:

   > The cited GDD does not assign Eldrin as this quest's giver; linking him to this quest is an unconfirmed design proposal.

   Align its warning accordingly. Keep the existing correctly qualified NPC
   assumption. Do not convert "the GDD does not assign" into "cannot be" or
   "is not" the quest giver.

## Preserve the valid voice and raw critique

Frozen NPC excerpt `e08649e9-f605-440c-8160-84da343232f6` states:

> He speaks in a formal, slow manner and references ancient lore history to guide the player.

The current style, "formal, slow manner, references ancient lore history", is a
faithful paraphrase. Do not change it merely to appease the model's unsupported
finding. Preserve the original critique and separate its quality assessment
from revision-compliance checks.

The existing evaluation service permits scorecards only for completed runs
(`backend/app/design_agent/evaluation.py`, `create`). The approval guard
requires a resolved independent critique
(`backend/app/design_agent/grounding.py`, `validate_design_approval`).
This brief does not repurpose either contract or introduce an override.

## Preflight evidence and acceptance limits

A read-only database transaction retrieved the exact artifact/snapshot/critique.
The proposed changes were applied only to an in-memory copy, affecting ten
string fields across the four selected sections. Existing local contracts
validated the proposed artifact's actionable structure. Assertions confirmed:

- Exactly one NPC, three matching NPC/quest dialogue lines and one quest remain.
- Voice, greeting/completion lines, citations and all five unselected sections
  are unchanged.
- Reward remains exactly 100 gold and 250 XP; runtime is null; dependencies
  remain empty.
- The complete structured quest-state contract is unchanged.
- All 18 unresolved assumptions remain unconfirmed.
- Approval still raises "Independent critique must be resolved."

This is one offline structural/preservation preflight, not a backend-suite run,
browser acceptance, fresh generation-quality proof or runtime playtest.

## Proposed next authorized execution

Only after fresh explicit consent: use the configured NVIDIA generation model
for one focused revision and an independent critique, with at most three
requests total including all retries/repairs. Send the saved Frostpeak excerpts
and selected artifact content; save results only in a new isolated QA workspace.
Do not change existing workspaces, environment/model settings or runtime
approval. Check all ten field changes and unchanged-section preservation.
If critique disagrees again, preserve the raw result and report the evidence;
do not silently suppress findings, approve, switch models or keep retrying.

## Bounded hosted check and local fix

The user authorized the three-request scope. New isolated workspace:
`qa-frostpeak-focused-20261012-eea1a9b0`; run:
`0d64a66e-a66c-4d5f-8da5-543d26b3e8e5`.

Two requests were sent to the unchanged configured NVIDIA Super model. The
first response reached the configured 2,048-token limit. The 4,096-token retry
ended normally, returning valid JSON, but put section-level `citations`,
`confidence` and `warnings` inside its single NPC record. The required section
confidence was missing. The staged cap blocked a further repair to reserve a
critique request. No revised artifact or critique persisted. The failed run
retains its raw responses and assessment; its unused allowance is closed.
Outside-QA fingerprints of all 38 database tables were unchanged during that
check. No runtime approval was performed.

The subsequent local fix:

- Makes generated NPC records reject unknown fields instead of silently
  discarding misplaced metadata. Historical storage contracts remain unchanged.
- Relocates the three explicit metadata fields only when the response is
  complete JSON, its section contains only `content`, its content contains only
  `npcs`, and exactly one otherwise-valid NPC supplies all three fields. No
  confidence, citation, warning or design value is invented. Conflicting,
  incomplete, duplicate-key, multi-NPC and unknown-field cases fail closed.
- Records the local recovery in safe diagnostics. Generated/revised recovered
  drafts carry a visible structural-recovery warning and remain approval-blocked.
  Historical closing-delimiter recovery warnings still trigger the same guard.
- Explicitly explains the section envelope in generation/revision instructions.
- Prevents a hosted schema repair from discarding ambiguous nested metadata.

### Verification and limits

New regressions reproduced the missing recovery and silent metadata loss before
production changes. Final local offline run: **294 passed, 5 deselected in
9.22 seconds**, with sockets blocked, `--noconftest -p no:cacheprovider`, and
bytecode writes disabled. The five deselected database-fixture cases were not
run: the shared conftest rebuilds the test schema. The earlier Docker expansion
also encountered two missing `/docs/demo/cyberrakshak_gdd.md` fixtures; both
passed when rerun from the existing Windows environment with repository docs
available. Coverage tooling was unavailable in Docker; no percentage is claimed.

An additional read-only transaction replayed the actual saved second response
through the configured adapter, mocked transport, blueprint validation,
citation grounding and scoped-revision validation. It made zero hosted calls
and saved nothing. All 12 checks passed: five unselected sections, voice,
greeting/completion, three matching NPC/quest lines, the neutral reminder,
state/reward/runtime/dependencies, section citations, record source IDs, stored
fresh-dialogue policy, 18 assumptions, visible recovery blocker and blocked
approval. Saved QA run/artifact/evidence hashes remained identical.

Environment hashes remained unchanged. No model/environment changes, database
writes, installs, commits or pushes were made for this local fix. Changed Python
files passed syntax checks and the scoped Git whitespace check. This is not a
full backend-suite result, fresh hosted semantic acceptance, browser walkthrough
or runtime playtest. The next hosted gate needs fresh explicit authorization:
a clean focused revision and independent critique, not approval of this replay.

## Follow-up live check and critic evidence boundary

A separately authorized follow-up used a process-only 4,096-token revision
budget and the same model. Isolated workspace:
`qa-frostpeak-live-4096-20261012-e7427f19`; run:
`7c6415b0-d0ef-4289-82f1-a27af154e3e9`; revised artifact:
`de133363-d795-4aee-a816-4c8ff9456f0a`; critique:
`9bef2b40-1084-453d-99e7-2aa9224d2bf3`.

Two of three authorized requests completed without retry, repair or local
recovery. Revision took 30.539 seconds and critique 4.697 seconds; total reported
usage was 23,842 tokens. Cost was unavailable. The process-only budget was
restored; the unused allowance was closed. Existing workspace/table fingerprints
and environment hashes remained unchanged. Results and manual assessment were
saved only in that new QA workspace; no runtime approval occurred.

All ten requested field corrections matched. Eleven strings changed because
the NPC's already-correct quest-giver assumption was also paraphrased. This was
semantically equivalent but an unrequested scope deviation. The five unselected
sections, voice, greeting/completion lines, matching dialogue mappings, source
IDs, reward, runtime, dependencies and quest state contract were preserved.
All 18 assumptions remained unresolved.

The independent critic returned `needs_revision` with three unsupported findings:

- It denied the voice attribution while quoting the GDD's explicit Eldrin voice
  attribution in frozen chunk `ecb18686-524b-4892-9d54-fb818f5a16fc`.
- It alleged copied completion dialogue by comparing it to a reward sentence,
  not matching spoken source wording. Grounded completion meaning is required
  by the human request; it is not proof of copied dialogue.
- It requested `state_contract.restart.lifecycle: active`, which already exists.

Those raw findings were retained, not deleted or converted into approval. This
was a successful scoped revision, not a reliable critic or fresh from-scratch
creative-generation acceptance result.

### Local critic-contract hardening

Only critic instructions and existing field-contract guidance were changed:
require current-field/source comparison, read named character passages with
local pronoun attribution, distinguish copied wording from shared quest meaning,
and inspect structured restart fields separately from event text. Unsupported
traits, near-verbatim copying, incompatible triggers and incorrect state values
remain reviewable defects. No game-specific exemption, verdict filter, new
schema, model change or approval override was added.

Six counterfactual prompt/input cases (supported/unsupported voice,
new/copied wording, compatible/incompatible restart event) reproduced missing
guidance before the change and passed afterward. They verify input visibility,
instructions and preservation of findings, NOT hosted semantic classifications.
The existing sub-500-word task-rubric guard remains unchanged and passes.

Final wider offline run: **300 passed, 5 database-fixture cases deselected in
8.04 seconds**, using the existing Windows environment with sockets blocked,
`--noconftest -p no:cacheprovider` and bytecode writes disabled. No shared test
schema was rebuilt. Python syntax and scoped Git whitespace checks passed;
environment hashes were unchanged. No full-suite, coverage-percentage or hosted
semantic-accuracy claim is made.

A read-only replay of the saved live draft, evidence and raw critic confirmed
all three findings and `needs_revision` survive unchanged; approval still raises
`Independent critique must be resolved.` No saved QA state was written and no
hosted request was sent for this local step. Fresh hosted critic accuracy,
database integration, browser acceptance and runtime playtesting remain separate
verification gates; do not infer them from the offline checks.

