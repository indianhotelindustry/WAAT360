from src.ai.base import AIProvider
from src.ai.gemini_provider import GeminiProvider


def get_ai_provider(provider_name: str = "gemini") -> AIProvider:
    """
    Factory function to instantiate the configured AI Provider.
    Defaults to GeminiProvider.
    """
    if provider_name.lower() in ("gemini", "google"):
        return GeminiProvider()
    return GeminiProvider()
