import re
from app.services.llm.base import LLMProvider

class MockLLMProvider(LLMProvider):
    provider_name = "local_mock"

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

        # 2. Extract lore snippets from the prompt.
        # Check for LORE CONTEXT: in system prompt
        lore_snippets = []
        lore_section = re.search(
            r"(?:LORE CONTEXT|World Lore Context)\]?:?\s*\n(.*?)(?=\n+\[[A-Z_\s]+\]|$)", 
            system_prompt, 
            re.IGNORECASE | re.DOTALL
        )
        if lore_section:
            # Split by line and grab lines that are not bullet list markers or section headers
            lines = [s.strip() for s in lore_section.group(1).split("\n") if s.strip()]
            for line in lines:
                # Exclude placeholder notices like "No relevant lore chunks provided"
                if "No relevant lore chunks" in line:
                    continue
                # Strip leading dashes or indices if they are formatted
                cleaned = re.sub(r"^[-*#\d\.\s]+", "", line).strip()
                if len(cleaned) > 10:
                    lore_snippets.append(cleaned)
            lore_snippets = lore_snippets[:2]

        # 3. Format realistic mock response
        mock_response = f"[{npc_name} of the {faction}]\n"
        if lore_snippets:
            mock_response += "Based on the supplied lore context, I know:\n"
            for snippet in lore_snippets:
                mock_response += f"- {snippet}\n"
        else:
            mock_response += "No lore context was provided for this query.\n"

        mock_response += f"\nYou asked:\n\"{user_prompt}\"\n\n(Local demo response generated using {model_name}.)"
        
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
