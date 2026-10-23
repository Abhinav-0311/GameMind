# Quest state contract and independent critique

## Scope

New NVIDIA blueprint generations and quest-section revisions require a versioned
`state_contract` for every quest. Stored legacy drafts remain readable without
conversion. This changes design JSON, not database tables, environment settings,
model routing, runtime binding schemas or Unity code.

## How to integrate a reviewed contract

The contract is a proposal, not executable code. Review its events against the
cited GDD before approving it. Version `1` supports independent boolean objectives;
source-required sequencing or prerequisites need separate implementation review.

1. Start an attempt with lifecycle `active` and every declared objective flag
   `false`. Keep lifecycle separate from the flags.
2. Bind each objective's human-readable `event` to an observable game action.
   While active, that event sets only its own `flag` to `true`; other flags persist.
   Do not treat nearby presence or an animation as proof of the required action.
3. After **each** objective update, evaluate every `completion.required_flags`
   using AND. Only then set lifecycle to `completed`. Test all partial states and
   both action orders. Objective events must not mutate a terminal attempt.
4. While active, a declared failure event sets lifecycle to `failed` without
   clearing progress. The explicit restart event atomically clears all
   `restart.clear_flags` and sets lifecycle back to `active`.
5. Verify restart from partial and failed attempts. Review dialogue against zero,
   partial and complete progress; a line saying exactly one task remains does
   not fit a situation where both tasks can remain.
6. Keep reward dispatch, engine IDs and event wiring separate. `runtime: null`
   stays design-only. Approval does not materialize this contract into engine data.

The dashboard's existing recursive artifact view can display the JSON. The
downloadable technical brief includes the contract, integration notes and proposal
labels. No runtime export contract was changed.

## Validation and trust boundaries

- Schema checks reject duplicate/reserved flags, missing/renamed objectives,
  incomplete completion/reset sets, OR completion, last-action-only reevaluation,
  invalid lifecycle values and competing free-form assignment fields.
- Typed integration checks use these fields instead of parsing arrow notation.
  Legacy prose checks are retained for compatibility and are not semantic proof.
- Revisions cannot silently remove a contract from a retained quest.
- The independent critic receives the human request, draft, evidence and proposal
  status, not local failure conclusions. Deterministic blockers are merged after
  review without removing original model findings.
- Full-blueprint and scoped-section repair guards preserve readable design data
  and citations. Repair cannot invent, change or remove a state contract or
  silently discard an out-of-scope section. Metadata-only repair remains allowed;
  closing-delimiter recovery still requires review.

## Verification boundary

Initial focused offline selection: **312 passed, 5 deselected in 8.45 seconds**.
The five database-dependent cases were excluded; repository `conftest.py` and
pytest's cache provider were disabled to avoid resetting the existing database.
The selection covers contracts, request/approval gates, scoped revisions, prompt
boundaries, JSON repair/recovery and the portable brief. `git diff --check` passed
for the touched production files. Environment-file hashes remained unchanged.

### Partial-revision preservation follow-up

Independent verification reproduced a gap: partial quest-section JSON repair
could invent a missing contract, pass the normal revision adapter and scoped
revision gate, and return without a recovery-review flag. This was an offline
mock-transport reproduction, not a hosted request or persistent approval.

Scoped revision response models now inherit an explicit application marker.
The existing original-versus-repaired preservation check applies to their selected
sections as well as full blueprints. It rejects invented/changed/removed contract
content, dropped quests, changed citations and discarded out-of-scope sections.
It still accepts metadata-only correction with unchanged design data.

Seven new negative cases failed before the fix and pass afterward. The unchanged
metadata-only repair case also passes. Re-running the original missing-contract
probe now fails with `structured_output_invalid` after two mock transport calls.
Final focused regression selection: **320 passed, 5 deselected in 9.42 seconds**.
In-memory Python syntax checks and `git diff --check` passed. Environment hashes
remain unchanged; no database or runtime approval operations were performed.

To rerun the targeted checks from `backend` without repository DB fixtures:

```powershell
.\.venv312\Scripts\python.exe -B -m pytest --noconftest -p no:cacheprovider test_quest_state_contract.py -k partial -q
```

Offline regression checks use hand-authored contracts and mocked transport. They
do not prove fresh NVIDIA output quality, browser acceptance, engine event wiring,
production reliability or the full database-dependent suite. No NVIDIA request,
persistent approval or environment change was made for this implementation.

## Shared-progress dialogue follow-up

