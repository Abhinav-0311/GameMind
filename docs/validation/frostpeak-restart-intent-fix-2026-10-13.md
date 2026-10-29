# Saved Frostpeak restart intent — FRESH-06

## Outcome

The saved restart proposal is now flagged by a local review/approval blocker.
It previously passed the typed state contract because its flag reset set and
`lifecycle: active` were structurally valid. Those checks did not establish that
selecting abandonment or merely speaking after failure meant starting a new attempt.
This is a design-contract ambiguity, not a reproduced game-engine bug.

No saved draft was rewritten. No Unity implementation or runtime schema changed.

## Observed case and proposed intent

Saved run: `4c05934b-40d6-4a0e-8ac9-0df311a09129`.
Artifact: `cea14acb-54e2-4898-bdf0-3c4585b48344`.

Original `state_contract.restart.event`:

> Player selects 'Abandon Quest' from quest menu or interacts with Eldrin after quest failure

The declared restart clears `guards_cleared` and `flag_raised` and sets lifecycle
active. Both alternatives therefore promise a reset/reactivation without a separate
new-attempt decision. Proposal confirmation alone cannot clarify which behavior
the player should receive.

Recommended engine-neutral policy for review:

| Action | Intended treatment |
| --- | --- |
| Select Abandon Quest | Do not infer restart; settle cancellation/failure behavior separately. |
| Talk to Eldrin after failure | Present dialogue or the restart option; do not infer reset. |
| Confirm Restart Quest after failure | Explicit new attempt: clear all declared flags and set lifecycle active atomically. |

Human-authored candidate event:

> Player confirms Restart Quest to begin a new attempt after quest failure

This is a proposed design decision, not a GDD fact or verified event binding. It
does not settle abandonment semantics, reward dispatch, or restart after completion.
The candidate was evaluated only in memory and not saved or approved.

## Focused implementation

- `backend/app/design_agent/grounding.py`, `_request_coverage_gaps`: recognize
  the observed affirmative abandonment-selection and ordinary post-failure
  interaction alternatives in a typed restart event. Emit `restart_event_intent`
  under `quest_hooks`, naming the unsafe alternatives and requesting clarification.
- Existing critique completion merges this as a High system finding without
  removing original model findings. Existing approval recomputes the gap, even
  when the model reports ready and all assumptions are confirmed.
- `backend/test_quest_state_contract.py`: six focused cases cover the saved event,
  each unsafe alternative, a safe alternative beside an unsafe one, and explicit
  confirmation/negated wording remaining unchanged.

This is deliberately bounded English matching, not a general natural-language
intent parser. It matches complete affirmative alternatives; other wording and
other games still require human/independent review. No match is not acceptance.
There is no automatic event rewrite, model/prompt change or additional retry.

## Verification

- RED: **3 failed, 3 passed**, 33 deselected. The three failures reproduced absent
  restart-intent detection, not a runtime reset execution.
- GREEN focused replay: **6 passed**, 33 deselected, in **4.00 s**.
- Final bounded eight-file offline set: **219 passed in 14.14 s**. Includes those
  six cases and all prior selected checks; it is not the full backend suite.
  Selection: NVIDIA provider, local LLM provider, structured-output diagnostics,
  Phase 3 generation contract, generation-quality guards, quest state contract,
  finding-resolution audit and finding-approval policy tests.
- The saved-case approval regression first removes the separate progress-dialogue
  defect in an in-memory copy. Restart intent is then its sole request-coverage
  gap and still blocks approval with a ready critic and confirmed proposals.
- Replayed the complete actual saved artifact and evidence in a read-only database
  transaction: exactly one restart-intent gap; its High finding is merged while
  every original raw critic finding remains. Changing only the candidate event
  removes that gap. The dialogue contradiction and other quality blockers remain.
- Re-read artifact and critic hashes matched the previous report. Environment
  hashes also matched the baseline; scoped `git diff --check` passed.

Offline tests disabled bytecode, plugin autoload, repository `conftest.py`, and
pytest cache. Socket/PostgreSQL connections were blocked, and HTTP was restricted
to mocks or in-process TestClient. SQLite audit tests used disposable in-memory
databases; no shared schema reset or app lifespan ran. The separate actual-artifact
replay used read-only PostgreSQL transactions and rolled back.

No NVIDIA calls, installs, environment changes, existing-workspace data writes,
runtime approval, materialization, commit or push occurred. Local source/tests and
this note are the only intended changes. ECC AI Regression Testing guided replay
of the saved failure and isolation of the approval check.

## Remaining / next

Inspect the empty runtime preview (FRESH-05) against the existing dashboard contract
and engine-neutral integration requirements. Do not invent Unity bindings to fill
it. Critic reliability, fresh provider acceptance, and a full dashboard acceptance
walkthrough remain open; this step does not close those gates.
