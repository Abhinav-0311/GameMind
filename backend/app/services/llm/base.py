from abc import ABC, abstractmethod

class LLMProvider(ABC):
    provider_name = "local"

    @abstractmethod
    async def generate_response(
        self, 
        system_prompt: str, 
        user_prompt: str, 
        max_output_tokens: int,
        model_name: str
    ) -> tuple[str, dict]:
        """
        Executes generative chat query.
        Returns:
            tuple[response_text, telemetry_dict]
        """
        pass