The bounded live Frostpeak QA run `13527cca-1b95-400d-a720-1a31eff553a6`
returned clean generation JSON but failed semantic acceptance. Its progress
situation included zero and partial completion, while its line asserted that
guards remain and the flag is down. Either assertion can be false after one
objective completes. The independent critic missed this mismatch.

Generation and revision guidance now requires a shared reminder to fit every
incomplete flag combination, without claiming a fixed remaining count or a
specific objective's current state. The compact NPC dialogue revision also
receives original situation/line pairs and read-only quest-state context;
its response scope still cannot change quests.

A bounded English check now flags recognized fixed-state/count assertions in
explicit zero/partial-progress situations for a single typed multi-objective
quest. It is merged after independent critique and recomputed before approval,
even when proposals are confirmed. It neither rewrites dialogue nor removes
model findings. Questions and conditional instructions are retained. Multiple
quests, unknown wording and narrower state-specific situations remain for
independent/human review; absence of this signal is not semantic acceptance.

Verification: six new assertions failed before the first fix; the compact
revision-context regression separately reproduced missing situation context.
Final focused offline selection: **332 passed, 5 deselected in 8.38 seconds**.
A read-only check against the actual saved QA artifact confirmed the new blocker
and denied the pure approval validator even with a mock-ready critic and all
proposal confirmations. An in-memory neutral replacement cleared this specific
gap. No saved draft, critique, database record, environment setting or model
configuration was changed during that check; no NVIDIA request was sent.

For a future reviewed revision, test the spoken line at `(false, false)`,
`(true, false)` and `(false, true)`, and exclude it at `(true, true)`. Preserve
voice, citations and rewards. If the same line exists in quest dialogue hooks,
target both NPC and quest sections; an NPC-only patch intentionally preserves
unrelated quest content. Fresh generation acceptance, critic false positives,
repeat/reset consistency and scene-proposal labelling remain open.

## Critic review-contract follow-up

The same saved Frostpeak critic alleged missing proposal labels for failure,
restart and dialogue despite the record assumptions, and treated application
state-contract fields as details the GDD needed to specify. Its task also
unconditionally requested legacy Objective/Event/State/Check prose for typed
quests, creating conflicting integration requirements.

The critic task is now a single classify-ground-review rubric, reduced from
629 words / 4,591 characters to 399 words / 2,885 characters. Application field
semantics explicitly describe `mode=all`, per-objective reevaluation, persistent
flags, terminal attempts and atomic restart. Proposed event meanings still
require source compatibility; enum semantics do not verify a binding. Legacy
prose checks are explicitly legacy-only. Missing-label findings must identify
the assertion and why existing labels do not cover it. Conditional no-op
recommendations and duplicate findings are discouraged. No response schema,
model, token budget, approval rule or environment configuration changed.

Verification: the new review-contract regression failed before the fix.
Final focused selection: **333 passed, 5 deselected in 9.66 seconds**. A read-only
offline replay of the saved provider response preserved all seven original
findings and appended the known dialogue-state blocker after model review.
The critic input retained source evidence, quest content and proposal labels,
without local diagnostic conclusions. Saved artifact and critique hashes and
environment-file hashes remained unchanged. `git diff --check` passed.

This is an input-contract correction, **not proof that hosted false positives
are resolved**. Replaying a saved answer cannot measure the new prompt's model
judgments. No NVIDIA request, database write or runtime approval occurred.
Fresh authorized acceptance must show fewer bogus label findings while still
catching partial-state dialogue defects, wrong rewards, actual missing labels
and source contradictions. Do not filter findings or confirm proposals merely
to obtain a passing verdict. Repeat/reset consistency and scene-proposal
labelling remain the next local issues.

## Greeting repeat/reset follow-up (2026-10-12)

The saved Frostpeak greeting declared `on_first_interaction` / `first greeting`
but promised repetition on each interaction, with an unspecified quest-state
change as reset. The server-derived manual test separately promised eligibility
after reset regardless of situation. These are inconsistent design instructions,
not evidence of a verified runtime bug.

Shared generation/revision guidance now distinguishes situation eligibility,
repetition limit and an explicitly named reset (or no reset), and requires
mapping/implementation-note consistency. It does not replace conflicting human
direction. A small English guard blocks an explicit first-event declaration
paired with an unqualified repeat-each/every-interaction clause. It is merged
after independent critique and recomputed before approval; proposal confirmation
cannot waive it. Negated, qualified and unknown prose remains for review. The
guard does not interpret arbitrary policies, cross-check all scene notes or
establish reset-event reachability.

