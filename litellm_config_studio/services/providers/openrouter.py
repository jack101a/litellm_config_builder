from __future__ import annotations

from litellm_config_studio.models import ProviderInfo, ProviderModel, TestRequest, ModelCapability
from litellm_config_studio.services.providers.base import ProviderAdapter
from litellm_config_studio.services.providers.openai_compatible import OpenAICompatibleAdapter


class OpenRouterAdapter(ProviderAdapter):
    provider_id = "openrouter"
    display_name = "OpenRouter"
    default_env_prefix = "OPENROUTER_API_KEY"
    default_api_base = "https://openrouter.ai/api/v1"

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            provider_id=self.provider_id,
            display_name=self.display_name,
            model_fetch="Full via OpenRouter /models",
            rich_metadata="Good: pricing, context, architecture, supported params",
            thinking_mode="Model/provider-specific metadata",
            wildcard="Useful as openrouter/* but explicit aliases are better for WebUI",
            default_env_prefix=self.default_env_prefix,
            default_api_base=self.default_api_base,
            notes="OpenRouter's model endpoint is one of the richest metadata sources.",
        )

    async def fetch_models(self, api_key: str | None = None, base_url: str | None = None) -> list[ProviderModel]:
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        data = await self.get_json("https://openrouter.ai/api/v1/models", headers=headers)
        models: list[ProviderModel] = []
        for item in data.get("data", []):
            model_id = item.get("id")
            if not model_id:
                continue
            supported = set(item.get("supported_parameters") or [])
            caps = ModelCapability(
                function_calling="tools" in supported or "tool_choice" in supported,
                structured_output="response_format" in supported,
                vision="image" in str(item.get("architecture", {})).lower() or "multimodal" in str(item).lower(),
                streaming=True,
                reasoning="reasoning" in supported or "include_reasoning" in supported,
            )
            models.append(
                ProviderModel(
                    provider_id=self.provider_id,
                    model_id=model_id,
                    display_name=item.get("name"),
                    litellm_model=f"openrouter/{model_id}",
                    api_base=self.default_api_base,
                    description=item.get("description"),
                    context_window=item.get("context_length"),
                    max_output_tokens=(item.get("top_provider") or {}).get("max_completion_tokens"),
                    pricing=item.get("pricing"),
                    capabilities=caps,
                    sources={
                        "model_id": "provider_api",
                        "context_window": "provider_api",
                        "pricing": "provider_api",
                        "capabilities": "provider_api",
                    },
                    raw=item,
                )
            )
        return models

    async def test_chat(self, request: TestRequest) -> dict:
        adapter = OpenAICompatibleAdapter(
            provider_id=self.provider_id,
            display_name=self.display_name,
            default_api_base=self.default_api_base,
            default_env_prefix=self.default_env_prefix,
        )
        model = request.model or "openai/gpt-4o-mini"
        if model.startswith("openrouter/"):
            model = model.split("openrouter/", 1)[-1]
        request.model = model
        return await adapter.test_chat(request)
