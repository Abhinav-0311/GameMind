# Phase 2: NVIDIA Inference Reliability

## Outcome

Phase 2 adds optional real inference to the durable GameMind design-agent
workflow without weakening its zero-cost default. The workflow still uses the
deterministic mock provider unless `DESIGN_AGENT_PROVIDER=nvidia` is explicitly
configured.

## Implemented

- OpenAI-compatible NVIDIA chat-completions client using HTTPX.
- Independent planner, generator, critic, and reviser model configuration.
- Explicit request timeouts.
- Bounded exponential retry for network failures, timeouts, HTTP 408, HTTP 429,
  and selected HTTP 5xx responses.
- Immediate failure for authentication and non-transient request errors.
- Pydantic validation at every provider output boundary.
- One bounded structured-output repair request.
- Optional OpenAI JSON-mode request field for NVIDIA models that support it;
  schema prompting and Pydantic validation remain active when it is disabled.
- Optional observable fallback from NVIDIA to the deterministic mock provider.
- Effective provider, model, attempts, repair status, fallback reason, tokens,
  latency, and cost availability recorded in node traces.
- Run-level degraded state exposed through the design-agent API.
- Provider configuration persisted without API credentials.

## Reliability Rules

1. Authentication failures are not retried.
2. Structured-output repair runs at most once.
3. Fallback catches typed NVIDIA provider failures, not arbitrary application
   exceptions.
4. A fallback node records `mock` as the effective provider and `nvidia` as the
   failed primary provider.
5. NVIDIA pricing is not assumed. Numeric cost remains zero for schema
   compatibility while trace metadata records `cost_status=unavailable`.
6. The API key is used only in the outbound authorization header and is not
   included in persistable configuration, errors, traces, or provider results.

## Verification

Targeted provider and workflow tests:

```text
13 passed in 4.15s
```

Full backend regression:

```text
203 passed, 1 deselected in 42.51s
```

The deselected test is the repository's opt-in load benchmark, not a skipped
functional test.

Deterministic tests cover:

- Valid NVIDIA structured output.
- Token and attempt accounting.
- Rate-limit retry followed by success.
- Bounded timeout retry.
- Authentication failure without retry.
- One successful JSON repair.
- Repair-budget exhaustion.
- Explicit degraded fallback.
- Secret exclusion from persisted provider configuration.
- A full durable run reaching human review through fallback.

## Live Inference Boundary

No live NVIDIA request was required for automated verification, and no API key
was added to the repository. A live CyberRakshak smoke test remains optional and
must be performed only with a local environment secret. It should verify model
availability and output quality, not basic retry or checkpoint correctness,
which are already covered deterministically.

## Next Phase

Phase 3 adds one minimal review and trace console for starting a run, inspecting
the draft and critique, approving or rejecting it, and understanding degraded
provider events. It must not expand into section-level editing.