Derived manual tests no longer promise automatic replay. They require a stated
reset, rechecking eligibility, and continued suppression when a suppressed line
has no permitted reset. The compact-pair maximum still fits the existing
1,500-character regression bound. Exact spoken text and repeat policy are kept.

Verification: four new test cases failed before implementation; five conservative
reference cases already passed. Final focused offline selection: **342 passed,
5 deselected in 8.56 seconds**, including existing literal human-policy and compact
revision checks. This is not the full database-dependent suite. A read-only,
rolled-back database transaction confirmed the saved greeting is flagged, the
pure approval validator refuses the saved draft with a mock-ready critic and
proposal confirmations, and original critic findings remain intact. An in-memory
`Once ever; no reset.` reference clears only this repeat conflict; it is not an
adopted Frostpeak design decision. Saved artifact/critique hashes and both env-file
hashes stayed unchanged. No NVIDIA request, database write or runtime approval.

Local guidance and the known-conflict guard are implemented. Fresh model acceptance
is still open: inspect the exact greeting, progress and completion mappings,
named resets and their scene notes together. Scene activation/placement proposal
labelling remains the next local issue; no UI or Unity scope was added here.

## Scene-integration proposal follow-up (2026-10-12)

FQA-C04 in the same saved Frostpeak draft asserted that Eldrin's Watchtower
overlooks Ash Pass and that entering the pass activates the quest. The sample
GDD names Eldrin as Archmage of the Watchtower and supplies the guard/flag
objectives, but does not establish that spatial relationship or activation
event. Existing dialogue/state-contract assumptions did not specifically label
these scene instructions.

Generation and revision now ask for source constraints to remain separate from
proposed scene placement and activation, with proposal scope in the relevant
record's assumptions. Critic field guidance explicitly covers implementation
notes: plans are not active engine behavior, generic dialogue/state-contract
labels do not automatically cover unrelated scene claims, and labels never
excuse source contradictions. No critic findings are filtered or rewritten.

Local normalization conservatively renames explicitly prefixed `Scene integration:`
notes to `Scene integration proposal:` and adds one record-scoped confirmation
requirement. It preserves the instruction body and unrelated notes, is
idempotent, and does not duplicate every instruction into assumptions. This is
a status-label safeguard, not an entailment classifier: it also labels
source-constrained integration plans, without asserting that their source facts
are unsupported. Arbitrary unprefixed prose, other languages and source
contradictions still require independent/human review. It does not infer a
location, activation event, engine binding or approved runtime behavior.

Five focused regression cases failed before implementation (three new cases
and two extended critic cases). Final focused offline selection: **345 passed,
5 deselected in 9.22 seconds**. Confirmation tests exercise the pure shared
approval gate: one unconfirmed scene record blocks; all explicit confirmations
permit an otherwise valid reference; deleting scene assumptions does not bypass
their reconstruction during approval. This does not perform runtime approval.

A rolled-back read-only transaction checked the actual saved artifact. Both
scene notes were labelled only in memory, two scene confirmations remained
pending, and source IDs, instruction bodies, rewards, objectives and state
contract stayed intact. An offline replay retained every saved critic finding
and supplied the new field guidance and scene assumptions in the critic input.
Saved artifact, critique and evidence were unchanged, as were both env-file
hashes. Syntax checks and tracked-file whitespace checks passed. No hosted
request, database write, installation, commit, UI change or Unity work occurred.

Reproduce the focused cases from `backend`, without the DB fixture loader:

```powershell
.\.venv312\Scripts\python.exe -B -m pytest --noconftest -p no:cacheprovider test_generation_quality_guards.py test_design_prompt_usability.py -k 'scene_integration or scene_guidance or critic_receives_field_contracts' -q
```

The known local follow-ups now have regression checks; they do not prove fresh
model acceptance. Next is a newly authorized, bounded fresh acceptance check
against the same criteria, not further feature expansion. Browser acceptance
and the isolated database-dependent suite remain separate outstanding gates.

## First-contact greeting coverage correction (2026-10-12)

The subsequent isolated Frostpeak acceptance run
`bbefafeb-545c-4622-be70-fd7f2625723c` exhausted its five-request authorization.
Its version-2 draft (`31abcad5-db7d-402a-8c7c-55d235e2bce5`) contains
`first_interaction` / `Player first encounters Eldrin in the Watchtower`, but
the bounded English coverage check incorrectly reported missing greeting
dialogue. It recognized `first encounter`, not `first encounters` or
`first interaction` after trigger separator normalization.

