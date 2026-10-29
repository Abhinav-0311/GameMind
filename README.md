GameMind is an AI game-design co-pilot for solo and small indie teams that turns an uploaded GDD into a cited, human-approved design blueprint, built on a durable LangGraph workflow (FastAPI, PostgreSQL, ChromaDB, Next.js; Unity runtime optional and later).

## What is proven

- **Cited Flash-Lite drafts on the free tier:** two Frostpeak browser runs reached human review in **34.730 s (2026-10-28)** and **65.486 s (2026-10-27)**. These include critique—not generation-node timings or a performance guarantee. [Browser evidence](docs/acceptance/2026-10-27-live-approval-export.md).
- **Persistent human review:** B3's saved 2026-10-26 review was reopened on the later mock-profile backend on **2026-10-27**, with its draft, critique and revision count intact. This demonstrates persistence across backend launches, not general crash-recovery reliability. [B3 check](docs/acceptance/2026-10-27-browser-walkthrough.md#part-a--b3-read-only).
- **Fail-closed approval:** unconfirmed proposals blocked approval on **2026-10-26**; blocking critique findings disabled it in the browser on **2026-10-27**. [Proposal guard](docs/acceptance/2026-10-23.md#run-b4c-approval-and-export), [critique guard](docs/acceptance/2026-10-27-live-approval-export.md#step-3--approval-gate-stopped-no-submission).
- **One fresh browser approval/export success:** Run C on **2026-10-28** confirmed proposals, approved, created an immutable final and approved blueprint, exported the governed brief, and reloaded the completed state. Its original strict-hash verdict was **FAIL**, not a full MVP pass. [Run C](docs/acceptance/2026-10-27-live-approval-export.md#fresh-run-approval-attempts).
- **Fail-closed finalization integrity, with a narrow metadata exception:** offline regressions verify the guard and independent verifier on **2026-10-27/29**. Run C meets that policy, **not raw reviewed/final byte equality**. [MVP E64/E68](MVP.md#8-evidence-ledger), [policy below](#final-artifact-integrity).
- **Request budgeting:** Pacific-day counts, per-run caps and bounded process-local RPM have **2026-10-23** offline coverage; live runs reconcile startup GETs, inference and retries. These are local safety limits, not Google's quota guarantees. [MVP E60](MVP.md#8-evidence-ledger), [live retries](docs/acceptance/2026-10-23.md#run-a5-gemini-36-flash-production-retries).

## What is not proven or known limitations

- The critic varies and misses semantic defects: copied quest dialogue, unsupported assumptions and even `name resets` placeholders. **Human review is the real quality gate.** [A6](docs/acceptance/2026-10-23.md#run-a6-flash-lite-product-path), [Run C assessment](docs/acceptance/2026-10-27-live-approval-export.md#fresh-run-approval-attempts).
- Flash-Lite revision is unreliable: one small memory correction worked; larger quest/NPC corrections failed local validation. A recorded rejection with no revised artifact can leave the draft unapprovable; start a new isolated run. [B4b success](docs/acceptance/2026-10-23.md#run-b4b-f04-live-adaptive-revise-schema), [failed correction](docs/acceptance/2026-10-27-live-approval-export.md#correction-attempt-on-the-same-run), [current containment, E67](MVP.md#8-evidence-ledger).
- Newer Flash models often returned **503 in these recorded free-tier attempts**—not a claim about every account or current availability. [A3–A5](docs/acceptance/2026-10-23.md#run-a3-showcase-180s-timeout).
- The brief is a **cited design scaffold, not an implementation-ready spec**. Speaker/faction assumptions, reset rules and repeated dialogue need design work. [Run C assessment](docs/acceptance/2026-10-27-live-approval-export.md#fresh-run-approval-attempts).
- Key-less mock mode is local deterministic extraction: no new content generation and no complete design-run approval flow. [Mock walkthrough](docs/acceptance/2026-10-27-browser-walkthrough.md), [scope/limits](MVP.md).
- Retrieval uses **hashed lexical vectors, not semantic embeddings**. Unity/runtime integration is **not covered by this dashboard MVP**. [MVP scope and reproduction notes](MVP.md).

**Status: NOT ACCEPTED.** [MVP.md](MVP.md) remains the canonical checklist and evidence ledger. One successful browser journey does not establish reliable revision, semantic quality, production readiness or Unity acceptance.

## Recorded results, including failures

Individual observations, not averages. `P/R/G/C/V/F` mean plan / local retrieval / generate / critique / revise / finalize. Counts separate inference POSTs from startup model-verification GETs; failed sends count too. Latency is reported API/browser wall time unless labelled otherwise; human review time is excluded.

| Run / date / report | Model(s) | Nodes / stopping point | Recorded latency | Real requests | Outcome |
| --- | --- | --- | --- | --- | --- |
| [A, 2026-10-23](docs/acceptance/2026-10-23.md#run-a) | 3.5 Flash-Lite | P/R/G complete; C invalid | 19.438 s start | 3 POST + 1 GET | Critique validation failed; no review/approval |
| [A3, 2026-10-25](docs/acceptance/2026-10-23.md#run-a3-showcase-180s-timeout) | Lite planner; 3.8 Flash generator | P/R complete; G upstream 503 | 148.105 s start | 2 POST + 2 GET | No draft; this attempt stopped before retries |
| [A5, 2026-10-25](docs/acceptance/2026-10-23.md#run-a5-gemini-36-flash-production-retries) | Lite planner; 3.6 Flash generator | P/R complete; G failed three sends | 48.820 s start | 4 POST + 2 GET | Three upstream 503s, including two production retries |
| [A6, 2026-10-26](docs/acceptance/2026-10-23.md#run-a6-flash-lite-product-path) | 3.5 Flash-Lite | P/R/G/C → review | 31.160 s start, with observer overhead | 3 POST + 1 GET | Real, non-degraded draft; critic missed defects; approval not attempted |
| [B4b, 2026-10-26](docs/acceptance/2026-10-23.md#run-b4b-f04-live-adaptive-revise-schema) | 3.5 Flash-Lite | P/R/G/C → V/C → review | 84.928 s start; 49.302 s correction, both instrumented | 5 POST + 1 GET | Small memory correction passed; frozen decision survived; eight other sections unchanged |
| [Fresh proof, 2026-10-27](docs/acceptance/2026-10-27-live-approval-export.md#verdict-fail--approval-blocked-at-human-review) | 3.5 Flash-Lite | P/R/G/C → review | 65.486 s start | 3 POST + 1 GET | Two medium findings blocked browser approval |
| [Same-run correction, 2026-10-28](docs/acceptance/2026-10-27-live-approval-export.md#resumed-with-docker-running--2026-10-28) | 3.5 Flash-Lite | V failed; no new C/F | 4.352 s review request | 1 POST + 1 GET | Google 200, local validation failed; draft retained, approval blocked |
| [Run C, 2026-10-28](docs/acceptance/2026-10-27-live-approval-export.md#fresh-run-approval-attempts) | 3.5 Flash-Lite | P/R/G/C → approval/F/export/reload | 34.730 s to review; 426 ms approval | 4 POST + 1 GET | Browser flow succeeded; C needed one corrective re-ask. Strict hash FAIL; documented-metadata policy met |

The historical [2026-10-27 full browser attempt](docs/acceptance/2026-10-27-live-browser-walkthrough.md) also failed correction and then returned 500 on approval. [E67](MVP.md#8-evidence-ledger) records offline containment of that conflicting-review error, not repair of that historical run or proof of useful correction.

## Demo

A recorded walkthrough will be linked here; the app can be tried with the Frostpeak sample in the quickstart.

## Quickstart — synthetic Frostpeak, hosted DEV profile

Prerequisites: Docker Engine with Compose, Node.js 20+ and npm. This is local setup, **not production deployment**. Free-tier Gemini input/output may be used by Google to improve its products: use only the [synthetic Frostpeak sample](docs/demo/sample_gdd_frostpeak.md) or other non-confidential GDDs. [Unpaid-service data terms](https://ai.google.dev/gemini-api/terms#unpaid-services).

1. Clone and enter the repository:

   ```powershell
   git clone https://github.com/Abhinav-0311/GameMind.git
   cd GameMind
   ```

2. Copy the example environment **only if `.env` does not already exist**:

   ```powershell
   if (-not (Test-Path .env)) { Copy-Item .env.example .env }
   ```

3. Set these values in your local `.env` before hosted startup; keep the other example settings. Never commit your key:

   ```dotenv
   LLM_PROFILE=dev
   GEMINI_API_KEY=<your Gemini API key>
   GEMINI_DEV_MODEL=gemini-3.5-flash-lite
   GEMINI_TIMEOUT_SECONDS=180
   DESIGN_AGENT_FALLBACK_TO_MOCK=true
   DESIGN_AGENT_FALLBACK_DISABLED_NODES=["revise"]
   ```

   **Offline alternative:** leave `LLM_PROFILE=test` and `GEMINI_API_KEY` blank. No key or Google requests are needed; this is extraction/workflow inspection, **not** a generation → approval demo. A hosted key does not guarantee acceptable output.

4. Start PostgreSQL, Chroma and the backend. Its normal command applies migrations before serving:

   ```powershell
   docker compose up -d --build db chromadb backend
   ```

   Check [health](http://localhost:8000/health) and [API docs](http://localhost:8000/docs). Gemini startup makes a budgeted model-verification GET per distinct selected model; it is not zero-request startup. The optional worker is not needed for this inline local flow.

5. Start the frontend in another terminal, from the cloned repository:

   ```powershell
   cd frontend
   npm ci
   $env:NEXT_PUBLIC_API_URL='http://localhost:8000'
   npm run dev
   ```

   Open the [dashboard](http://localhost:3000/design-agent).

6. Create a **new isolated workspace**. In **Sources → Load Frostpeak demo**, load the bundled sample (or upload `docs/demo/sample_gdd_frostpeak.md`). Run local review and inspect its questions. To follow Run C, resolve the platform decision as human direction: `unity_runtime_preview.content.target_platform` must be `"Windows PC"`; this is not a GDD fact.

7. Start a governed run with **max revisions 2**, **runtime preview enabled**, and the explicit **unspecified-memory** option for this sample. Read and grant hosted-transfer consent. These are Run C's settings; a runtime preview is not runtime approval. At human review, inspect the cited Summary, draft sections, frozen evidence, actual providers, critique and scorecard.

8. Review the content yourself. If gates permit, confirm the current draft's proposals individually, approve once, then export the technical brief from the completed run. A degraded run needs deliberate extra acknowledgement. If findings block approval, inspect them—do not dismiss them merely to obtain an export. Correction is unreliable; a failed correction with a recorded rejection may require a new isolated run.

Run C browser-verified source/decision/consent → generation → proposal confirmation → approval → export → completed reload. It did **not** verify a clean-clone installation: acceptance used an existing SDK-equipped test image with source bind-mounted. Earlier B4b/B4c API checks alone were not browser proof. Do not reuse historical QA workspaces for this quickstart.

Stop the frontend with **Ctrl+C**; stop the stack with `docker compose stop` from the repository root. Do not remove persistent volumes to stop the app.

## Final artifact integrity

The immutable final artifact preserves the reviewed design content, with explicitly enumerated deterministic server metadata additions (memory_unspecified and runtime_deferred plus its warning). Raw reviewed and final hashes may therefore differ; the verifier checks both hashes and rejects every other difference.

The verifier derives allowed additions from the **reviewed content and frozen settings**; it never strips flags blindly or ignores whole sections. Verdicts: `EXACT`, `EQUAL_EXCEPT_DOCUMENTED_METADATA`, `MISMATCH`. Run C's sole added `/npc_memory_design/memory_unspecified=true` meets this policy and **did not meet strict byte equality**. Its original FAIL verdict remains in the report. Moving both flags before review is planned after the MVP. [E64/E68](MVP.md#8-evidence-ledger), [Run C hashes](docs/acceptance/2026-10-27-live-approval-export.md#read-only-persistence-and-strict-integrity-result).

From `backend/` in a configured backend environment:

```powershell
python verify_final_integrity.py <run-id>
```

This reads the approval-linked draft and immutable final in one PostgreSQL READ ONLY transaction, without a model call. It prints both canonical UTF-8 JSON SHA-256 hashes and all differing/offending paths. Exit 0 accepts either equality verdict, 1 means mismatch, 2 means read/input failure. CLI database selection is tested offline; **live application CLI execution is not recorded in E68**. An integrity verdict is not a content-quality score.

## Providers and request budgets

- `LLM_PROFILE=test`: key-less, offline extraction. `dev`: environment-selected `GEMINI_DEV_MODEL` for every hosted node; the recorded default is `gemini-3.5-flash-lite`. `showcase`: dev model for planning, `GEMINI_SHOWCASE_MODEL` for artifact work. Recorded newer-Flash failures make showcase **not** the quickstart. [Profiles and outcomes](docs/acceptance/2026-10-23.md).
- Mock fallback is degraded local output, not hosted quality. It waives no approval checks; Gemini profiles exclude revise by default. Legacy NVIDIA does not apply that node-exclusion setting. [Provider selection](backend/app/design_agent/provider_factory.py), [B3 warning](docs/acceptance/2026-10-27-browser-walkthrough.md#part-a--b3-read-only), [E65/E67](MVP.md#8-evidence-ledger).
- **NVIDIA is a legacy optional design-agent provider**, not the current DEV path or every runtime endpoint. Existing code/configuration remains; provider-neutral naming/cleanup is planned after the MVP. [Historical routing and Gemini extension](MVP.md#chunk-1-execution-contract--decided-2026-10-18).

Local Gemini budget defaults in `.env.example`: **dev 5 RPM / 500 RPD**, **showcase 3 RPM / 20 RPD**, **12 attempts/run**, preflight estimate **8**. PostgreSQL reservations use the `America/Los_Angeles` day; every real HTTP attempt, including startup GETs and failed/retried sends, counts before sending. RPM is process-local, not distributed. These limits do not establish Google's quota or billing; a reservation can exceed actual sends after a crash. [Offline E60](MVP.md#8-evidence-ledger), [live reconciliation](docs/acceptance/2026-10-27-live-approval-export.md#final-quota-evidence-and-cleanup).

Read today's reserved counts without contacting Google:

```powershell
docker compose exec -T backend python gemini_usage.py
```

## Implementation map and safe verification

| Area | Entry point |
| --- | --- |
| Next.js / React dashboard | `frontend/src/app/` |
| FastAPI API | `backend/main.py`, `backend/app/api/v1/` |
| PostgreSQL models / migrations | `backend/app/models/`, `backend/alembic/` |
| ChromaDB hashed lexical retrieval | `backend/app/services/rag_service.py` |
| LangGraph workflow / checkpoints / provider boundary | `backend/app/design_agent/` |
| Optional, later Unity client | `Unity/Assets/Scripts/` — not MVP proof |

LangGraph owns orchestration; a declared LangChain dependency is not a separate demonstrated agent workflow. [ARCHITECTURE.md](ARCHITECTURE.md) and [DOMAIN_MODEL.md](DOMAIN_MODEL.md) map provider, budget, revision and final-metadata behavior; they are not release evidence. Current status is in [MVP.md](MVP.md).

**Never run pytest inside the normal application container:** `backend/conftest.py` drops/recreates its target schema. Use fresh disposable storage via the [CI workflow](.github/workflows/verify.yml) or guarded [MVP baseline procedure](MVP.md#7-current-blockers-and-next-work). Never reset an application or retained QA database.

Frontend checks from `frontend/`: `npm run lint`, `npm run build`, `npm run test:design-agent-api`. The separate `npm run test:dashboard-states` intercepts API responses; it is **not** live browser/backend acceptance. Passing tests/builds do not establish useful hosted output, reliable correction or Unity execution. [Verification ledger](MVP.md#8-evidence-ledger).

Further reference: [dashboard workflow](docs/workflows/dashboard_workspace.md), [deployment](docs/deployment.md), [security baseline](SECURITY_BASELINE.md), [optional runtime contracts](docs/integrations/runtime_api.md). Next work and open gates remain in [MVP.md](MVP.md), not a test count or historical phase label.
