# NVIDIA structured-output transport and malformed retry — 2026-10-16

## Implemented local fix; hosted behavior still unverified

The NVIDIA adapter now requests strict JSON Schema through `response_format`, following the current NVIDIA LangChain client's preferred request shape. It no longer sends top-level `guided_json` for native structured requests.

The existing `CompletionRequest.guided_json` flag remains for caller compatibility; its meaning is still native structured output versus the existing explicit prompt-only mode. No new configuration option, model, dependency or fallback chain was added.

The truncation guard now stops before a larger-token retry when output contains an over-64-character closing-delimiter run and the existing JSON nesting scanner confirms a mismatch. Both conditions are required, so unfinished strings containing delimiter characters are not mistaken for this corruption case. Actual truncation retains the existing single larger-budget retry.

## What the source research establishes

The older [NIM structured-generation guide](https://docs.nvidia.com/nim/large-language-models/1.13.0/structured-generation.html) shows the `nvext` envelope. That alone was insufficient grounds to move the field.

The [current NVIDIA LangChain implementation](https://raw.githubusercontent.com/langchain-ai/langchain-nvidia/main/libs/ai-endpoints/langchain_nvidia_ai_endpoints/chat_models.py) recognizes three envelope styles and prioritizes the OpenAI-compatible structured format. Its implementation notes warn that legacy fields can be ignored by some backends even when HTTP succeeds. Our request shape is aligned with that preference, without importing or installing the client.

The [exact hosted Super reference](https://docs.api.nvidia.com/nim/reference/nvidia-nemotron-3-super-120b-a12b-infer) does not fully establish this model's schema-feature support. Endpoint-specific enforcement and whether the old envelope caused the saved failure still require a live control. Source references checked on 2026-10-16.

## Scope and behavior

Production change: `backend/app/design_agent/llm_provider.py`.

Existing tests updated: `test_design_agent_llm_provider.py`, `test_structured_output_diagnostics.py`, `test_content_only_qa.py`, `test_design_contract_v2.py`.

- Native request body contains `response_format.type=json_schema`, `json_schema.strict=true`, a fixed response name and the unchanged response model schema.
- Planning/prompt-only requests are unchanged.
- Request rejection with HTTP 400/422 surfaces immediately; there is no automatic retry using weaker constraints or an alternative envelope.
- Authentication, model routing, thinking mode, timeout, ordinary transport retries and token settings are unchanged.
- The delimiter-loop error retains sanitized syntax position, finish reason, model and usage diagnostics, with `truncation_retry_skipped=delimiter_loop`.
- There is no repair request for this detected loop and no automatic recovery into an approvable artifact.
- All grounding, ownership, independent critique, proposal-confirmation and approval gates remain in place.

## Verification

- Red phase: the updated envelope assertion and three retry controls failed against the previous implementation.
- Focused provider/diagnostic selection: 39 passed, one existing warning.
- Final selected offline regression run: **584 passed, five database-fixture cases deselected, one existing Starlette/AnyIO warning, 22.72 s**. Five focused cases were added, not 584.
- Controlled API generation → revision → independent mocked critique → explicit design approval → brief export remains covered by the selected suite. It uses mocked HTTP, disposable SQLite and in-memory checkpoints, not hosted inference or native PostgreSQL.
- Replay of each immutable saved malformed Frostpeak output through the actual updated provider with MockTransport now makes exactly one mocked request and rejects the delimiter loop. The historical run still records the two requests it actually used; it was not rewritten.
- Legitimate truncated text, including an unterminated string ending in many delimiter characters, still receives its existing bounded retry. The same schema is sent on that retry.
- Native payload tests preserve the exact Pydantic schema and verify strict mode and absence of legacy envelope fields.
- HTTP 400/422 controls verify one request only, with no silent schema downgrade.
- All 39 application-table fingerprints match the pre-QA baseline; historical telemetry comparison uses the recorded cutoff.
- Existing QA artifacts/closed ledgers and saved report/result hashes unchanged; no new approved blueprints.
- Environment-file hashes unchanged; backend/database/Chroma healthy.
- Syntax parsing and scoped whitespace checks passed.

No hosted requests, installs, model/environment changes, database migrations, application-workspace writes, commits or pushes occurred in this chunk. No frontend build/browser walkthrough or full backend-suite rerun. Dedicated lint/type/coverage tools were not installed; no measured coverage claim.

## Remaining uncertainty

The replay proves that the retry waste is fixed, not that NVIDIA now generates useful game content. Local request-shape tests cannot prove remote schema enforcement, and a basic schema success would not prove support for every complex union/reference/pattern in the full design schema.

If the endpoint rejects strict structured requests, the failure will be visible rather than silently falling back. The current patch's hosted compatibility must be checked before a new GDD-quality run.

## Smallest next gate

One fresh, explicitly authorized NVIDIA request using **synthetic data only**, with no GDD excerpts, database access, retries, repair, approval or environment/model changes:

- Use the currently configured Super model and the production strict response-format envelope.
- Limit output to a small allowance for a two-field object.
- Require a fixed marker string and fixed integer in the schema.
- Give a deliberately conflicting plain-text instruction so a normal JSON-compliant prompt cannot falsely establish schema enforcement.
- Accept only a clean stopped response that parses and satisfies the exact schema. HTTP 200 alone is not success.
- Record the result separately; do not reuse or reopen a closed QA budget.

Only after this transport control should the focused NPC/quest revision and real independent critique be retried. Full useful generation → explicit design approval → brief export remains outstanding.

Ponytail kept the implementation in the existing adapter and reused its scanner/diagnostics. Python Testing supplied red/green controls; Verification Loop separates local proof from the outstanding hosted acceptance.

