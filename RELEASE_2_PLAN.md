# GameMind: Release 2 Implementation Plan (Gameplay Content Layer)

This plan maps out the architecture and design blueprints for **Release 2 (Gameplay Content Layer)** of GameMind. It separates development into 5 sequential phases.

No code changes or implementations will be conducted during this planning phase.

---

## Phase 7A: NPC Data Model

### Goals
Establish a structured schema to store NPC metadata, personality constraints, dialogue styles, and initial world parameters in the relational database.

### Database Changes (PostgreSQL)
Create the `npcs` configuration table:
```sql
CREATE TABLE npcs (
    id VARCHAR(100) PRIMARY KEY, -- e.g., 'eldrin_mage'
    name VARCHAR(100) NOT NULL,
    title VARCHAR(100),
    personality_summary TEXT NOT NULL, -- e.g., 'Cautious librarian, speaks in warning tones.'
    dialogue_style TEXT, -- e.g., 'Arcane vocabulary, hesitant, uses ellipses frequently.'
    base_location VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

### API Endpoints
* `POST /api/v1/npcs` - Ingests a new NPC configuration profile.
* `GET /api/v1/npcs` - Lists all stored NPC profiles.
* `GET /api/v1/npcs/{id}` - Retrieves detailed configuration for a specific character.
* `PUT /api/v1/npcs/{id}` - Modifies NPC personality summaries and traits.
* `DELETE /api/v1/npcs/{id}` - Cleans up NPC profile configuration.

### UI Screens
None. This is a pure backend schema and CRUD api validation phase.

### Implementation Order
1 (First phase of Release 2, acts as the foundation database layer).

### Risks
- Ensuring URL-safe, lowercase, alphanumeric ID names (e.g. `eldrin_mage` instead of user-facing spaces like `Eldrin the Mage`).

---

## Phase 7B: NPC Studio UI

### Goals
Construct the visual management board for creating, modifying, and listing NPC character profiles.

### Database Changes
None.

### API Endpoints
Connects to `/api/v1/npcs` endpoints.

### UI Screens
* **NPC Studio View:**
  - Accessible via sidebar navigation.
  - **Main Area:** Vercel-style list table showing name, title, base location, and shortcuts to modify profiles.
  - **Right Drawer Panel:** Stripe-style configuration form (inputs for ID, Name, Title, Base Location, Personality summary text block, and Dialogue style rules).

### Implementation Order
2 (Following database model completion).

### Risks
- Validation of required form parameters before executing PUT/POST calls.

---

## Phase 8: NPC Dialogue Engine

### Goals
Generate context-aware, lore-consistent NPC dialogues returning structured JSON objects optimized for game engines (Unity).

### Database Changes
None.

### API Endpoints
* `POST /api/v1/dialogue` - Triggers structured dialogue generation.
  - **Request Body:**
    ```json
    {
      "npc_id": "eldrin_mage",
      "player_message": "What do you know about Vulcana?",
      "location": "watchtower",
      "reputation": "friendly"
    }
    ```
  - **Response Schema (Structured Gemini Output):**
    ```json
    {
      "dialogue": "Vulcana's fires burn hot, traveler. Eldrin warns you: stay clear of Warlord Ignis's iron legions.",
      "emotion": "concerned",
      "animation": "look_away"
    }
    ```

### UI Screens
* **NPC Studio (Dialogue Playground Panel):**
  - Integrated under character selections.
  - Lets developers enter a player message, select a simulated location, choose a reputation tier, and click "Submit".
  - Displays the output in a visual chat bubble (with emotion tags) side-by-side with a raw monospace JSON response block.

### Implementation Order
3 (Requires NPC profiles schema to load personality guidelines).

### Risks
- **Hallucinations:** Gemini returning statements clashing with ingested lore. Mitigated by querying RAG for document contexts and injecting matches into the system prompt.
- **Latency:** Structured outputs can introduce a 1-2 second generation delay.

---

## Phase 9: Quest Generator

### Goals
Enable the dynamic generation of side-quests that are consistent with world history and NPC backgrounds.

### Database Changes
Create `generated_quests` database table:
```sql
CREATE TABLE generated_quests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    npc_id VARCHAR(100) REFERENCES npcs(id) ON DELETE SET NULL,
    title VARCHAR(255) NOT NULL,
    objectives JSONB NOT NULL, -- list of steps
    rewards JSONB NOT NULL, -- gold, xp, items
    difficulty VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

### API Endpoints
* `POST /api/v1/quests/generate` - Generates a structured side quest.
  - **Request Body:** `{ "npc_id": "eldrin_mage", "player_level": 12, "location": "frostpeak" }`
  - **Response Body:** Returns title, list of objective steps, difficulty rating, and rewards list.

### UI Screens
* **Quest Studio View:**
  - Standard sandbox interface allowing developers to trigger quest generations.
  - Displays generated quest sheets (with objectives checklist, gold, and XP rewards) formatted in a clear, high-density print layout.

### Implementation Order
4.

### Risks
- **Impossible Objectives:** Quest generator generating locations or enemies that do not exist in the world-building documentation. Resolved by scoping RAG context boundaries in system prompts.

---

## Phase 10: Hint System

### Goals
Expose progressive, puzzle-solving hint engines that avoid spoiling story paths.

### Database Changes
None.

### API Endpoints
* `POST /api/v1/hints/generate` - Generates hint tiers.
  - **Request Body:** `{ "quest_title": "Missing Patrol", "puzzle_description": "Geothermal Lock", "level": 1 }`
  - **Response Body:** Returns progressive hints (Level 1: Subtle, Level 2: Moderate, Level 3: Direct).

### UI Screens
* **Quest Studio (Hint Inspector):**
  - Text input to specify the puzzle, with selectors for Level 1, 2, and 3 hints. Displays progressive hints.

### Implementation Order
5 (Final phase of Release 2).

### Risks
- Preventing Level 1 hints from disclosing the puzzle resolution directly. Corrected by prompting Gemini to strictly adhere to progressive disclosure.
