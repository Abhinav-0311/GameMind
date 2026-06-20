import logging
from google import genai
from app.config import settings

logger = logging.getLogger(__name__)

class GeminiService:
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.client = None
        if self.api_key and self.api_key != "your_gemini_api_key_here":
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.error(f"Failed to initialize Gemini Client: {e}")
        else:
            logger.warning("GEMINI_API_KEY is not set or using default placeholder. Gemini services will be unavailable.")

    def is_available(self) -> bool:
        return self.client is not None

    def generate_embedding(self, text: str) -> list[float]:
        """Generate embedding for a single text using text-embedding-004."""
        if not self.client:
            raise ValueError("Gemini API Client is not configured. Please check your GEMINI_API_KEY.")
        
        try:
            response = self.client.models.embed_content(
                model="text-embedding-004",
                contents=text
            )
            if response.embeddings and len(response.embeddings) > 0:
                return response.embeddings[0].values
            raise ValueError("Empty embedding response received.")
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise e

    def generate_batch_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts in a single batch call."""
        if not self.client:
            raise ValueError("Gemini API Client is not configured. Please check your GEMINI_API_KEY.")
        if not texts:
            return []
        
        try:
            response = self.client.models.embed_content(
                model="text-embedding-004",
                contents=texts
            )
            if response.embeddings:
                return [emb.values for emb in response.embeddings]
            raise ValueError("Empty batch embedding response received.")
        except Exception as e:
            logger.error(f"Error generating batch embeddings: {e}")
            raise e
