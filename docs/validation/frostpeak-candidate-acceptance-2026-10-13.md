# Frostpeak corrected candidate and acceptance checklist — 2026-10-13

## Outcome

A local, assistant-authored candidate is saved in
[frostpeak-design-candidate-2026-10-13.json](frostpeak-design-candidate-2026-10-13.json).
It is a review package, not an API request, an approved artifact, fresh NVIDIA
output, or an import instruction. Its proposed design-only scope is for a new
explicit review; the original QA run remains in its legacy scope.

No application code, tests, model settings, environment files, existing QA records,
approval, or runtime data were changed in this step. The candidate and this report
are the only new files.

## Corrections and preservation

The candidate changes 15 leaf fields in three sections: npc_archetypes,
quest_hooks, and npc_memory_design. All changed paths are recorded in its assessment.

- Replace the shared progress line in the NPC hook, trigger, manual check,
  derived integration note and quest hook:
  > Your charge at the Ash Pass is not yet fulfilled. Attend to what remains, seeker, and return when both duties are done.
- Qualify progress eligibility as an active attempt. Failed attempts must not
  replay active-progress dialogue merely because their preserved flags are partial.
- Replace the structured restart event and its copied quest/memory instructions:
  > Player confirms Restart Quest to begin a new attempt after quest failure
  Abandon Quest and ordinary post-failure dialogue do not authorize restart.
  Abandonment behavior remains a separate, undecided design choice.
- Remove the unsupported tutorial prerequisite. Do not infer Eldrin's scene
  placement from his Watchtower title; leave location and quest activation unbound
  until confirmed. Update the greeting situation and its mirrored manual note.

Preserved: Eldrin's source-supported voice, greeting and completion lines, exactly
one NPC/one quest/three matching spoken hooks, all section citations, quest objectives,
100 gold and 250 XP, null runtime, empty dependencies, and every state-contract field
except the restart event. All six unselected sections remain unchanged, including
the deliberately empty runtime preview. Nothing substitutes invented engine IDs.

## Usefulness review

| Attempt state | Progress reminder | Reason |
| --- | --- | --- |
| Active, neither flag set | Eligible | Does not claim a specific objective has been completed. |
| Active, guards cleared only | Eligible | Does not claim guards still stand. |
| Active, flag raised only | Eligible | Does not claim the flag is still lowered. |
| Completed, both flags set | Not eligible | Completion dialogue applies instead. |
| Failed, progress preserved | Not eligible | Active-attempt qualifier fails; offer a separately confirmed restart. |

This is a manual logical review of declared behavior, not a running game simulation.
The line fits Eldrin's formal register and addresses unfinished duties without
inventing a factual state. It remains a narrative proposal, not a GDD quotation.
The greeting is atmospheric rather than a complete quest briefing; the UI/objective
text must still communicate the two required actions.

The two objective events may occur in either order. Each sets only its own flag.
Completion reevaluates after each update and requires both flags. Failure preserves
flags; an explicit confirmed restart clears both and returns lifecycle to active.
These are proposed design contracts, not executable event bindings.

Remaining implementation decisions include abandonment/cancellation treatment,
activation and scene placement, dispatch/priority when dialogue situations overlap,
and reward delivery/idempotency. The saved repeat policies have not been silently
changed into a new policy: greeting remains once per playthrough, incomplete reminder
repeatable when eligible, completion once upon completion, with no scanner-bypass
reset. A designer must confirm how deliberate interactions dispatch playback and
persist suppression; a continuous eligibility check must not imply repeated audio.

## Local verification

The complete actual saved artifact/evidence/critique were refreshed through a
PostgreSQL read-only transaction, then rolled back. Network access was blocked
after that snapshot; candidate transformations and assessment ran in memory.

- Both observed baseline request gaps were reproduced: restart_event_intent and
  dialogue_progress_state.
- After correction, the bounded request/quest checks report no such gaps.
- Under the original scope, the empty runtime preview still blocks Grounding and
  Completeness. The old run cannot acquire deferral from this review package.
- Under a hypothetical new explicit design-only scope, the remaining scorecard
  blocker is Integration readiness: **16 proposals remain unconfirmed**.
- The raw critic still blocks approval. Its old result and fingerprint cannot
  serve as independent review of this changed candidate. No finding was deleted,
  silently dismissed, or converted into approval.
- Exact dialogue mirrors, source voice, unaffected sections, citations, reward,
  dependencies, runtime and preserved state-contract fields were asserted.
- **11 existing offline regressions passed, 99 deselected**, in 6.86 seconds.
  Selection covered saved progress/restart failures, raw-critic preservation,
  candidate mirrors, explicit runtime deferral and persisted scope binding.
  Repository conftest/cache/bytecode/plugin autoload were disabled, external
  sockets/PostgreSQL blocked; disposable SQLite was used where needed.
- **3 targeted browser fixture checks passed**: normal GDD consent submission,
  completed design-only run export blocking, and Blueprint Studio deferred actions.
  All API calls were intercepted; these are not live backend workflow acceptance.
- No new tests, dependencies, NVIDIA requests, shared-schema reset, commit or push.
- A final read-only recheck matched the original artifact and critic SHA-256
  recorded in the candidate provenance. Both environment-file hashes also matched
  the baseline; the saved legacy run retains all original blockers.

An initial diagnostic output attempted to access expired ORM identifiers after
rollback. Copying identifiers before rollback corrected that diagnostic error;
it was not an application failure or database mutation.

ECC AI Regression Testing guided replay/preservation assertions rather than adding
test-count-driven work. ECC Browser QA guided the targeted existing interaction
checks. No visual redesign or production-reliability claim is made.

## Acceptance checklist / next gate

1. Start a new isolated design-only QA run through the normal GDD review flow,
   using the existing frozen Frostpeak evidence and configured model routing.
   Do not toggle or rewrite the original run.
2. Only after fresh bounded authorization, run planner -> fresh generation ->
   independent critique. Count every retry/repair against the authorized total;
   stop when exhausted. Do not switch models or alter environment to force a pass.
3. Compare the fresh result against this candidate's acceptance cases, not its
   exact wording: correct source voice; three usable new lines; consistent mirrors;
   both partial states; failure/restart intent; both objective orders; exact rewards;
   unsupported details labelled proposals; no invented scene bindings.
4. Review each proposal individually. Retain evidence-backed human review of any
   critic false positive separately from proposal confirmation. Never reuse the
   original critique or invent a successful evaluation.
5. Verify save -> reload -> review status -> design brief in the actual dashboard.
   Approval, if later explicitly authorized, is design-only; runtime export,
   materialization and bundles must still reject it.
6. Stop expanding features until this one real-content journey passes. Unity and
   runtime acceptance remain later gates.

Fresh generation usefulness and hosted critic reliability remain open. This local
candidate is a concrete acceptance reference, not proof that GameMind can reliably
generate it unaided.
