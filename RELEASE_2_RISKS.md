# GameMind: Release 2 Risk Management & Mitigations

This document analyzes the primary technical and product risks associated with introducing the **Gameplay Content Layer (Release 2)**, detailing concrete mitigation strategies for each.

---

## 1. Technical Risks

### Risk A: Gemini API Cost Growth
* **Description:** As players converse with NPCs, prompt weights grow rapidly (due to RAG lore injection and history summaries), resulting in high token usage and API costs.
* **Mitigation Strategy:**
  1. **Strict Context Capping:** Limit similarity queries to the top 3 matches (`limit=3`) rather than retrieving large sets.
  2. **Short-Term Memory Window:** Restrict the active conversation history window in the prompt to the last 5 turns.
  3. **Summarization:** Offload older turns to long-term memory summaries instead of feeding raw chats back into Gemini.

### Risk B: Context Window Growth
* **Description:** Ingesting multiple NPC guides, relationships scores, active quests, and short-term chat logs overflows context sizes, causing latency spikes and potential generation failures.
* **Mitigation Strategy:**
  1. **Pydantic System Prompts:** Standardize inputs using compact JSON tags instead of wordy descriptions.
  2. **Selective Injection:** Inject memory summaries only if semantic searches indicate relevance to the player's message (using a thresholds filter, e.g. similarity >= 65%).

### Risk C: Memory Scaling & Latency
* **Description:** Loading database records for NPC profiles, relationships, and history logs on every `/dialogue` POST request increases latency.
* **Mitigation Strategy:**
  1. **Caching:** Cache the static `npc_profiles` parameters (personality summaries, styles) in memory (e.g. FastAPI app state or redis) to avoid repetitive Postgres calls.
  2. **Indexed Foreign Keys:** Ensure database indexes are set up on foreign keys like `memories.npc_id` and `relationships.npc_id`.

### Risk D: Prompt Drift
* **Description:** As more prompt variables (location, reputation, quests) are concatenated, the NPC may ignore its dialogue style guidelines, speaking out of character.
* **Mitigation Strategy:**
  1. **Structured Formatting:** Enforce dialogue guidelines inside a system prompt wrapper block separate from variable contexts.
  2. **Gemini System Instructions:** Pass style instructions strictly in the `system_instruction` parameter of the Gemini API Client, separating it from user variables.

### Risk E: Retrieval Failures (Empty RAG Context)
* **Description:** If a query returns no matches in ChromaDB, the Dialogue Engine might default to standard knowledge and hallucinate world facts.
* **Mitigation Strategy:**
  1. **Default Fallbacks:** If RAG returns no matches (max similarity < 55%), fallback to a generic system prompt stating the NPC is unaware of the topic.
  2. **Grounding Constraints:** Instruct the model: *"If no background text is provided, state that you do not have this information."*

---

## 2. Product Risks

### Risk F: NPC Inconsistency
* **Description:** The NPC references events that contradict the world history document or active world events (e.g. claiming King Arven is alive when the lore states he died).
* **Mitigation Strategy:**
  1. **World Event State Injection:** Inject active world events (e.g. `siege_active: true`) directly into the NPC's prompt environment.
  2. **Structured Outputs:** Force Gemini to parse responses through a validation schema that separates dialogue text from reasoning blocks.

### Risk G: Repetitive Quests
* **Description:** The Quest Generator generates similar quest structures repeatedly (e.g., "Retrieve the Sky-iron logs" then "Retrieve the Sky-iron valve"), making the gameplay feel artificial.
* **Mitigation Strategy:**
  1. **Objective Diversity Check:** Force the Quest Generator to select from a variety of objective templates (e.g. kill, retrieve, speak).
  2. **Seed Injection:** Inject the titles of the last 3 generated quests as negative constraints (e.g. *"Do not generate quests resembling: [Titles]"*).

### Risk H: Hint Spoilers
* **Description:** Level 1 hints (intended to be subtle) disclose the exact coordinates or puzzle resolution immediately.
* **Mitigation Strategy:**
  1. **Distinct Prompting Tiers:** Instruct the model using strict level guidelines:
     - *Level 1 (Subtle):* Describe only environment features or rumors.
     - *Level 2 (Moderate):* Point to a specific zone or NPC.
     - *Level 3 (Direct):* Give exact instructions or solutions.

### Risk I: Hallucinated Lore
* **Description:** Generating NPC dialogue or quests that introduce locations or factions not found in the game lore database.
* **Mitigation Strategy:**
  1. **RAG-Bound Generation:** Add strict system constraints: *"You must only use locations, factions, and characters present in the retrieved context. Do not invent new names."*
  2. **Post-Validation:** The Validation Agent in Release 3 will scan generated content against ChromaDB before returning the payload.
