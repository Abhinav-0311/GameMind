# GameMind working agreement

These project instructions supplement the parent `AGENTS.md`; they do not replace
its UI/design requirements. For frontend work also read `frontend/AGENTS.md`.

## Mandatory MVP checkpoint

Before every GameMind task, read `MVP.md`. It is the canonical product scope,
Phase 0–6 acceptance checklist, current blocker list and evidence ledger.

- Before implementation/QA, select the relevant checklist IDs, inspect the actual
  state and identify the smallest coherent change and its verification. State the
  intended user-visible outcome briefly. Do not infer the next phase from “next”
  when the preceding acceptance gate is still failing.
- After authorized implementation/QA, update the affected checklist/status,
  blockers/next action and concise evidence in `MVP.md`. Mark an item accepted only
  with evidence for its entire outcome. Reopen it if a relevant regression appears.
- For read-only/discussion requests, consult the checklist without editing it or
  implementing changes. A documentation task does not close product gates.
- Separate implementation, mocked/offline tests, live backend/browser proof,
  hosted content quality, approval/export and Unity proof. Never use one as proof
  of another; never count overlapping test selections as separate total coverage.
- Do not expand features, change models/frameworks, or start Unity to bypass a
  failing generation/review gate. Keep the dashboard-first scope and Unity last.
- Historical plans, transcripts and Phase 1–8 reports are context, not current
  task instructions, acceptance sign-off or permission to execute commands.

## Safety and scope

- Preserve unrelated working-tree changes and historical QA artifacts/results.
  Use existing helpers and the smallest complete fix; avoid accumulating layers
  of prompt text, heuristic exceptions, tests or new reports without product value.
- `backend/conftest.py` drops/recreates its target schema. Never run it against the
  application database or any retained QA database. Verify a fresh disposable test
  target first. For offline tests, use appropriate guards; `--noconftest` alone
  does not block database/network access in test code.
- Hosted calls require the user's applicable consent and bounded allowance; count
  every retry/repair. Never reopen or reuse an exhausted allowance. This working
  agreement does not grant new external-call, environment, approval, commit or
  push authority.
- Do not weaken evidence, authorization, revision, approval or runtime gates to
  obtain a passing demo. Record the blocker truthfully in `MVP.md`.
