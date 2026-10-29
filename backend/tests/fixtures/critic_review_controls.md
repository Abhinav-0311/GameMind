# Frozen critic controls — version 2

MVP target: **P3.1**, with structural checks relevant to **P3.3**.

The [JSON dataset](critic_review_controls.json) contains two manually authored,
source-reviewed baselines and six fixed cases. These are assistant-authored QA
inputs, not new NVIDIA output, exact historical request replays, human-approved
designs or full dashboard acceptance. Sources are the bundled project GDD for
CyberRakshak and the synthetic Frostpeak sample, not an external/public corpus.

Normalized-LF dataset SHA-256:
`9389e8531643379f8c5b6f398e95f2608b599518eb01641014601689d6cc8d3b`

Version 1 failed container adapter checks: its 14 CyberRakshak evidence items
exceeded the existing 10-item budget, omitting required level headings. Version 2
groups adjacent levels 1–3, 4–7 and 8–10 into exact contiguous source excerpts and
remaps their citation IDs. All seven CyberRakshak excerpts fit 1200 characters;
the adapter must retain every excerpt unchanged. Authored content, cases, expected
defects and source hashes are unchanged. No provider budget/configuration changed.
Version 1 is preserved locally at
`<QA_DIR>/critic-control-baseline-20261016\critic_review_controls.v1.json`
(normalized-LF SHA-256
`4ea692e7f8185c73783071efeb5ec88a2e100e7f185d2682c57deedaa3e151f6`).

## Cases fixed before another hosted check

| Case | Expected agreed defect | Required comparison |
| --- | --- | --- |
| `frost-valid` | None of the agreed source/state defects | Labelled speaker associations and failure/restart proposals are not source-defined quest-giver bindings. Shared progress is neutral across zero and either partial state. |
| `frost-progress-state` | Progress speech contradicts its eligible state | At zero progress, guards are not defeated; after flag-first progress, the flag is not lowered. |
| `frost-ore-quantity` | Completion threshold is 4 instead of source-required 5 | At 4 mined chunks, the sole completion event can fire while the source objective remains incomplete. |
| `frost-source-omissions` | Source-backed premise and visual direction omitted | Empty current fields do not preserve the supplied premise/style despite citation presence. |
| `cyber-valid` | None of the agreed source/state defects | The quoted warnings match their link/file/firewall situations. Reuse is allowed; quest packaging/event wiring are labelled proposals. |
| `cyber-file-link-mismatch` | Link/URL speech mapped to a file interaction | Before opening a suspicious executable, the proposed warning talks about a URL instead of the file. |

Each bad case changes only its listed RFC 6902 JSON Patch fields relative to its
baseline. Exact artifact paths, source quotes and failing-state explanations are
stored with the expectations. This fixes the earlier non-comparable control setup
where other sections changed between critique attempts.

“Valid” means no agreed high-risk grounding/state defect in the selected slice,
not ideal prose or automatic approval readiness. In particular, explicitly unknown
NPC-memory rules remain empty. The existing completeness scorecard may still
block such a section; that unresolved P3.4 behavior is not hidden by these controls.
The final human content review remains a separate MVP release requirement.

## Loading and checking without leaking answers

1. Load the baseline selected by `case.baseline`, apply `case.patch` without
   mutating it, then validate with `GovernedBlueprintContent`. Its existing model
   derives duplicated hooks/manual-test text; it does not repair source facts.
2. Send **only** the resulting artifact, baseline evidence and review request
   through the normal critic adapter. Never send `expected_defects`, `must_not_flag`,
   this case table or earlier verdicts to the model as answers.
3. Keep raw model findings before local checks and the effective review afterward.
   A local guard catching the problem does not count as the hosted critic finding it.
4. Compare each raw finding with the agreed defect's meaning, relevant current
   field, exact frozen quote or eligible-state counterexample. Record misses,
   invalid references and false positives separately. No substring-based automatic
   “semantic pass” and no model grading its own answer.
5. An additional credible defect requires explicit adjudication, not automatic
   dismissal because it was unexpected. If a control genuinely needs correction,
   preserve the current version, document the reason and create a new version before retesting;
   do not change expectations to make a failed run pass.
6. Record dataset/code/config/request fingerprints for before/after comparisons.
   Fix the inputs and isolate any QA writes. A six-case set is **not** permission
   for six requests: retries and repairs consume the user's separately granted cap.

## What the offline checks prove

`backend/test_critic_controls.py` verifies source hashes/exact excerpts, closed
artifact validity, citation membership, existing reference paths, immutable bases,
normal-adapter compatibility and absence of answer leakage. It also replays the
observed draft-note-as-GDD-quote error and confirms the existing gate rejects it.

Related projection regressions preserve canonical note indices after duplicate
removal, reject references to omitted notes, bind returned values/provenance to the
original draft, and preserve legacy behavior. Indexed note objects exist only in
the compact critic input; saved artifacts/API note arrays are unchanged.

Run with the existing guarded offline runner from `backend`:

```powershell
.\.venv312\Scripts\python.exe -B <QA_DIR>/qa-action-contract-local-20261016\offline.py test_critic_controls.py test_independent_critic_boundary.py test_design_prompt_usability.py
```

That runner is a machine-local QA helper, not a committed project dependency.
An equivalent CI check must establish network/database isolation separately.
Do not substitute an unguarded whole-suite command: repository `conftest.py`
resets its database. Container `/docs` is not mounted, so source hashes are checked
on the host; container verification excludes that one check explicitly.

No hosted model accuracy, approval/export or runtime claim follows from these
offline checks. The next gate is P3.2: genuinely test critic sensitivity and false
positives with fresh bounded authorization, retaining the first responses.
