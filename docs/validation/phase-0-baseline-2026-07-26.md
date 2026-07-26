# Phase 0 Baseline Verification

Date: 2026-07-26
Repository: GameMind
Branch: `master`
Remote tracking state at audit start: 9 commits ahead of `origin/main`

## Purpose

This baseline records the state of GameMind before adding LangGraph, LangChain
Core, workflow persistence, or new model providers. It separates verified
behavior from known gaps so later agent work cannot hide regressions or claim
coverage that does not exist.

The accepted agent scope is defined in
[`docs/architecture/design-agent-mvp.md`](../architecture/design-agent-mvp.md).

## Changes reviewed for the baseline

The pre-existing working tree contained one coherent CyberRakshak quality-gate
change:

- Blueprint readiness now distinguishes approval blockers from advisories.
- Required summary, narrative, NPC, quest, and level content is validated.
- Truncated records and raw table fragments block approval and materialization.
- The approval API returns structured readiness details on conflict.
- The Blueprint screen disables approval and presents concise blockers.
- Regression tests cover malformed narrative, truncated NPC dialogue, and
  advisory-only art or memory gaps.
- The CyberRakshak product audit records the source-to-output defects that
  motivated the change.

No part of this work introduces LangGraph or changes the future agent design.

## Runtime health

Docker Desktop was started and the existing containers reached the expected
state:

| Component | Verified state |
| --- | --- |
| PostgreSQL | Healthy |
| Chroma | Healthy |
| FastAPI backend | Running |
| `/health` | `status=healthy` |
| LLM mode | `local_demo`, provider `mock` |
| Embeddings | `local_lexical`, 384 dimensions |
| Vector collection | `lore_chunks_local_lexical_v1` |

This is the intended zero-cost development baseline.

## Automated verification

### Backend

Command:

```powershell
docker exec gamemind_backend pytest -q
```

Result:

```text
190 passed, 1 deselected in 38.96s
```

The deselected test is the explicitly marked multi-threaded load benchmark
excluded by `backend/pytest.ini`. It is not a skipped functional test. The
Chroma-dependent graph-aware memory test ran because Chroma was available.

### Frontend

Commands:

```powershell
npm.cmd run lint
npm.cmd run build
```

Results:

- ESLint passed with no reported errors or warnings.
- Next.js production compilation and TypeScript checks passed.
- All 18 static routes were generated.

## Browser smoke verification

Playwright inspected the running dashboard and backend on:

- `/`
- `/knowledge`
- `/decisions`
- `/blueprints`
- `/query`
- `/vertical-slice`
- `/workspace`

Verified behavior:

- Home loaded with healthy API responses.
- The CyberRakshak source library showed the 17-chunk GDD.
- The Blueprint screen selected the latest CyberRakshak draft.
- Readiness displayed `Approval blocked`.
- Approval was disabled.
- The malformed narrative fragment and truncated Adi profile were visible as
  blockers.
- Runtime Test loaded the CyberRakshak source and NPC context.
- No horizontal navigation or route failure was encountered in this smoke pass.

### Baseline issue fixed

The anonymous local-mode Workspace page requested protected membership routes
and generated three `401 Unauthorized` console errors.

The frontend now:

1. Loads the authentication session first.
2. Requests members only for an authenticated user.
3. Sends credentials with authenticated membership and invitation requests.
4. Presents an intentional local-workspace state and sign-in action.

After the fix, Playwright reported zero console errors on `/workspace`.

## Known gaps accepted for Phase 0

1. Playwright is installed, but the repository does not yet contain a reusable
   Playwright test suite or `test:e2e` command. This smoke pass is evidence, not
   automated CI coverage. A focused agent journey belongs in the console and
   case-study phases.
2. The load benchmark remains excluded from the default suite. The previous
   CyberRakshak audit found its shared threaded `TestClient` strategy could
   hang; it must be redesigned or time-bounded before becoming a production
   gate.
3. Lore Search still displays Frostpeak example questions in the CyberRakshak
   workspace.
4. The Decisions page initially selects the latest source revision, which may
   show no decision records even when another source has resolved decisions.
5. The local branch name is `master` while the GitHub tracking branch is
   `origin/main`, and the local branch began this audit nine commits ahead.

These gaps are documented rather than expanded into Phase 0 work because they
do not prevent implementation or verification of the bounded design-agent
workflow.

## Baseline verdict

The current application is a stable private technical beta suitable for the
design-agent implementation:

- Core backend tests pass.
- Current blueprint-quality changes are covered and work in the browser.
- Frontend lint and production build pass.
- PostgreSQL, Chroma, FastAPI, mock inference, and local embeddings are healthy.
- Agent scope and acceptance gates are frozen.

Phase 1 may begin only after this baseline and its reviewed implementation
changes are committed as one coherent checkpoint.
