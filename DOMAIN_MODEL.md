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
| Agent lifecycle | DesignAgentRun, DesignAgentJob; provider/scope, execution and bounded revision state |
| Review history | DesignAgent evidence/artifact/critique/execution/review/resolution/evaluation models in `models/design_agent.py` |
| Approved design | GameBlueprint; structured design sections, source IDs and materialization manifest |
| Runtime | NPC profiles, conversations/messages, memories, quests/objectives/progress, generated quests, world state, relationships, graph and telemetry models |

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

Materialization separately maps valid approved runtime bindings into runtime
records. Game clients must consume the appropriate project/blueprint bundle rather
than infer content from similarly named NPCs or quests.

For lifecycle behavior see [architecture](ARCHITECTURE.md); for acceptance and
current failures see [MVP.md](MVP.md). Historical QA reports remain preserved.