The correction adds those two explicit first-contact forms to the existing
greeting coverage pattern. It does not change generated text, repeat policy,
saved critiques, approval rules or other dialogue stages. This remains a label
coverage check, not proof that speech is useful, source-grounded or correctly
triggered in a game. Negation, arbitrary prose and multilingual semantics are
not newly interpreted.

Test-first verification reproduced four failing first-contact cases; four
ordinary idle/return/interaction controls already passed. After correction,
all eight cases pass, including preservation of an independent high-severity
finding. The broader focused offline selection passed **353 tests, 5 deselected
in 9.04 seconds**, using `--noconftest -p no:cacheprovider` to avoid the project
database fixtures. This is not a full backend-suite or browser result.

A rolled-back `SET TRANSACTION READ ONLY` check recomputed quality on a copy of
the actual saved version-2 draft: no greeting gap (and no other currently
recognized request gap), but integration readiness still blocked with ten
unconfirmed assumptions. Version 2 has no valid independent critique; the pure
approval gate refused it with `Independent critique must be resolved.` The
version-1 critic is not a version-2 review. Saved artifacts, critiques and
evidence hashes were unchanged; no runtime blueprint exists for this draft.

The fresh acceptance outcome remains failed. Invented scene prerequisites
survived the targeted revision, and the final hosted critic was truncated.
Empty deterministic gap lists do not resolve those issues. Next local point:
inspect and repair focused-revision compliance against explicit rejected
prerequisites, preserving source-supported constraints and unrelated sections.
No NVIDIA requests, environment changes, saved QA writes, runtime approval,
installation, commit, UI change or Unity work occurred in this correction.

Reproduce this point from `backend`:

```powershell
.\.venv312\Scripts\python.exe -B -m pytest --noconftest -p no:cacheprovider test_phase3_generation_contract.py -k 'first_contact_covers or ordinary_interactions_do_not' -q
```

## Revision requirement handoff follow-up (2026-10-12)

Read-only inspection of the same isolated acceptance run confirmed that the
complete human rejection reached the previous revision: it explicitly asked
to remove invented tutorial and leaving-Watchtower prerequisites. Both were
retained in version 2 despite other requested changes. This was model
noncompliance, not a missing rejection string. The local section-change gate
correctly detected changes but does not establish arbitrary semantic compliance.

One concrete input gap was found: revision requests did not carry the original
run objective, freshness flag and saved dialogue policy together with the
rejection reason. They now do, through the normal workflow, full selected-section
revision, compact NPC dialogue patch and optional resilient fallback. Human
requirements remain separate from frozen evidence and old draft content.
Original freshness also drives source-example withholding during revision.
Locked repeat/reset policy still remains unchanged by server normalization.

Shared revision guidance now requires addressing every requested correction,
rechecking applicable implementation notes and assumptions, removing explicitly
rejected dependencies rather than merely relabelling them, and retaining source
constraints and unrelated scope. No new semantic parser, success-attestation
schema, model, provider request or automatic retry was added. Independent
critique and human inspection remain necessary; no finding is suppressed.

A directly related fallback test exposed an existing schema error: deterministic
mock revisions inserted `review_adjustments` into closed NPC/quest content.
Those typed sections now keep that directive in provider metadata instead.
Legacy generic-section behavior is preserved. This is schema validity and
observable degradation, not proof that a mock revision satisfies the request.

Verification: three handoff regressions failed before implementation. The new
fallback exercise then reproduced the forbidden-field error before its fix.
Final focused offline selection: **358 passed, 5 deselected in 9.36 seconds**.
Tests cover both hosted-adapter revision shapes without HTTP, original-request
and scope preservation, and both typed mock-fallback sections. Existing
database-backed provider doubles were updated for the optional keyword;
their full integration tests were not run here.

An offline capturing-provider replay used the saved real version-1 inputs,
full rejection and version-2 response inside a rolled-back read-only database
transaction. Original requirements and rejection reached the prompt; seven
unselected sections and saved artifact/critic/evidence hashes were preserved.
The old response still contains both rejected prerequisite notes and still
passes the existing material-change gate. This deliberately records the
remaining semantic gap rather than treating a prompt change as a model-quality
pass. Saved drafts were not repaired, approved or rewritten.

