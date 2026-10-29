# Nested finding review fix — FRESH-04

## Scope and outcome

The fresh Frostpeak NVIDIA check exposed a frontend contract mismatch: the critic
used `npc_archetypes.content.npcs[0].dialogue_style` as its finding section, while
the form indexed the artifact with that whole string. Review opened with no draft
fields, even though server policy allowed recording a human judgment.

The form now derives a presentation section from a plain section name or a
syntactically recognized dotted/bracket path beneath `content`. The section must
be an own property of the displayed artifact. Field choices still come from the
actual section content and use existing JSON pointers; the reviewer must select
the exact field. No model expression is executed, and the critic's raw section,
finding identity, fingerprints, evidence, and server approval policy are unchanged.

Unknown/malformed sections and sections without selectable fields show an explicit
blocked explanation. Both field selection and recording are disabled. Initial
keyboard focus goes to Cancel in that state; cancellation restores the review
trigger. No automatic field selection, judgment, proposal confirmation or approval
was added.

## Files changed in this step

- `frontend/src/components/DesignFindingReviews.tsx`
- `frontend/tests/dashboard-states.mjs`
- This verification note.

The component and test script already existed as untracked working-tree files;
their prior contents and unrelated changes were preserved. No backend, package,
environment or model configuration edits were made.

## Verification

- RED: the existing record/reload flow, updated to the real nested path shape,
  failed selecting `/npc_archetypes/content/npcs/0/dialogue_style`: the option
  was absent before the fix.
- GREEN: **15 focused browser checks passed**. The three existing record/reload
  scenarios now exercise the nested path at 1440, 768 and 375px, including original
  critique preservation, exact quotes, light/dark label contrast and separate
  approval. Three additional safe-boundary scenarios cover unknown sections,
  malformed paths and empty sections. Existing permissions, stale catalog,
  unavailable service, save conflict, proposal and frozen-evidence checks passed.
- TypeScript: `node node_modules/typescript/bin/tsc --noEmit --incremental false`
  passed.
- Scoped ESLint: `node node_modules/eslint/bin/eslint.js
  src/components/DesignFindingReviews.tsx tests/dashboard-states.mjs` passed.
- Full existing dashboard regression: **95 browser checks passed**, including
  the 15 focused scenarios above (not 110 distinct checks). Minimum measured
  broader semantic-text contrast was **5.11:1**. These are fixture/browser checks,
  not backend test counts or production-readiness evidence.
- **Live read-only browser verification passed** against the actual saved run
  `4c05934b-40d6-4a0e-8ac9-0df311a09129` in isolated workspace
  `qa-frostpeak-fresh-20261013-24ca4759`: the exact dialogue-style field and frozen
  NPC quote were available, and valid input enabled Record human review. Approval
  stayed blocked. Cancel/reload passed. Before/after draft and critique hashes and
  finding-resolution count matched. No review was submitted, and there were zero
  browser errors, HTTP errors or mutation attempts.

All browser-fixture API traffic was intercepted. Simulated record and approval
POSTs are not real database acceptance. Live verification used a memory-only
session for the already-created isolated QA owner, blocked all mutations and
external traffic, and saved no authentication material.

The initial sandbox browser launch could not find the user-installed browser;
the same check ran successfully outside that sandbox using the existing browser.
No browser or package installation was performed.

## Design review and limits

Emil design engineering guided the restrained inline explanation and keyboard
continuity; ECC React Testing guided observable behavior and raw-review
preservation checks using the existing browser harness, without adding libraries.

| Before | After | Why |
| --- | --- | --- |
| Valid nested finding leaves an empty selector | Recognized section supplies actual draft fields | Makes the existing task completable without changing critic evidence |
| Unsupported section gives no explanation | Explicit blocked state and a reachable Cancel action | Avoids guessing and preserves keyboard continuity |

Self-review retained the existing layout, spacing, controls and focus styling;
no decorative motion, extra panel or new workflow was warranted. This is a
functional browser verification, not a fresh visual/axe audit or full backend
suite result. No production build was run over the active dev server's `.next`.

Environment hashes matched the preceding QA baseline. No NVIDIA requests,
database writes, runtime approvals/materialization, installs, commits or pushes
were performed in this step.

## Still open

FRESH-01 planner reliability, FRESH-02 partial-state dialogue contradictions,
FRESH-03 critic usefulness, and the runtime-preview/integration questions remain
open. This fix does not make the saved draft acceptable or prove generation
reliability. Next: replay the saved null/missing planner-query responses and fix
that contract locally before any newly authorized hosted acceptance run.
