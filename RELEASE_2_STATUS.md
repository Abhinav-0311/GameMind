# GameMind: Release 2 Status & Progress Ledger

This document serves as the status report for Release 2 development within the canonical workspace `E:\College\Project\Bot`.

---

## 1. Completed Phases

### Phase 7A: NPC Profile Data Layer
* **Objective:** Design and store static NPC characteristics separating configuration from future gameplay execution.
* **Deliverables:**
  * Created the PostgreSQL model for `npc_profiles` using UUID primary keys.
  * Implemented backend schemas, validation constraints, and regex checking on slug identifiers (`^[a-z0-9_-]+$`).
  * Created REST CRUD endpoints in FastAPI (`POST`, `GET`, `PUT`, `DELETE`).
  * Implemented soft-delete workflow setting `deleted_at` timestamp rather than hard deletion.
  * Verified backend logic with full integration tests.

### Phase 7B: NPC Studio UI
* **Objective:** Implement the frontend management console for NPC configuration.
* **Deliverables:**
  * Added TypeScript interfaces and api endpoints fetch clients in `frontend/src/lib/api.ts`.
  * Activated NPC Studio navigation in the sidebar and Command Palette (`Ctrl + K` action, shortcut `G N`) inside `DashboardLayout.tsx`.
  * Created `frontend/src/app/npcs/page.tsx` displaying a high-density, Vercel-style table grid of all active NPCs.
  * Implemented live text search filters and faction filters.
  * Created a Stripe-style slide-over Form Drawer for creating and editing NPC characteristics (Name, Title, Faction, Personality guidelines, Voice IDs, and JSON configuration files).
  * Implemented client-side regex slug validation and JSON parsing verification.
  * Implemented soft-delete modal confirmation displaying database implications.

### Phase 8A: Dialogue Assembly Layer
* **Objective:** Build a deterministic and testable prompt construction, persona injection, and context assembler layer without making live LLM calls.
* **Deliverables:**
  * Created schemas for `DialogueAssembleRequest` and `DialogueAssembleResponse` incorporating `npc_slug`, `player_message`, `selected_chunk_ids`, `assembled_prompt`, `character_count`, `estimated_tokens`, and database-retrieved chunks metadata.
  * Created a prompt assembly service `dialogue_service.py` to fetch, sort, truncate, and stitch NPC attributes, RAG database context, and player inputs into a final formatted string, returning warnings upon truncation.
  * Exposed `POST /api/v1/dialogue/assemble` API endpoint router.
  * Integrated a split-pane Dialogue Debugger drawer panel inside the NPC Studio UI enabling live lore retrieval checks, checkbox-based chunk filters, token telemetries, warning logs, and prompt copying.

### Phase 8A.5: Prompt Evaluation Scenario Tests
* **Objective:** Regression test dialogue assembly behaviors using integration fixtures.
* **Deliverables:**
  * Wrote an automated integration test suite `test_dialogue.py` verifying 8 unique prompt assembly scenarios (Persona consistency, claim refusal safety instructions, multi-chunk formatting, missing factions, deleted profile rejection, empty context fallback, oversized message truncation warnings, and context window overflow protection).
  * Verified all test cases pass successfully.

---

## 2. Current Database Tables

| Table Name | Primary Key | Key Columns | Purpose |
| :--- | :--- | :--- | :--- |
| **`documents`** | `UUID` | `title`, `content_type` | Stores metadata of uploaded PDF/markdown game files. |
| **`document_chunks`**| `UUID` | `document_id`, `chunk_index`, `content`, `metadata_json` | Stores parsed text chunks and vectors. |
| **`npc_profiles`** | `UUID` | `slug` (unique), `name`, `personality_summary`, `dialogue_style`, `faction_alignment`, `animation_hints` (JSONB), `memory_settings` (JSONB), `deleted_at` | Stores static NPC parameters and soft-delete states. |

---

## 3. Current API Endpoints

### Health Check
* `GET /health` — Verifies API running and connections to PostgreSQL, ChromaDB, and Gemini API setup.

### Knowledge Library (RAG)
* `GET /api/v1/documents` — Lists ingested documents.
* `POST /api/v1/documents/upload` — Accepts txt, md, or pdf uploads (max 5MB), extracts chunks, and embeds them.
* `GET /api/v1/documents/{id}` — Fetches document metadata and its chunk list.
* `DELETE /api/v1/documents/{id}` — Deletes PG chunks, Chroma vectors, and document metadata.
* `POST /api/v1/query` — RAG vector search matching user text against chunks.

