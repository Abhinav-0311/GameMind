# Quest-action native-schema compatibility — 2026-10-16

## Outcome

Implemented a narrow compatibility change at the failing quest-action boundary. Local regression checks pass. **The real NVIDIA revision and useful generation remain unverified after this change.** No hosted requests were made in this chunk.

Production scope: `backend/app/design_agent/contracts.py` only. Existing tests extended in `backend/test_content_revision.py`. No model switching, prompt expansion, new dependencies, environment changes, frontend changes, approval bypasses or saved-artifact rewrites.

## Evidence and limits of the diagnosis

The immutable native Frostpeak request failed exactly after its first `completion_action`, with an illegal comma and then a closing-delimiter loop. Its three action fields used the JSON Schema pattern `\S+\s+\S+`.

A raw quote-wrapped version of that regex can consume JSON quotes and structure. A standard-library reproduction accepts this invalid JSON as a regex match:

```text
{"completion_action":"defeat all",}"}
```

The JSON parser rejects the same text. This is a reproduction of a **specific grammar-construction mechanism**, not an execution of NVIDIA's hosted backend or a local XGrammar installation.

Primary-source support:

- [XGrammar v0.1.29 converter](https://raw.githubusercontent.com/mlc-ai/xgrammar/v0.1.29/cpp/json_schema_converter.cc), lines 2978–2991 and 1870–1883: the pattern path directly converts the regex, wraps it with quotes and ignores simultaneous length constraints.
- [Current upstream converter](https://raw.githubusercontent.com/mlc-ai/xgrammar/main/cpp/json_schema_converter.cc), lines 2208–2244 and 2603–2607: the JSON-string regex path explicitly excludes unescaped quotes, backslashes and control characters.
- [Upstream grammar documentation](https://github.com/mlc-ai/xgrammar/blob/main/docs/defining_structures/ebnf_grammar.md): explains JSON-string character exclusion.

These sources establish a relevant known mechanism. They do **not** identify NVIDIA's deployed grammar engine/version, prove the full hosted root cause, or explain the independently observed copying of old NPC greetings.

## Smallest change

`_quest_action_schema` removes only `pattern` from the JSON Schema representation of `QuestEventAction`. The shared field keeps the **same Pydantic regex, minimum length and maximum length** for local Python/JSON validation.

This changes provider-side guidance, not the application's acceptance rule:

- Completion/failure/restart actions remain strings with length bounds in the outgoing schema.
- Readability is still enforced after parsing, before assembly and persistence.
- Single-word event identifiers, punctuation-only failures and oversized actions still fail.
- Valid quotes, backslashes and multilingual wording remain accepted locally.
- Invalid governed action data is still rejected after one mocked request, with semantic repair skipped.
- No generic schema stripping, fallback transport, setting or second product flow was added.

Actual saved-request comparison confirms the new schema is identical after removing exactly these three pattern entries:

- `/$defs/DraftObjective/properties/completion_action`
- `/$defs/GroundedRevisionQuest/properties/failure_states/items`
- `/$defs/GroundedRevisionQuest/properties/restart_action/anyOf/0`

Citation enums, identity selectors, closed objects, required fields, array limits, runtime deferral and every other schema entry are unchanged.

## Verification completed

- Red phase: two targeted tests failed against the old behavior; 34 existing/local controls passed.
- Focused seven-module run: **241 passed**, one existing Starlette/AnyIO deprecation warning.
- The same seven-module selection inside the running Python 3.11 backend container: **241 passed**, 11.00 seconds, with PostgreSQL/external-network guards and shared conftest excluded.
- Final broader 23-module selection: **595 passed, five PostgreSQL-fixture cases deselected**, one existing warning, **23.29 seconds**. This is a selected regression run, not the full backend suite. Fourteen new parameterized cases were added in one existing test module; the 595 checks were not all newly added.
- The broader selection includes controlled normal API generation → scoped revision → independent mocked critique → explicit proposal confirmation/design approval → brief export; runtime approval remains blocked. These use mocked HTTP, disposable SQLite and in-memory checkpoints, not live generation or an actual dashboard session.
- Frozen Frostpeak projected draft remains a schema-valid control.
- The exact corrupt hosted completion still fails through the production provider with **one MockTransport request**, no larger-budget retry and no accepted candidate.
- Syntax parsing passed for both edited Python files. Scoped `git diff --check` passed; Git warns about eventual CRLF normalization.
- All **156 table fingerprints** across the application and three prior isolated QA databases remain unchanged. Telemetry compares only rows existing at the prior recorded cutoff.
- The original hosted ledger remains closed at one request; zero newly approved blueprints.
- Environment hashes, NVIDIA adapter and transport file hashes unchanged. Immutable QA result SHA256 remains `c256b1bc956a144de4abbd97aa942051f0c116e9fd7a0536a5779ce0cf2e7b8f`.

The first Windows sandbox test attempt stalled and was explicitly stopped. The final scoped runs completed after rerunning outside that sandbox with the same explicit PostgreSQL/external-network guards. No stalled attempt is counted as passing.

## Verification not performed

- No fresh NVIDIA request, independent hosted critique, browser walkthrough or hosted generation → approval → export proof.
- No full PostgreSQL backend-suite run; shared `conftest.py` rebuilds a database schema, so it was intentionally excluded.
- No measured coverage, dedicated Ruff lint or Pyright check: those tools are not installed. Nothing was installed.
- No independent generic JSON Schema validator or native grammar compiler is installed; schema/control assertions and the documented raw-wrapper reproduction are the local evidence.

## Next acceptance gate

With fresh bounded authorization, first exercise a **single-objective structured response using the unchanged configured model** and the reduced action schema. If it parses and passes local validation, try the focused NPC/quest correction and independent critique in a new isolated QA workspace. Stop on a repeated structural failure; never use partial copied greetings or semantic repair as an accepted result.

Success must include useful new greeting/progress/completion lines, the full five-ore requirement, unchanged rewards, valid proposed failure/restart actions and independent review. Only a separate authorized approval/export flow can establish product acceptance.

## Reproduction

From `E:\College\Project\Bot\backend`:

```powershell
& '.\.venv312\Scripts\python.exe' -B 'E:\College\Project\GameMind-QA\qa-action-contract-local-20261016\offline.py' test_content_revision.py test_content_draft.py test_design_contract_v2.py test_quest_state_contract.py test_design_agent_llm_provider.py test_structured_output_diagnostics.py test_nvidia_design_agent_provider.py
& '.\.venv312\Scripts\python.exe' -B 'E:\College\Project\GameMind-QA\qa-action-contract-local-20261016\inspect.py'
```

The local inspection scripts/results are outside the application repository. Earlier QA source/results were not rewritten.

Ponytail kept the production fix to one shared field-schema hook. Python Testing supplied red/green controls; Verification Loop separates completed local checks from outstanding hosted acceptance.

