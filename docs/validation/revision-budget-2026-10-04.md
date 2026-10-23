# Exhausted design-agent revision budget — 2026-10-04

## Scope and behavior

- Reproduced the enabled revision button at the configured limit. The durable API also accepted the extra rejection and transitioned the run to `revision_limit_reached` instead of rejecting it before mutation.
- The review API now returns HTTP 409 for `reject` when `revision_count >= max_revisions`, before resuming a checkpoint, recording review events, or enqueuing work.
- Exhaustion does not bypass quality checks or prevent otherwise valid approval. Existing terminal runs remain terminal; no historical checkpoint was reopened.
- A review-paused run with an exhausted budget no longer prevents a separately consented fresh run for the same source. Queued/running reviews and review-paused runs with revisions remaining still prevent duplicate active reviews.
- The dashboard displays the used budget, disables further revision requests, guards stale forms after refresh, and explains the historical exhausted state instead of calling it work in progress.

## Verification

- Test-first reproduction: browser expected a disabled button but observed an enabled one; durable API expected 409 but received 200 with a terminal revision-limit transition.
- Eight new backend cases cover inline/queued budget guards, at/above-limit values, repeated rejection without mutation, fresh-run consent, and approval compatibility.
- Workflow/job/focused-revision suite: 34 passed. Full default backend suite: 370 passed, 1 load test deselected, 84.97 seconds. Providers are mocked and database fixtures use only `gamemind_test`.
- Frontend lint and production build/type checking passed. Six focused browser cases cover three widths, approval compatibility, stale forms, and historical terminal state.
- Read-only live browser checks passed at 1440, 768, and 375px: revision disabled, approval blocked, runtime export absent, fresh-run consent visible, no page crashes or backend writes. The saved QA run response hash was unchanged.
- Broader dashboard fixtures initially timed out in account-recovery busy-state checks, including a serial rerun. Isolated cases passed. The harness now waits for initial network activity to settle before interacting with server-rendered forms; no account-recovery implementation was changed. With this readiness wait, all four account fixture cases and the full 70-case dashboard suite passed. Minimum measured semantic-text contrast across the existing rubric was 5.11:1. These fixture results are not live authentication acceptance or a proof that no timing issue remains under all conditions.
- Coverage percentage and the excluded load test were not measured in this change.

## QA dialogue policy selected by the user-delegated decision

These are review proposals, not facts extracted from the GDD and not activated runtime behavior:

- Link/file warnings: once per object per mission attempt.
- Firewall warnings: once per barrier per mission attempt.
- Reset only when the mission restarts; scanning, URL verification, quarantine, or crossing a barrier does not reset warning suppression. Do not invent a scanner-bypass mechanic.
- QA checks: same object/barrier twice produces one warning; a different object/barrier gets its own warning; mission restart allows the warning again; scanner actions alone do not allow repetition.

Keep dialogue intent aligned: URL warning for suspicious links, executable-file warning for suspicious files, literal-firewall warning for firewall encounters. This policy does not repair the saved v3 artifact or authorize release.

## Preserved live state and next gate

Workspace `qa-cyberrakshak-2026-10-03-c2600869`, run `56218f49-d469-4057-aad6-a5c891031dee`: `awaiting_review`, revisions 2/2, artifact v3. No saved draft, source, approval, runtime data, model configuration, API key, or Unity file was changed. No NVIDIA request was made.

Next: a fresh isolated generation/independent-critique acceptance cycle with renewed, bounded hosted-provider consent and explicit model routing. Correct dialogue trigger mapping, grounding gaps, and quest progression before considering approval. The existing draft remains blocked; this fix is not proof of creative generation or production reliability.