### NPC Studio CRUD
* `GET /api/v1/npcs` — Returns all active (non-soft-deleted) NPC profiles.
* `GET /api/v1/npcs/{id}` — Fetches a single active NPC profile by UUID (404 if soft-deleted).
* `POST /api/v1/npcs` — Creates a new NPC profile. Rejects duplicate slugs and validates format.
* `PUT /api/v1/npcs/{id}` — Updates active NPC profile configuration fields.
* `DELETE /api/v1/npcs/{id}` — Soft-deletes an NPC profile (populates `deleted_at`).

### Dialogue Assembly Layer
* `POST /api/v1/dialogue/assemble` — Deterministically formats NPC attributes, retrieves selection database lore, and structures the final prompt context.


---

## 4. Current Frontend Pages

* **`/` (Workspace Overview):** High-density statistics dashboard representing the current database volumes (documents, chunks, NPCs).
* **`/knowledge` (Knowledge Base):** Upload and manage manuals, and inspect parsed text paragraphs.
* **`/query` (Query Studio):** Console to run vector queries and test semantic search confidence scores.
* **`/npcs` (NPC Studio):** Management dashboard to search, filter, create, edit, and archive NPC configurations.

---

## 5. Known Technical Debt

1. **Archive Recovery UI:** Soft-deleted NPCs remain in the database (with `deleted_at` filled), but there is currently no client interface to view, restore, or purge soft-deleted records.
2. **JSON Editor Experience:** Advanced configuration parameters (`animation_hints`, `memory_settings`, `metadata`) are entered as text strings inside textareas, validating syntax on submit. A structured key-value table form editor would improve usability.
3. **Data Fetching Hooks:** Page components currently handle loading and error states using manual `fetch` calls and React state wrappers inside `useEffect`. Transitioning to a react data fetching client (e.g. SWR or React Query) would streamline frontend state sync.

---

## 6. Security Decisions

* **Authentication Isolation:** Restored standard secure authentication (`scram-sha-256`) in the database. Credentials are kept inside local `.env` files (excluded from code repositories).
* **Scope Restriction Governance:** Formulated the canonical project boundary rule in `SECURITY_BASELINE.md` preventing developer tooling or agents from searching or reusing credentials from other local projects.
* **Client-Side Validation:** Rigid slug format validation (`^[a-z0-9_-]+$`) executed in the browser prevents malformed input, SQL issues, or URL-safe schema failures prior to network submission.

---

## 7. Open Risks

* **Faction Referrals:** Factions are currently freeform text slugs. There is no relational faction validation, which could result in naming mismatches (e.g. `cinder_vanguard` vs `cindervanguard`).
* **Context Overload:** As NPC profiles (personality summaries, dialog guidelines) and semantic search RAG chunks grow, sending raw data to LLM context windows will hit token limits and scale API costs.

---

## 8. Recommended Next Phase

### Phase 8A: Dialogue Assembly Layer (Release 2)
* **Focus:** Build a deterministic and testable prompt construction, persona injection, and context assembler layer without making LLM calls.
* **Actions:**
  * Define structured input payload schema:
    ```json
    {
      "npc_id": "uuid",
      "player_message": "string",
      "retrieved_lore": ["string"]
    }
    ```
  * Define structured output payload schema:
    ```json
    {
      "system_prompt": "string",
      "npc_context": "string",
      "retrieved_context": "string",
      "assembled_prompt": "string"
    }
    ```
  * Implement prompt construction logic (NPC persona details, core instructions, dialogue style directives, and retrieved lore integration).
  * Build active context window management to prevent token overflow.
  * Define conversation state management tracking short-term memory dialogue cycles.
  * Build a dialogue preview/debugger view in the NPC Studio UI.

### Phase 8A.5: Prompt Evaluation (Release 2)
* **Focus:** Test the deterministic assembly layer using regression fixtures.
* **Actions:**
  * Define test scenarios and fixture structures:
    - NPC stays in character
    - NPC refuses unsupported lore claims
    - Contradictory lore retrieval
    - Empty retrieval results
    - Excessively large retrieval sets
    - Missing faction alignment
    - Deleted NPC profile
  * Save scenario payloads as fixtures to run automated regression checks against prompt format templates.

### Phase 8B: Gemini Integration (Release 2)
* **Focus:** Implement live generative engine capabilities after validation of the deterministic assembly layer.
* **Actions:**
  * Integrate backend services with the Gemini API.
  * Implement token accounting, rate limiting, and retry policies.
  * Expose an interactive chat simulator window inside the NPC Studio UI mapping assembled prompts to Gemini queries.
  * Build observability logs tracking token consumption and Gemini latency.

