# Content-first initial generation

## Why this change

Fresh normal-flow QA run `86af9a14-0b73-4dbf-a386-36083f36890d` failed before a draft was stored. Its response mixed objective, failure and restart keys and referenced nonexistent quests. This change addresses model-authored bookkeeping, not all defects in that response. Saved failed runs remain unchanged.

## Scope

- New contract-2 initial generation uses `ContentBlueprintDraft`. The model writes objective/completion-action pairs, readable failure causes, optional explicit restart confirmation, and spoken mappings with a stage and zero-based quest index.
- `assemble_content_draft` derives quest/trigger IDs, distinct event keys, objective flags, complete required/clear lists and dialogue eligibility in a new copy. It validates the result against the existing governed contract. Derived choices are labelled unverified implementation proposals requiring review.
- The server does not fill missing facts, rewards, citations, action descriptions or unsupported records. Invalid indexes, missing quest associations, failed dialogue without a failure condition and duplicate objectives are rejected. Quantity-loss checks still inspect authored objective and completion-action text.
- The ordinary generation adapter returns the existing canonical blueprint shape to the unchanged workflow. Independent critique, finding resolution, human approval and export gates remain in place. Metadata identifies the internal generation contract as `content_first_v1`.
- The existing scoped revision wire contract and legacy generation remain unchanged. No stored draft is migrated, repaired, approved or exported by this change. The earlier scaffold-dependent QA helper is not a production dependency.
- Assembly failures stop without a semantic repair request. Sanitized failure diagnostics retain completed-response usage; they do not expose model text or credentials in the user-facing exception. Original raw QA responses remain in their existing isolated records.

## Verification performed

- **336 selected container checks passed**, with five shared-database fixture cases and four host-document cases excluded. The latter four passed on the host: two dialogue-source projection cases and two saved-query/source-coverage cases. This is **340 distinct selected checks**, not the full backend suite.
- All **13 new focused cases** also passed under the existing Windows Python environment. These overlap the container selection and are not added again to the distinct total.
- Coverage includes deterministic assembly, input immutability, reordered two-quest/two-NPC references, exact action-key coverage, null failure/restart, invalid references/objectives, missing citations, quantity loss, wire-schema constraints, runtime deferral, syntax recovery, no semantic repair, sanitized errors and token accounting. Existing grounded mocked-HTTP generation/revision and approval regressions passed.
- Test runners disabled destructive shared-database conftest, pytest cache and bytecode writes; external connections and shared PostgreSQL access were blocked. HTTP tests used mocked/in-process transports. The host reported an existing Starlette/AnyIO deprecation warning.
- Tracked diff whitespace checks passed. `.env` and `.env.example` hashes match the pre-change baseline. No dependency, model, environment, migration, frontend, commit or push changes were made in this chunk.

## Still unverified

No NVIDIA requests, fresh dashboard submission, real-data approval/export or Unity execution were performed in this chunk. Decoder acceptance of this new schema and useful source-grounded creative output remain unproven. Structural consistency cannot establish correct source interpretation, observable completion conditions or dialogue quality; independent and human review still matter.

The next acceptance gate is a newly bounded NVIDIA normal-flow run in a new isolated QA workspace, reviewing the actual draft and critique before any legitimate approval and export. Previously closed request budgets must not be reused. Do not retrofit the failed saved responses into passing examples.

## Citation-completion follow-up (2026-10-15)

The later isolated run `9e397acf-a8c4-405c-83bc-557a7bd0acfc` produced populated sections with empty citations. Its scoped correction also retained empty citations and unchanged text in four targeted sections, so the revision was rejected. No saved response or artifact was repaired retrospectively.

- The shared grounded response model now requires explicit citations for nonempty section content in new governed generation and scoped revision. The emitted schema includes self-contained cited/empty alternatives; genuinely empty sections and deferred runtime can remain uncited. Canonical stored schemas are unchanged.
- A citation-only revision counts as material only when frozen, section-matched IDs replace an empty or invalid-only citation list. Existing valid citation reshuffling, foreign IDs, unrelated-section drift and partial targeted revisions remain rejected. The workflow supplies its existing frozen evidence to that check.
- Citation identity is not proof that evidence supports a claim. Independent critique, quality checks, proposal confirmation and human approval still apply; no approval or export was performed.
- **417 selected offline checks passed**, with five shared-database fixture cases excluded, after the final assertions. Only three new test cases were added; existing wire-schema and unsupported-section regressions were extended. This is not a full-suite result. An existing Starlette/AnyIO deprecation warning remains.
- Docker was stopped. The Windows runner disabled shared conftest, cache and bytecode, blocked external connections and PostgreSQL, and used mocked HTTP/in-memory SQLite. An initial sandbox attempt stalled in Windows event-loop socket initialization and was stopped; the same guarded selection then passed outside that restriction.
- Environment hashes matched the pre-change baseline. No NVIDIA requests, service startup, dependency/model/environment changes, migration, commit or push occurred. The preceding hosted budget remains closed. Live decoder acceptance, exact saved-response replay and fresh dashboard generation through legitimate approval/export remain unverified.

