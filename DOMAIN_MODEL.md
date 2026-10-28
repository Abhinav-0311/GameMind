# GameMind domain boundaries

This is an orientation map, not a duplicate schema specification.
SQLAlchemy models in `backend/app/models/` and migrations in `backend/alembic/`
are the database authority. Pydantic contracts define the API/design wire shapes.
The previous Release 2/3 examples are not current schema or acceptance guarantees.

## Durable ownership

| Area | Models / purpose |
| --- | --- |
| Access | User, ProjectMembership, AccountActionToken; accounts, workspace roles and one-time actions |
| Workspace | GameProject; boundary for project data |
| Sources | Document, DocumentChunk; revision lineage, source kinds, stored text and evidence |
| Human direction | DesignDecision; unresolved/resolved design questions and supporting sources |
| Agent lifecycle | DesignAgentRun, DesignAgentJob; provider/scope, checkpoints/jobs and bounded revision state. `revision_count` counts saved revisions; `model_config.consecutive_revision_failures` counts consecutive failed corrections separately (default limit 3 from `DESIGN_AGENT_MAX_CONSECUTIVE_REVISION_FAILURES`), reset on a saved revision. `gemini_request_count` is the durable per-run HTTP-attempt counter. |
| Gemini budgets | GeminiDailyUsage (`models/gemini_usage.py`, table `gemini_daily_usage`); composite key `(model_id, pacific_day)`, reserved `requests` and `exhausted` flag. Shared per model/database, not project-scoped; Pacific date is derived with `America/Los_Angeles`. RPM windows live only in process memory, not this table. |
| Review history | DesignAgent evidence/artifact/critique/execution/review/resolution/evaluation models in `models/design_agent.py` |
| Approved design | GameBlueprint; structured design sections, source IDs and materialization manifest |
| Runtime | NPC profiles, conversations/messages, memories, quests/objectives/progress, generated quests, world state, relationships, graph and telemetry models |

The counters above have different meanings: an unchanged draft after failed
revision consumes no saved-revision slot, but any real Gemini attempts still
count against quota and the separate failure counter increments. A recorded
rejection remains in review history; a conflicting approval on that same artifact is refused before
graph resume. A new, successfully revised artifact can receive its own review.
Degraded acknowledgement is recorded in approval-event `details`; it is not a
claim that fallback content is source-verified. See `workflow.py`, `service.py`
and `review_policy.py` under `backend/app/design_agent/` for those lifecycle rules.

LangGraph checkpoint tables are declared in the model metadata and created by
Alembic. Stored history is not disposable just because it belongs to a QA project.

## Design data is not runtime data

Design sections carry `content`, `citations`, `confidence` and `warnings`. The
governed content contract names summary, narrative, art, NPCs, memory, levels,
gameplay, quests and runtime preview; missing facts stay explicit unknowns.

`design_agent/content_draft.py` separates model-authored content from server-derived
keys/state bookkeeping. Quest state contracts describe objectives, all-required
completion, optional failure and confirmed restart. NPC dialogue mappings bind
spoken text to a stage/quest eligibility and repeat policy. These are reviewable
design proposals, not proof of working engine events.

Draft/revision artifacts reference frozen evidence. Final approval binds the exact
current artifact/review and creates an immutable design snapshot. A design brief
may be exported after valid design approval; runtime-deferred runs cannot acquire
a runtime export through that approval.

The immutable snapshot preserves reviewed design content with enumerated,
deterministic final-only metadata: `npc_memory_design.memory_unspecified=true`
only for the frozen unspecified-memory opt-in and empty/uncited/warned reviewed
memory; `unity_runtime_preview.runtime_deferred=true` plus the exact deferral
warning only for frozen `defer_runtime=true`. These are section-level metadata,
not new GDD facts or model output after review. `workflow._finalize` checks the
reviewed/candidate digests before saving; any other difference fails closed with
no new blueprint/final and returns to review. Raw reviewed/final hashes may
therefore differ. The independent `backend/verify_final_integrity.py` reports
both hashes and all paths and re-derives only those exceptions; it never ignores
whole sections. See [architecture](ARCHITECTURE.md#critique-and-finalization-integrity)
for the exact warning and predicates. Moving these flags before human review is
planned after the MVP ([E68](MVP.md#8-evidence-ledger)).

Materialization separately maps valid approved runtime bindings into runtime
records. Game clients must consume the appropriate project/blueprint bundle rather
than infer content from similarly named NPCs or quests.

For lifecycle behavior see [architecture](ARCHITECTURE.md); for acceptance and
current failures see [MVP.md](MVP.md). Historical QA reports remain preserved.
