import re
from app.services.llm.base import LLMProvider

class MockLLMProvider(LLMProvider):
    provider_name = "local_mock"

    def _clean_lore_text(self, value: str) -> str:
        value = re.sub(r"Document:\s*[^\n]+", " ", value)
        value = re.sub(r"Content:\s*", " ", value)
        value = re.sub(r"#+\s*", " ", value)
        value = re.sub(r"\*\*(.*?)\*\*", r"\1", value)
        value = re.sub(r"\s+", " ", value)
        return value.strip()

    def _extract_source_label(self, value: str) -> str:
        source_match = re.search(r"Document:\s*([^\n]+)", value)
        return source_match.group(1).strip() if source_match else "uploaded lore"

    def _select_relevant_sentence(self, lore_text: str, user_prompt: str) -> str:
        sentences = [
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?])\s+", lore_text)
            if len(sentence.strip()) > 24
        ]
        if not sentences:
            return lore_text[:260].strip()

        prompt_terms = {
            term.lower()
            for term in re.findall(r"[A-Za-z][A-Za-z'-]{3,}", user_prompt)
            if term.lower() not in {"what", "when", "where", "tell", "about", "who", "does", "with"}
        }
        for sentence in sentences:
            lowered = sentence.lower()
            if any(re.search(rf"\b{re.escape(term)}\b", lowered) for term in prompt_terms):
                return sentence

        return sentences[0]

    async def generate_response(
        self, 
        system_prompt: str, 
        user_prompt: str, 
        max_output_tokens: int,
        model_name: str
    ) -> tuple[str, dict]:
        # 1. Parse NPC Name and Faction from system_prompt
        name_match = re.search(r"Character Name:\s*([^\n]+)", system_prompt)
        faction_match = re.search(r"Faction Alignment:\s*([^\n]+)", system_prompt)
        
        npc_name = name_match.group(1).strip() if name_match else "the NPC"
        faction = faction_match.group(1).strip() if faction_match else "UNALIGNED"

        # 2. Extract lore from the prompt.
        lore_section = re.search(
            r"(?:LORE CONTEXT|World Lore Context)\]?:?\s*\n(.*?)(?=\n+\[[A-Z_\s]+\]|$)", 
            system_prompt, 
            re.IGNORECASE | re.DOTALL
        )
        source_label = "uploaded lore"
        selected_lore = ""
        if lore_section:
            raw_lore = lore_section.group(1)
            if "No relevant lore chunks" not in raw_lore:
                source_label = self._extract_source_label(raw_lore)
                selected_lore = self._select_relevant_sentence(
                    self._clean_lore_text(raw_lore),
                    user_prompt
                )

        # 3. Format a presentable local response rather than exposing prompt internals.
        if selected_lore:
            mock_response = (
                f"{npc_name}: {selected_lore}\n\n"
                f"That is the account preserved in {source_label}. "
                "Treat it as grounded lore, not a generated invention."
            )
        else:
            mock_response = (
                f"{npc_name}: I do not have enough grounded lore to answer that confidently yet. "
                "Add more source material or ask about a documented character, faction, place, or quest."
            )
        
        telemetry = {
            "latency_ms": 100,
            "input_tokens": len(system_prompt + user_prompt) // 4,
            "output_tokens": len(mock_response) // 4,
            "estimated_cost_usd": 0.0,
            "safety_ratings": [
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "probability": "NEGLIGIBLE"
                }
            ]
        }
        return mock_response, telemetry
