# Planner query contract — FRESH-01

## Outcome

The fresh hosted planner contract and prompt are hardened locally. **Fresh NVIDIA
acceptance remains unverified.** No hosted request was made in this step.

The saved baseline run `d1a4aa16-6333-4227-b450-83b3823a60f6` returned JSON null
for `section_queries.unity_runtime_preview`; its repair removed that key. Both
were already rejected by runtime validation. The model-facing dictionary schema,
however, did not require the section-query object or explicitly require its nine
members. The diagnostic run `4c05934b-40d6-4a0e-8ac9-0df311a09129` returned the
literal string `"null"` for that query: structurally accepted then, but not a useful
search query. These observations do not establish why the provider chose those
values; confusion with the human requirement for a null quest runtime binding is
a plausible cause, not a proven provider-internal explanation.

## Focused change

- `HostedRetrievalPlanOutput` makes `section_queries` mandatory for new hosted
  plans. Its schema names all nine required properties as bounded strings and
  forbids extra section keys. Runtime validation requires complete coverage and
  rejects `null`, `none`, and `n/a` placeholder strings, case-insensitively after trimming.
  The schema explicitly excludes the lowercase `null`, `none`, and `n/a` strings;
  runtime validation remains authoritative, including case variants.
- The hosted planner prompt distinguishes search queries from generated quest
  runtime bindings. Runtime-preview retrieval must still search for integration,
  client events or quest-state evidence; searching is not evidence of an engine
  fact or permission to invent bindings.
- The adapter consumes that strict contract and no longer substitutes generic
  queries for an incomplete fresh hosted response. Existing local/mock planning,
  `ResearchPlan`, and legacy `RetrievalPlanOutput` parsing stay available. No saved
  plan, draft, critique or QA workspace was rewritten.
- The same strict schema reaches the existing single repair attempt. No new retry
  loop, inference call, model selection, endpoint, setting or package was added.

## Changed files

- `backend/app/design_agent/contracts.py`
- `backend/app/design_agent/nvidia_provider.py`
- `backend/test_nvidia_design_agent_provider.py`
- `backend/tests/fixtures/frostpeak_planner_responses.json`
- This note.

The JSON fixture contains only the three saved planner output strings, not GDD
excerpts, request headers, credentials or private reasoning. It is historical
response data, never instructions. The existing adapter boundary test now expects
the strict hosted model; the previous adapter-level single-query fallback test
now verifies legacy readability separately from strict fresh-hosted rejection.

## Verification

- Corrected RED regression: the exposed schema did not require `section_queries`,
  and replay of the diagnostic literal `"null"` was incorrectly accepted. The
  saved JSON-null and missing-key responses were already rejected, as expected.
  An initial replay-test constructor omission was corrected before this RED run;
  it is not counted as evidence of an application defect.
- GREEN provider boundary set: **25 passed** in **2.20 s**.
- Final bounded regression set: **150 passed** in **6.18 s** across
  `test_nvidia_design_agent_provider.py`, `test_design_agent_llm_provider.py`,
  `test_structured_output_diagnostics.py`, `test_phase3_generation_contract.py`,
  `test_generation_quality_guards.py`, and `test_quest_state_contract.py`.
  The 25-provider set is included in the 150, not additional coverage.
- Replayed all three saved invalid query variants through the real adapter and
  NVIDIA JSON-validation boundary using HTTP mock transport, with repair disabled:
  each fails after one simulated request, without generation.
- Replayed the original null -> missing-key repair sequence: it still fails after
  exactly two simulated requests. The repair prompt contains the same complete
  nine-query schema and retains the untrusted-output instruction boundary.
- Positive repair check: supplied an explicitly **synthetic** corrected response
  with `runtime integration client events quest state` replacing the diagnostic
  `"null"` query. It passes after one simulated repair, retaining all query text,
  the human objective, and server-owned nine-section scope. This is not evidence
  that NVIDIA will produce that correction on its own.
- Existing model routing, missing-key/degraded fallback, transport errors,
  reasoning redaction, output budgets, dialogue, quest and quality guards passed
  in the bounded set. No model or environment settings were changed.

Tests ran in the existing backend container with bytecode disabled,
`--noconftest -p no:cacheprovider`, plugin autoload disabled, and socket,
PostgreSQL and non-mock HTTP connection guards. No shared test-schema reset or
application lifespan ran. The two saved QA runs were read in read-only database
transactions only. Environment hashes matched the prior baseline.

No full backend-suite, browser walkthrough, production build, new hosted
generation, semantic-quality acceptance or production-reliability claim is made.
ECC AI Regression Testing guided replay of the observed failures rather than
adding unrelated coverage. No install, migration, database write, runtime
approval/materialization, commit or push was performed.

## Next

Review the saved progress dialogue against every eligible objective-flag state,
then address dialogue/critic usefulness together. Do not change models or expand
the feature set to hide those failures. A fresh end-to-end provider acceptance
run still requires new bounded consent and must use the normal updated planner,
without the earlier process-only diagnostic prompt override.
