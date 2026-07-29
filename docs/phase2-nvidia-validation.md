# Phase 2 NVIDIA Validation

Validated on July 29, 2026 using synthetic game-design content only. No private
or real GDD content was sent to NVIDIA during this verification.

## Provider Contract

- Planner: `nvidia/llama-3.1-nemotron-nano-8b-v1`
- Draft, critique, revision:
  `nvidia/llama-3.3-nemotron-super-49b-v1.5`
- Planner key: `NVIDIA_NANO_API_KEY`
- Draft/critic/revision key: `NVIDIA_SUPER_API_KEY`
- Hosted requests are enabled only when `LLM_PROVIDER=nvidia`.
- Mock remains the deterministic default for tests and CI.

The planner model owns only the semantic retrieval query. The user objective and
the nine required GameMind blueprint sections are deterministic workflow fields.
This prevents malformed model output from changing the workflow contract.

## Live Provider Results

The Super critic completed three consecutive minimal structured-output calls.
Observed latency was approximately 26-55 seconds. Two calls required a second
transport attempt. Its separate reasoning field was detected and discarded.

The Nano endpoint accepted authentication but repeatedly exceeded the
30-second-per-attempt reliability budget during this validation window. The
bounded provider stopped after three attempts and returned the sanitized
`provider_timeout` failure code.

These measurements describe the free hosted endpoint during one validation
window; they are not a service-level guarantee.

## Durable Workflow Proof

An isolated synthetic GDD completed this sequence:

```text
plan
-> retrieve evidence
-> generate blueprint
-> critique
-> human review
-> reject
-> revise using the existing evidence snapshot
-> critique
-> human review
-> restart backend
-> approve
-> finalize
```

Measured assertions:

- Retrieval executions: 1
- Retrieval revision after rejection: 1
- Revision executions: 1
- Critique executions: 2
- Final artifact: immutable
- Technical brief export: successful
- Runtime export: successful
- Provider-node traces with latency: all present
- Degraded provider nodes: 5

The hosted calls timed out for the full-payload workflow and each node completed
through the observable mock fallback. Trace records retained provider attempts,
failure codes, primary wait time, total node latency, token estimates, and
degraded status.

## Operational Conclusion

Phase 2 proves the provider abstraction, real NVIDIA authentication and model
routing, structured-output validation, bounded retry behavior, reasoning
isolation, observable fallback, durable checkpoints, evidence reuse, and
restart-safe human approval.

The free NVIDIA endpoint is suitable as an optional inference path, not as an
unbounded synchronous dependency. Production UI work must present these runs as
durable asynchronous workflows and expose degraded execution clearly.