## Failure-event correction after live citation QA (2026-10-15)

Isolated run `7c23d226-c291-4358-82e7-2e942e110e34` in `qa-frostpeak-citations-20261015-058037fe` used its six authorized NVIDIA requests: planner plus JSON repair, generation, critique, scoped revision and second critique. Revision 2 filled/cited four source-backed sections and preserved every unselected section and both quest rewards. Both raw critics nevertheless reported no defects. The draft retained unfinished objectives as failure causes; it was not approved. Live read-only run/trace returned 200, unapproved exports 409 and cross-workspace access 404. Protected pre-existing rows across 39 tables were unchanged. The budget is closed.

This offline correction addresses the failure-rule issue only:

- Completeness now accepts an explicit typed `failure: null` contract without requiring invented failure text. Legacy quests without an explicit state contract still need failure descriptions. Other quality/approval requirements remain in force.
- The content-first prompt again forbids unfinished-objective failure predicates and requests empty failure states when neither evidence nor human direction supplies an event.
- Existing governed request checks flag bounded English unfinished-state forms in failure descriptions and mapped failure actions. These become high-severity effective findings and cannot be cleared merely by confirming proposals. Event-context wording is not automatically rejected; this check is not a semantic event verifier or a general language parser.
- **423 selected offline checks passed**, five shared-database cases excluded. Six new parametrized cases cover the three observed predicates, hidden action wording and explicit event contexts; existing failure-free completeness and mocked generation-prompt checks were extended. No full-suite/coverage claim; the existing Starlette/AnyIO warning remains.
- Read-only replay detected all three problematic causes in the exact saved revision. SHA-256 fingerprints of its artifacts, stored critiques, evidence and run configuration matched before/after. Environment hashes were unchanged. No new hosted requests, migrations, installs, commit or push occurred.

Remaining: dialogue eligibility review, first-pass source coverage and reliable independent semantic critique. No new browser, runtime or approved-export acceptance was performed; the prompt change still requires future bounded hosted verification.

## Dialogue situation/stage review correction (2026-10-15)

The saved Frostpeak mappings declared `progress` themselves; the assembler did not accidentally remap a valid greeting. The correction therefore leaves assembly and stored output unchanged rather than guessing replacement eligibility.

- The existing governed quality check now flags exact `greeting` labels with non-greeting stages, and bare `quest_offer` labels with progress/completion stages. Findings require a purposeful correction and cannot be dismissed merely by confirming proposals. Other wording still needs semantic review.
- Generation and scoped-revision guidance preserve deliberately quest-scoped greetings and require explicit offer availability. No pre-quest lifecycle or automatic offer activation was invented. An independent `other` mapping remaining structurally valid is not proof that its intended availability is correct.
- **439 selected offline checks passed**, five shared-database cases excluded: six new cases and ten previously existing dialogue-alignment checks added to the earlier selection. The unchanged generation prompt-size limit passed after duplicate formatting advice was removed; it was not raised. The existing Starlette/AnyIO warning remains. This is not a full-suite or coverage claim.
- Read-only replay of run `7c23d226-c291-4358-82e7-2e942e110e34` exposes all six saved situation/stage conflicts. Fingerprints of its run configuration, artifacts, raw/stored critiques and frozen evidence matched before/after. No saved run, model/environment setting, schema, migration, dependency, commit or push was changed. No NVIDIA requests occurred; the prior six-request budget remains closed.

Remaining: first-pass source coverage and trustworthy independent semantic critique. Fresh hosted generation, browser behavior, meaningful approval/export and runtime execution remain unverified by this correction.

## Explicit critic source coverage (2026-10-15)

Fresh governed critiques now require a compact assessment for all nine sections: `covered`, `missing`, or `not_specified`; Unity runtime also permits `deferred`. These are model judgments of the supplied excerpts, not verified completeness scores or evidence that the whole GDD was retrieved. A `missing` assessment requires `needs_revision` and a finding in that section with an evidence ID and quote. Existing pointer/value/quote checks still validate anchors; none of these checks proves semantic entailment.

