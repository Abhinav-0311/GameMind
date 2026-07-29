# Phase 3 Design-Agent Console Verification

Date: 2026-07-29

## Scope

Phase 3 adds a focused human-review console for the durable GameMind design-agent workflow.

The console supports:

- selecting one indexed source and starting a governed run;
- inspecting one blueprint section at a time;
- reading the independent critique beside the artifact;
- approving or rejecting the complete run;
- requiring a concrete rejection reason;
- preserving evidence while a rejected artifact is revised and critiqued again;
- distinguishing hosted NVIDIA execution from deterministic local fallback;
- inspecting node attempts, providers, models, latency, tokens, cost, and status;
- downloading the immutable technical brief and runtime JSON after approval.

Section-level approval and inline blueprint editing remain deliberately excluded.

## Browser Verification

Playwright exercised the live Next.js page against the Docker backend.

- Desktop viewport: 1440 x 1000
- Mobile viewport: 375 x 812
- Light and dark themes
- Empty workspace and completed-run states
- Simulated awaiting-review presentation backed by a real persisted artifact
- Section tab navigation
- Rejection form focus and validation
- Trace expansion with 11 persisted node events
- Technical-brief download

Observed results:

- no browser console errors;
- no failed network requests;
- no horizontal overflow;
- one main landmark;
- no unnamed controls;
- no unlabeled form fields;
- no duplicate element IDs.

## Automated Gates

```text
Backend: 207 passed, 1 deselected
Frontend lint: passed
Frontend production build: passed
Next.js route: /design-agent prerendered successfully
```

The deselected backend test is the explicit load benchmark and is not part of the ordinary functional suite.

## Known Boundary

Run start and rejection currently use synchronous FastAPI requests. PostgreSQL and LangGraph preserve workflow state, but a slow hosted NVIDIA call can keep the initiating browser request open until the node succeeds or falls back. Moving execution behind a worker is a later production-hardening phase, not part of the scoped MVP.