Status: local requirement handoff and typed-fallback fixes are implemented;
fresh revision compliance is **not verified**. The exhausted five-request
authorization was not reused. A future explicitly authorized acceptance check
must inspect the actual regenerated notes and obtain a complete critique for
the same artifact version before approval. Browser acceptance and the isolated
database-dependent suite remain separate outstanding gates. No environment
change, installation, commit, UI work or Unity work occurred.

Reproduce the new local cases from `backend`:

```powershell
.\.venv312\Scripts\python.exe -B -m pytest --noconftest -p no:cacheprovider test_design_prompt_usability.py test_phase3_generation_contract.py -k 'revision_keeps_original or workflow_passes_original_requirements or revision_fallback_forwards' -q
```

## Focused notes-only correction (2026-10-12)

The subsequent authorized revision check used two of three permitted NVIDIA
requests; the unused request was closed. Run
`75e14b8b-2cad-4e24-ae02-8a26db2f98ce`, artifact
`fc5103a7-df0a-43fa-9f76-6a0561b0233e` remains awaiting review, not accepted.
The raw revision retained the rejected tutorial and leaving-Watchtower scene
prerequisites. No saved draft or independent finding was rewritten here.

Local inspection found that the material-change gate rejected *any* correction
consisting solely of removing authored integration notes. It now permits that
only when every other field in every selected section is exactly preserved.
Every selected section must still materially change; server boilerplate and
cosmetic changes do not count. Mixed partial rewrites cannot use note deletion
as a substitute for a missing correction. Unselected-section protection and
independent-critique/approval gates are unchanged. The provider instruction now
describes this exception rather than categorically forbidding note removal.

An in-memory replay of the saved Frostpeak artifact removed only the two whole
rejected scene notes, retained all other fields exactly, passed the material
gate, and remained blocked by the unchanged independent critique. This was a
local candidate, not fresh model generation, source entailment, a saved repair,
dashboard acceptance, or runtime proof. There were no hosted calls or database
access during this follow-up. Whether the model follows the requested correction
is still unproven; this exception does not evaluate arbitrary human intent.

Verification: the focused positive regression and updated prompt assertion
failed before implementation; negative scope/material-change cases passed.
The wider offline selection passed **363 tests, 5 deselected**. Existing
retained-timer/partial-rewrite regressions still pass. No environment change,
installation, commit, approval, UI work or Unity work occurred.

## Dashboard revision scope follow-up (2026-10-12)

Static inspection confirmed a dashboard/API mismatch: the backend accepts
multiple `target_sections`, while the dashboard's single select always sent
one. Linked NPC/quest corrections therefore could not be requested together
through the dashboard, despite the existing backend contract supporting them.

The existing revision form now uses native section checkboxes, defaults to the
currently viewed section, displays the selected count, and blocks submission
with no selection. Payload targets follow the canonical section order; reason
text cannot expand the selected scope. Reopening starts with the current section
alone rather than silently retaining a previous broader selection. No backend
schema, provider, model, or approval rule changed. Emil design-engineering
principles informed the restrained two-column control, 44px labels, keyboard
focus, and lack of decorative animation.

Verification: the focused browser test first failed against the old single
select. Four updated checks pass for single/linked targets at 1440px/light and
375px/dark, including keyboard selection, empty-scope blocking, exact POST
payloads, reopening defaults, and no horizontal overflow. The complete existing
dashboard fixture suite passed **76 checks**, with zero real backend mutations
or hosted requests. Screenshot inspection confirmed label fit and visible focus.
Production build, no-emit TypeScript, scoped ESLint, JavaScript syntax, and diff
whitespace checks passed.

The frontend was started on loopback using existing dependencies. Its first
sandboxed launch failed with filesystem access denied; the permitted local
launch and browser run succeeded outside that sandbox. An already-installed
Playwright browser was reused; no packages or browsers were installed. Backend
and database services were not started. API calls in the browser suite were
intercepted, so this is not live backend/revision/generation acceptance. Both
environment-file hashes match the preceding check; saved QA workspaces were
untouched. Fresh model compliance remains open and requires fresh authorization.

## Current-draft critique boundary (2026-10-12)

The next authorized check used **3/3 NVIDIA requests** in isolated workspace
`qa-frostpeak-notes-20261012-d8d44fa7`, run
`997e9116-e86d-46fd-9fbb-1dab64357c76`: a truncated 2048-token revision,
the existing successful 4096-token retry, and a complete independent critique.
Provider time was 38.36 seconds and reported usage was 33,942 tokens; dollar
cost was unavailable. This allowance is exhausted and closed.

