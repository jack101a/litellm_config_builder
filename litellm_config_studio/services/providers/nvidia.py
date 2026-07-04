from __future__ import annotations

from litellm_config_studio.models import ProviderInfo, ProviderModel, TestRequest
from litellm_config_studio.services.providers.openai_compatible import OpenAICompatibleAdapter
from litellm_config_studio.services.enrichment.nvidia_build import NvidiaBuildEnricher


class NvidiaAdapter(OpenAICompatibleAdapter):
    provider_id = "nvidia"
    display_name = "NVIDIA NIM"
    default_env_prefix = "NVIDIA_KEY"
    default_api_base = "https://integrate.api.nvidia.com/v1"

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            provider_id=self.provider_id,
            display_name=self.display_name,
            model_fetch="Partial via OpenAI-compatible /models; enriched via build.nvidia.com pages",
            rich_metadata="Good after webpage enrichment, but model-specific",
            thinking_mode="Model-specific extra_body/chat_template_kwargs extraction",
            wildcard="Possible for routing, but explicit aliases are better for WebUI and thinking presets",
            default_env_prefix=self.default_env_prefix,
            default_api_base=self.default_api_base,
            notes="Hosted NVIDIA endpoint is OpenAI-compatible. Rich details are scraped/enriched from build.nvidia.com/{model_id}.",
        )

    async def fetch_models(self, api_key: str | None = None, base_url: str | None = None) -> list[ProviderModel]:
        models = await super().fetch_models(api_key=api_key, base_url=base_url or self.default_api_base)
        for model in models:
            model.provider_id = self.provider_id
            model.api_base = base_url or self.default_api_base
            model.litellm_model = f"openai/{model.model_id}"
            model.sources["api_base"] = "built_in_preset"
        return models

    async def enrich_model(self, model: ProviderModel) -> ProviderModel:
        return await NvidiaBuildEnricher().enrich(model)

    async def test_chat(self, request: TestRequest) -> dict:
        request.base_url = request.base_url or self.default_api_base
        return await super().test_chat(request)