The concise critic rubric separates omitted source facts from labelled design proposals: absence from the GDD alone is not a proposal defect; contradictions and concrete usability failures still are. The existing prompt-size limit remains unchanged. No automatic filling, new model routing, retries, or approval bypass was added.

Coverage assessments survive canonical review parsing, effective-critique merging and provenance reconstruction. Historical reviews without the field retain their exact serialized shape and can still be reconstructed. No saved failed critique was rewritten or upgraded.

Verification: **456 selected offline checks passed**, five shared-database fixture cases excluded, with one existing Starlette/AnyIO deprecation warning. Six new cases cover absent/partial assessments, unanchored omissions, inconsistent verdicts, invalid design deferral and legacy/new provenance round-trips; eleven existing LLM parser checks were added to the previous selection. The runner disables shared conftest, cache and bytecode and blocks external connections and PostgreSQL; HTTP is mocked and applicable review tests use in-memory SQLite. This is not a full-suite or coverage result. Environment hashes remain unchanged.

No NVIDIA calls, saved-run edits, runtime approval, exports, migrations, installs, commits or pushes were performed. Both previous hosted budgets remain closed. The next meaningful gate is a newly authorized, bounded independent critique of the same frozen draft/evidence: inspect whether it actually detects omitted source content without misclassifying proposals. Live decoder acceptance, better semantic judgment, fresh dashboard generation and legitimate approval/export are not established by these offline checks.

## Source-first field-target follow-up (2026-10-15)

The subsequent two-request coverage check remained a semantic failure; its raw results and assessment stay in its isolated QA workspace. This local follow-up changes only fresh governed critique presentation and target selection, not those saved responses.

- Evidence now precedes the unchanged artifact in the critic input. Coverage guidance explicitly compares source evidence rather than treating blank draft fields as absent GDD facts. Human requirements and trust boundaries remain unchanged.
- Fresh correction targets exclude whole populated section-content and list-record objects, including entire NPC/quest records. Exact child fields, field maps, collections and empty objects remain selectable so real missing-key/item findings are not censored. Original indexes and escaped JSON pointers are preserved; exact value, replacement and quote checks remain in place. Historical canonical review parsing/provenance is unchanged.
- **456 selected offline checks passed**, five shared-database fixture cases excluded, with the existing Starlette/AnyIO warning. Existing tests were extended, not new test cases: record-target rejection, null/empty/map/collection targets, escaping, source-first payload order and the unchanged prompt-size limit. Shared conftest, cache and bytecode were disabled; PostgreSQL/external connections blocked, with mocked HTTP/in-memory SQLite where applicable.
- Read-only replay rejected both saved whole-quest findings under the fresh wire contract. Handwritten exact-field and four source-omission controls retained valid anchors through the adapter; a separate historical whole-record control still reconstructed under the canonical contract. These controls are not NVIDIA outputs or evidence of improved semantic judgment. Fingerprints of the original run, artifacts, critiques, evidence and closed coverage-QA record matched before/after.

No new NVIDIA requests, saved-run edits, model/environment changes, runtime approvals, exports, migrations, installs, commits or pushes occurred. This is not full-suite, browser or end-to-end acceptance. Whether source-first presentation improves real omission detection remains unverified; the two-request budget is closed.

## Defect detection without model-generated replacements (2026-10-15)

Fresh governed critiques now require `review_mode: defect_detection`. Their reference contains only the exact artifact path/value and optional frozen evidence ID/quote; `replacement` is forbidden in the fresh wire schema. Recommendations are verification steps, not rewritten design content. Scoped generation/revision remains the existing separate operation; nothing is patched or approved automatically.

Legacy corrective reviews retain their required replacement and non-no-op validation. Detection-only references require their explicit mode, while corrective references cannot bypass validation by adding that mode: their replacement field is rejected under the detection contract. Canonical parsing preserves both historical shapes and the new marker through provenance, repeated completeness merging and human-resolution approval projection. Exact value, section and quote checks remain; identity does not prove that a natural-language finding is true.

Verification: **459 selected offline checks passed**, five shared-database cases excluded, with one existing Starlette/AnyIO warning. One new contract check and two added approval-test variants cover the new mode; existing path/coverage/provenance/prompt tests were updated. The existing prompt-size limit passed without being raised. The guarded runner disables shared conftest, cache and bytecode, blocks PostgreSQL/external connections, and uses mocked HTTP/in-memory SQLite where applicable. This is not full-suite or coverage verification.