The actual raw revision removed exactly the two rejected scene-note entries.
The saved artifact, `4d826711-b3f4-450e-8282-b1ceed22de67`, matches that intended
notes-only correction exactly: all other fields, seven unselected sections,
source artifact, and isolated seed were preserved. This is revision compliance,
not fresh creative generation, retrieval, public-API/checkpoint acceptance,
or runtime proof.

The raw critic nevertheless repeated both deletion requests as high findings.
Both quoted notes were absent from the raw revision, saved artifact, and exact
artifact projection sent for critique, but present in historical rejection text.
Conflating that feedback with current content is the likely cause, not a proven
model-internal explanation. Critique
`ee353dd2-9c6c-4af6-abf0-25b1103793ef` remains unchanged and needs revision;
the disagreement is saved separately in the new QA run's manual assessment.
Unconfirmed assumptions, ambiguous progress wording, and inherited issues in
unselected memory/runtime-preview sections still need review. No approval was
granted.

Across 38 baseline tables, 37 outside-QA fingerprints were unchanged. The one
global telemetry-table difference coincided with the already-running cleanup
worker's five-minute cycle at 07:33:25 UTC within the QA interval; no existing
project-scoped table change was detected. This is not a claim of full global
database immutability. Environment hashes were unchanged.

The local follow-up adds an explicit review-basis label and current-draft
guidance to the normal NVIDIA critique input. Historical feedback remains
visible and unmodified as a requirement, not presumed current defect evidence.
Findings must refer to the current field/value, or the section with a missing
requirement. A corrected earlier defect must not be repeated, while a retained
or relocated defect and unrelated current problems must still be examined.
No result filter, auto-pass rule, output schema, provider routing, or approval
logic was added or changed.

One parameterized capturing-provider regression exercises removed and retained
notes. Both cases failed before implementation and pass afterward. It verifies
input/artifact/request preservation and retains even the supplied stale high
finding; it does not simulate a model learning to judge correctly. The wider
offline selection passed **365 tests, 5 deselected in 9.33 seconds**. The five
database-dependent cases remain outside this safe no-conftest selection; this
is not a full backend-suite result. Python syntax checks passed. Coverage
instrumentation was unavailable locally and was not installed; no coverage
percentage is claimed.

This local follow-up made no hosted calls and did not rewrite saved QA records,
environment files, or runtime approvals. No installation or commit occurred.
Live critic behavior with the revised input remains unverified and needs a new,
separately authorized check; the exhausted allowance is not reusable.

## Separate current-artifact critique from revision history (2026-10-12)

The subsequent authorized critic-only check disproved the preceding prompt-only
approach. In isolated workspace `qa-frostpeak-critic-20261012-e08053d8`, run
`6d0b19a1-4d18-46bf-885c-e39e80a8111e`, the critic repeated both already-removed
scene notes as high findings. Both notes were absent from the exact artifact
projection and present only in historical rejection text. Critique
`c55ea0df-70ca-4d19-b933-2afb1b333e23` remains unchanged; the manual disagreement
was recorded separately, without approval. One of two permitted requests was
used (3.069 provider seconds, 9,492 reported tokens); the allowance, including
the unused request, is closed. This is observed false-positive behavior, not
proof of the model's internal cause.

The local fix now sends only `objective`, `fresh_dialogue` and `dialogue_policy`
as critic requirements. The workflow excludes rejection history, and the NVIDIA
adapter independently allowlists those fields for direct callers. The allowlist
applies to both the prominent human-request text and `review_context.request`.
False and null values are preserved; caller data is not mutated. Current
artifact/evidence content is not scrubbed. Existing exact-duplicate projection
rules remain unchanged, so a rejected note still in the current artifact stays
visible to the critic. No findings are suppressed or rewritten by this fix.

The reviser still receives the complete rejection reason, selected sections
and original requirements. Review events, workflow state and saved audit
history are unchanged. Critique is explicitly scoped to current-artifact
quality against evidence and original requirements: it does not establish
compliance with arbitrary historical free-text revision requests. That remains
a separate human/revision-compliance responsibility. Approval rules, model
routing, schemas and environment settings were not changed.

Existing regressions were strengthened rather than increasing the suite count.
Before implementation, three boundary checks failed and the revision-feedback
preservation check passed. After implementation, all four passed. Captured
prompts verify that removed notes cannot leak through history, retained notes
remain visible in the artifact, original requirements reach both prompt
locations, and even a supplied stale high finding is retained unchanged.
These are offline contract tests, not semantic model acceptance.

