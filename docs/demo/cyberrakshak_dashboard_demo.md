# CyberRakshak Dashboard Demo

This is a historical presenter script, not evidence that CyberRakshak passes the
current workflow. CyberRakshak has not been run on the current code. Use the
Frostpeak quickstart in [README.md](../../README.md) for the recorded current-path
evidence and limitations. The steps below are proposed demonstration steps that
require fresh verification before presenting them as working behavior.

## Intended demonstration scope — not current proof

```text
GDD evidence
  -> local extraction and decision review
  -> optional NVIDIA design run
  -> independent critique and human checkpoint
  -> approved blueprint and explicit runtime bindings
  -> runtime test
  -> Unity last
```

The important claim is not that a model can invent quests or dialogue. It is
that GameMind makes evidence, assumptions, critique, approval, and runtime
eligibility visible in one project-scoped workflow.

## Before presenting

- Start the stack with `docker compose up -d --build`.
- Start the dashboard with `cd frontend` then `npm.cmd run dev`.
- Open `http://localhost:3000` and confirm the workspace readiness panel is
  healthy.
- Use a fresh `CyberRakshak` workspace when recording so old documents and
  blueprints do not distract from the path.
- Do not paste hosted-model keys on screen. The local evidence path is enough
  to demonstrate the product; NVIDIA review is optional and requires explicit
  consent in the UI.

## Presenter path

### 1. Establish the problem — Home

Open **Home** and explain:

> GameMind is an evidence-first game-design system. It helps a developer turn
> a GDD into reviewable NPC, quest, gameplay, and runtime work while keeping
> every important claim connected to source evidence.

Point out the recommended next action and the readiness panel. Do not describe
an empty or skipped materialization as runtime-ready.

### 2. Add the actual source — Sources

Upload [cyberrakshak_gdd.md](cyberrakshak_gdd.md) as a **GDD**.

Show that the source is indexed into chunks and inspect one or two chunks:

- Adi, Jay, and PATCH are named characters.
- The ten-level story arc is present.
- PATCH's scripted and rule-based dialogue roles are specified separately.

Explain that the original file remains the source of truth; indexing does not
replace it.

### 3. Surface uncertainty — Decisions

Open **Decisions** and review missing or conflicting implementation choices.
Use [cyberrakshak_technical_brief.md](cyberrakshak_technical_brief.md) only
when you need to record a proposed choice such as platform scope,
offline-service behaviour, or accessibility. Label it as a proposal, not as a
fact extracted from the GDD.

### 4. Show the governed agent — Design Agent

Select the indexed GDD and set a narrow objective, for example:

> Create reviewable NPC dialogue hooks, quest chains, gameplay loops, and
> runtime-readiness notes from the CyberRakshak GDD.

Explain the boundary before running it:

- Local evidence extraction happens first.
- NVIDIA is optional and explicitly consented to; never imply a hosted run was
  used when the local fallback produced the result.
- The draft is cited, then independently critiqued.
- A `needs revision` critique is a successful safety outcome: approval stays
  blocked until a person resolves the issue.

Open the trace and scorecard. Call out unsupported sections and assumptions as
review work, not failure to hide.

### 5. Make generated work useful — Blueprints

For the runtime-oriented acceptance path, add
[cyberrakshak_runtime_extension.md](cyberrakshak_runtime_extension.md) as a
**Quest brief** and use it with the GDD and technical brief as documented in
[cyberrakshak_acceptance.md](cyberrakshak_acceptance.md).

Review the blueprint sections in this order:

1. NPCs: Adi, Jay, and PATCH.
2. Quest objective, dependencies, failure states, and assumptions.
3. Gameplay and level notes tied to the ten-level GDD.
4. Runtime readiness and source citations.

Open source evidence for one claim. This is the moment that differentiates
GameMind from a free-form chatbot.

### 6. Cross the runtime boundary deliberately

Approve only after the evidence and visible assumptions are acceptable.

Then choose **Materialize**. Explain:

> Approval permits materialization, but it does not excuse missing runtime
> bindings. GameMind skips incomplete records and reports why instead of
> guessing rewards, objectives, or engine semantics.

If every record is skipped, the runtime bundle returns `409 Conflict` with an
actionable message. That is intentional: a game client must not treat review
text as live game data.

### 7. End with a small runtime proof

Use **Runtime Test** only when the materialization report contains explicit
runtime records. Demonstrate one NPC interaction, one quest, and progressive
hints. Keep the focus on the approved REST contract, not on raw JSON.

Unity is last and optional for this walkthrough. It should load only the
approved, materialized runtime bundle; it is not where generation, review, or
approval happens.

## Claims to avoid

- Do not claim all AI output is factual or production-ready.
- Do not claim an NVIDIA run succeeded if the run shows local fallback or a
  failed/needs-revision critique.
- Do not claim that a GDD-defined narrative idea is an engine-ready quest until
  it has explicit runtime bindings and a successful materialization report.
- Do not show API keys, raw environment files, or internal request payloads.

## Verification before recording

Run backend verification only against fresh disposable storage using the guarded
procedure in [MVP.md](../../MVP.md#7-current-blockers-and-next-work), never pytest
inside the application container. Historical results do not verify this script
on current code.

```bash
cd frontend
npm.cmd run lint
npm.cmd run build
```

The accepted runtime record count, critique verdict, and model provider shown
in a recording must match that recording's actual workspace state.