Read-only saved-failure replay kept both old no-op findings rejected and the truncated response invalid without repair. Handwritten four-omission and failure-condition controls passed the new identity contract through the adapter; these are not model outputs or semantic-quality evidence. Original run/artifact/critique/evidence and both later closed QA audit hashes matched before/after. Backend health passed; environment hashes were unchanged.

No NVIDIA requests, saved-run edits, model/environment/output-budget changes, runtime approval, exports, migrations, installs, commits or pushes occurred. The critic remains capped at 1,024 tokens. Whether this smaller responsibility reduces real truncation or false positives is unverified; all preceding hosted budgets remain closed.

## Bind fresh critique runtime coverage to human scope (2026-10-15)

The fresh governed critique schema now receives the saved run's explicit `defer_runtime` choice. Runtime coverage must be `deferred` in design-only scope; runs without explicit deferral cannot claim that status. This removes a human-owned scope decision from model classification. It does not certify empty or populated runtime content, suppress independent runtime findings, or change canonical historical review parsing.

The production change is limited to the existing dynamic coverage schema and its adapter caller. There are no prompt, model, output-budget, database, frontend or approval-policy changes. Existing runtime-scope checks still block populated preview/bindings in a design-only run, and runtime release remains separate from design review.

Verification: **461 selected offline checks passed**, five shared-database fixture cases excluded, with the existing Starlette/AnyIO warning. Two new parameterized cases cover both explicit scopes, wrong-scope status rejection, unchanged input/provenance, retained independent findings and deterministic runtime blockers. The guarded runner disables shared conftest, bytecode and cache, blocks PostgreSQL/external connections and uses mocked HTTP/in-memory SQLite where applicable. This is not a full-suite or coverage result.

Read-only replay kept prior failed/truncated reviews rejected, preserved saved audits and passed handwritten anchor controls without saving them. Environment hashes remain unchanged. No new hosted requests, saved-workspace changes, approval, exports, installs, migrations, commits or pushes occurred during this correction. This narrow contract fix does not resolve source-coverage/findings inconsistency, semantic false positives or missed quest/dialogue defects; live acceptance and fresh generation-to-approved-export remain unverified.

## Couple fresh section assessments to findings (2026-10-15)

Fresh governed responses now contain one assessment per canonical section, with its coverage status and findings together. The native schema's `missing` branch requires at least one finding with a nonempty evidence ID/quote and a reference in that same section; assessed/deferred branches remain distinct. Explicit runtime scope still comes from the human request. The adapter losslessly flattens validated assessments to the existing stored/API review shape and derives `needs_revision` whenever findings exist, rather than asking the model for a potentially contradictory verdict. This conservative derived verdict applies only to new responses. Canonical historical reviews, hashes, finding resolutions and approval policy are unchanged; old flat or failed responses are never upgraded through this fresh wire contract.

Fresh section reviews cannot use format repair to invent missing findings. The critic rubric no longer pressures the model to allege premature completion merely because a single event is declared: a full-total completion condition is legitimate, while a defect needs a concrete counterexample allowed by the declared action. It also distinguishes unfinished objectives from failure and exact greeting/offer labels from progress stages. This guidance is not a semantic validator or proof that future model findings will be true.

Verification: **464 selected offline checks passed**, five shared-database fixture cases excluded, with the existing Starlette/AnyIO warning. Three new checks cover coupled omissions/derived verdicts, prohibition of semantic repair, and preservation of three known failure-predicate plus six dialogue-stage blockers even when an independent model review returns no findings. The existing prompt-size limit passed without being raised. The test fixture adapter translates known canonical fixtures only; production accepts only the actual fresh wire response.

The existing project Ajv validator compiled the generated JSON schema, accepted a handwritten positive control and rejected six invalid controls, including the two historical failed responses. A read-only frozen-state replay retained exact field/quote checks and canonical provenance, kept the nine known deterministic blockers, and prevented approval on an empty model review. These controls are handwritten/mocked, not NVIDIA output. Existing-row fingerprints matched across 39 tables, saved QA audits and environment hashes were unchanged, and backend health returned 200. No dependency was installed.

No hosted requests, saved-workspace changes, model/environment/output-budget changes, approvals, exports, migrations, commits or pushes occurred. The 1,024-token cap remains. NVIDIA decoder acceptance, token fit for real findings, semantic false-positive/miss rates and fresh normal-flow generation through legitimate approval/export remain unverified. The changes resolve the structural inconsistency and preserve safety coverage; they do not justify a claim that live AI reliability is solved.
