import time
import asyncio
import logging
from google import genai
from google.genai import types
from app.services.llm.base import LLMProvider

logger = logging.getLogger(__name__)

class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str):
        self.api_key = api_key
        # Enforce a 5-second timeout via http_options
        self.client = genai.Client(
            api_key=api_key, 
            http_options={"timeout": 5.0}
        )

    async def generate_response(
        self, 
        system_prompt: str, 
        user_prompt: str, 
        max_output_tokens: int,
        model_name: str
    ) -> tuple[str, dict]:
        safety_settings = [
            types.SafetySetting(
                category="HARM_CATEGORY_HARASSMENT",
                threshold="BLOCK_MEDIUM_AND_ABOVE",
            ),
            types.SafetySetting(
                category="HARM_CATEGORY_HATE_SPEECH",
                threshold="BLOCK_MEDIUM_AND_ABOVE",
            ),
            types.SafetySetting(
                category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                threshold="BLOCK_MEDIUM_AND_ABOVE",
            ),
            types.SafetySetting(
                category="HARM_CATEGORY_DANGEROUS_CONTENT",
                threshold="BLOCK_MEDIUM_AND_ABOVE",
            ),
        ]

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=max_output_tokens,
            safety_settings=safety_settings,
            temperature=0.7,
        )

        attempts = 0
        max_attempts = 2  # Max 1 retry (2 attempts total)
        last_error = None
        start_time = time.time()

        while attempts < max_attempts:
            try:
                # Run the synchronous generate_content call in a thread pool
                response = await asyncio.to_thread(
                    self.client.models.generate_content,
                    model=model_name,
                    contents=user_prompt,
                    config=config
                )
                latency_ms = int((time.time() - start_time) * 1000)

                text_out = ""
                safety_blocked = False
                safety_ratings_data = []

                if response.candidates:
                    candidate = response.candidates[0]
                    if candidate.finish_reason == "SAFETY":
                        safety_blocked = True
                        text_out = "[The keeper falls silent, refusing to discuss these dark events.]"
                    else:
                        text_out = response.text or ""

                    if candidate.safety_ratings:
                        for rating in candidate.safety_ratings:
                            safety_ratings_data.append({
                                "category": rating.category,
                                "probability": rating.probability,
                                "blocked": rating.blocked
                            })
                else:
                    text_out = "[The speaker remains silent, lost in thought.]"

                # Extract token usage
                usage = response.usage_metadata
                input_tokens = usage.prompt_token_count if usage else 0
                output_tokens = usage.candidates_token_count if usage else 0

                # Pricing calculation logic (in USD per 1M tokens)
                is_pro = "pro" in model_name.lower()
                is_1_5 = "1.5" in model_name

                if is_pro:
                    in_rate = 7.00 / 1_000_000
                    out_rate = 21.00 / 1_000_000
                elif is_1_5:
                    in_rate = 0.30 / 1_000_000
                    out_rate = 2.50 / 1_000_000
                else:  # Defaults to 3.5 Flash rates
                    in_rate = 1.50 / 1_000_000
                    out_rate = 9.00 / 1_000_000

                estimated_cost = (input_tokens * in_rate) + (output_tokens * out_rate)

                telemetry = {
                    "latency_ms": latency_ms,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "estimated_cost_usd": float(estimated_cost),
                    "safety_ratings": safety_ratings_data,
                    "safety_blocked": safety_blocked
                }

                return text_out, telemetry

            except Exception as e:
                attempts += 1
                last_error = e
                logger.warning(f"Gemini API attempt {attempts} failed with error: {str(e)}")
                if attempts < max_attempts:
                    await asyncio.sleep(1.5)  # Wait 1.5s before the single retry
                else:
                    break

        # Both attempts failed
        latency_ms = int((time.time() - start_time) * 1000)
        telemetry = {
            "latency_ms": latency_ms,
            "input_tokens": 0,
            "output_tokens": 0,
            "estimated_cost_usd": 0.0,
            "safety_ratings": [],
            "error": str(last_error)
        }
        return f"[The speaker remains quiet, looking away lost in thought. (Error: {str(last_error)})]", telemetry