The wider offline selection passed **365 tests, 5 deselected in 13.22 seconds**.
The five database-dependent cases were deliberately excluded from the
no-conftest selection; this is not a full backend-suite or browser acceptance
result. Syntax checks passed for both production files and both updated test
files. Git whitespace checks passed; existing line-ending warnings remain.
Environment hashes match the preceding baseline. Coverage tooling was not
installed and no coverage percentage is claimed.

This implementation made no hosted calls, rewrote no saved QA records, and
performed no installation, commit, push or runtime approval. Live behavior with
the new input boundary remains unverified and requires fresh explicit consent.

## Dashboard list-URL loading regression (2026-10-12)

The read-only walkthrough reproduced unavailable Home, Sources and Design Agent
data in both the in-app browser and installed Chrome 155 using a fresh isolated
profile. Backend health, direct API GETs and CORS preflights succeeded. The
frontend requested `/api/v1/documents` and `/api/v1/blueprints`, whereas the
backend defines its list handlers at `/api/v1/documents/` and
`/api/v1/blueprints/`. The former URLs return 307 redirects.

A first comparison made after a failed redirect also failed on the canonical
document URL. A new browser context requesting canonical URLs first returned
200 for documents, blueprints and design-agent runs, then failed on the
redirecting document URL. This establishes redirect-dependent failure on this
machine, not the internal browser/network cause or universal behavior across
deployments. No CORS, authentication, proxy or browser security settings were
weakened to make the check pass.

The fix changes exactly three client list calls: dashboard documents, runtime
documents and dashboard blueprints now use the canonical backend URLs. Existing
fixture keys were aligned with those URLs, and the fixture harness explicitly
rejects noncanonical list calls instead of masking them with a successful
response. The existing focused Home partial-failure test failed before the
client correction (documents unavailable instead of the expected source count)
and passed afterward. No new test cases or dependencies were added.

Verification:

- **76 dashboard state checks passed**, including source-load recovery,
  consent, version-bound proposals, approval blockers, responsive states and
  keyboard interactions. All backend calls in this suite were intercepted;
  fixture POSTs are not live mutation/consent acceptance.
- A separate real-backend Chrome check loaded Home, Sources, the indexed
  document details and the saved isolated QA review successfully. Observed API
  responses were 200, with no failed API fetches, no 307 redirects and no page
  crashes. Approval remained visibly blocked. No form was submitted and all
  non-read HTTP methods and external services were blocked in this live check.
- `tsc --noEmit --incremental false`, targeted ESLint, test-script syntax and
  Git whitespace checks passed. A production build and backend suite were not
  rerun for this three-string client fix; no coverage percentage is claimed.
- `.env` and `.env.example` hashes match the prior baseline. No NVIDIA calls,
  installations, commits, pushes, draft updates or runtime approvals occurred.

The source contains a separate presentability issue at
`frontend/src/app/design-agent/page.tsx`: the complete run objective is rendered
as a large heading. The verified long-objective run fills the initial viewport
and pushes artifact/review controls below the fold. This was observed but not
changed in the list-URL fix. Full dashboard workflow and generation-quality
acceptance remain open; restored loading alone does not establish either.

## Compact review objective header (2026-10-12)

The next focused UI change resolves the oversized-objective heading observed
above. The run header now has a short "Design review" title and a two-line
objective preview. A native "Full objective" disclosure retains the complete,
unmodified objective in readable, wrapping text. The visual preview is hidden
from accessibility APIs to avoid duplicate objective text; the full text is
available through the keyboard-accessible disclosure. Opening it makes no API
request. Disclosure identity is scoped to the run, so switching runs does not
reuse another run's expanded state. No animation or dependency was added.

Self-review caught one remaining mobile problem: history and Refresh were
stacked, leaving the artifact heading below the initial viewport. They now
share a responsive row while retaining 44-pixel control heights. Long objective
tokens wrap rather than causing horizontal overflow. Existing empty, loading,
error, consent, revision and approval behavior was left unchanged.

The existing approval-blocker test was extended to 1440, 768 and 375 pixels with
a long objective and an unbroken token. Before the UI fix it failed because
the artifact was below the viewport. The first implementation passed desktop
and tablet but still failed mobile; after the controls adjustment all three
passed. Checks cover exact full-text preservation, collapsed initial state,
Enter/Space and pointer operation, expanded-text overflow, and blocked approval.
The total suite increased from 76 to **78 passing dashboard state checks** by
parameterizing that existing test, not by introducing another test framework.
These fixture tests intercept all backend requests, including simulated writes.

