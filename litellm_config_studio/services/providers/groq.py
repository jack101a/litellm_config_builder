from __future__ import annotations

from litellm_config_studio.models import ProviderInfo, TestRequest
from litellm_config_studio.services.providers.openai_compatible import OpenAICompatibleAdapter


class GroqAdapter(OpenAICompatibleAdapter):
    provider_id = "groq"
    display_name = "Groq"
    default_env_prefix = "GROQ_API_KEY"
    default_api_base = "https://api.groq.com/openai/v1"

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            provider_id=self.provider_id,
            display_name=self.display_name,
            model_fetch="Full/Partial via OpenAI-compatible /models",
            rich_metadata="Partial",
            thinking_mode="Model-specific",
            wildcard="Possible but explicit aliases recommended",
            default_env_prefix=self.default_env_prefix,
            default_api_base=self.default_api_base,
            notes="Groq is OpenAI-compatible but not every OpenAI parameter is supported.",
        )

    async def test_chat(self, request: TestRequest) -> dict:
        request.base_url = request.base_url or self.default_api_base
        return await super().test_chat(request)