A separate read-only live-backend Chrome check passed at 1440 and 375 pixels in
both light and dark themes. All six observed API responses in each case were
200; no failed requests, page crashes, blocked write attempts or external
requests occurred. The saved objective's 1,426 characters were preserved
exactly. Artifact heading y positions were approximately 661 and 851 pixels
respectively in a 900-pixel viewport; approval stayed blocked. Mobile approval
controls still follow the artifact vertically, so this does not claim that
every review control fits above the fold on a phone. Desktop/mobile screenshots
were saved outside the project under the authorized visualization directory.

TypeScript (`tsc --noEmit --incremental false`), targeted ESLint and whitespace
checks passed. The production build, backend suite, screen-reader testing and
physical-device testing were not run; no coverage percentage or full workflow
acceptance is claimed. Environment hashes are unchanged. No NVIDIA call, draft
update, approval, installation, commit or push occurred. Critic-quality and
remaining design decisions remain open; this is a presentation fix only.

## Frozen evidence inspection in draft review (2026-10-12)

The saved Frostpeak walkthrough confirmed a review gap: section citation counts
and record UUIDs were visible, but the actual cited source excerpts were not.
The draft also retains ambiguous greeting eligibility, an unsupported Ash Pass
location/proximity activation, a potentially unclear partial-progress reminder,
and wording that converts an unspecified quest-giver role into a negative fact.
Those draft fields and the raw critic finding were not rewritten by this fix.

A new read-only endpoint serves
`GET /api/v1/design-agent/runs/{run_id}/artifacts/{artifact_id}/evidence`.
It reuses workspace/auth dependencies, scopes the run, artifact and snapshot to
the selected workspace, and follows the artifact's exact snapshot ID. It never
substitutes the latest retrieval revision or current document chunks. Response
fields are explicitly limited to snapshot identity/revision and source text,
title, document ID, chunk ID and chunk index. No migration is required.

The draft has a collapsed native "Source evidence" disclosure. Its first open
loads that artifact's snapshot; section switches show only that section's cited
excerpts and reuse the same read. Missing references, empty citation lists,
loading and retryable errors are explicit. A mismatched response artifact is
rejected. Text renders as escaped plain text, not HTML. Component identity is
keyed by run and artifact so another draft cannot reuse its cached evidence.
Self-review improved reference metadata wrapping on narrow screens. No motion,
dependency, approval override or new hosted-provider path was introduced.

Test-first evidence: the endpoint returned 404 before implementation, and the
browser reproducer could not find the disclosure. The isolated endpoint checks
then passed, including historical revision selection, safe response projection,
foreign run/artifact/snapshot isolation, missing artifact/snapshot, and auth
dependency rejection. These use disposable SQLite tables and a SELECT-only
guard, not the application lifespan or the shared destructive conftest.

The final offline backend selection passed **95 tests in 5.15 seconds**:
`docker compose exec -T -e PYTHONDONTWRITEBYTECODE=1 -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 backend pytest --noconftest -p no:cacheprovider test_design_agent_evidence.py test_quest_state_contract.py test_phase3_generation_contract.py -q`.
Seven of these are new evidence endpoint cases; the rest are existing quest and
generation/approval contract checks. An earlier Windows virtualenv invocation
did not return a result and was interrupted; it is not counted as a pass.

The final dashboard suite passed **80 state checks**. Three existing responsive
review checks now cover on-demand exact text, escaped HTML, missing references,
empty-section evidence and cache reuse. Two new retry cases cover missing
snapshots and wrong-artifact responses. All API requests in this suite are
intercepted; it is not live write/consent acceptance.

Live read-only Chrome checks passed at 1440, 768 and 375 pixels in both themes.
Each case observed eight API responses, all 200, with no failed requests, page
errors, external requests or attempted writes. Opening evidence read once;
the NPC quote and both quest excerpts exactly matched the frozen response.
Keyboard open/close and horizontal-overflow checks passed. Fresh run reads
confirmed that artifact, critique and lifecycle status were unchanged and
approval remained disabled. Screenshots were saved outside the project.

TypeScript, targeted ESLint and whitespace checks passed. Environment hashes
remain unchanged. No NVIDIA calls, saved-draft edits, runtime approvals,
installation, staging, commit or push occurred. This is evidence-inspection
acceptance, not generation-quality, production, full-backend-suite, physical
device, screen-reader or coverage-percentage acceptance. The critic false
positive and the remaining draft decisions still require separate resolution.
