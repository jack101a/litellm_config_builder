from __future__ import annotations

from litellm_config_studio.models import ProviderInfo, ProviderModel, TestRequest, ModelCapability
from litellm_config_studio.services.providers.base import ProviderAdapter


class GeminiAdapter(ProviderAdapter):
    provider_id = "gemini"
    display_name = "Google Gemini"
    default_env_prefix = "GEMINI_API_KEY"
    default_api_base = "https://generativelanguage.googleapis.com/v1beta"

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            provider_id=self.provider_id,
            display_name=self.display_name,
            model_fetch="Full/Partial via Gemini models API",
            rich_metadata="Good: token limits and supported methods where returned",
            thinking_mode="Model-specific",
            wildcard="Good for LiteLLM model discovery where supported",
            default_env_prefix=self.default_env_prefix,
            default_api_base=self.default_api_base,
            notes="Gemini model IDs usually become litellm model names like gemini/gemini-2.5-flash.",
        )

    async def fetch_models(self, api_key: str | None = None, base_url: str | None = None) -> list[ProviderModel]:
        if not api_key:
            raise ValueError("Gemini API key is required to fetch models.")
        base = (base_url or self.default_api_base).rstrip("/")
        data = await self.get_json(f"{base}/models?key={api_key}")
        models: list[ProviderModel] = []
        for item in data.get("models", []):
            raw_name = item.get("name", "")
            model_id = raw_name.split("models/", 1)[-1] if raw_name else item.get("displayName")
            if not model_id:
                continue
            methods = set(item.get("supportedGenerationMethods") or [])
            models.append(
                ProviderModel(
                    provider_id=self.provider_id,
                    model_id=model_id,
                    display_name=item.get("displayName") or model_id,
                    litellm_model=f"gemini/{model_id}",
                    description=item.get("description"),
                    context_window=item.get("inputTokenLimit"),
                    max_output_tokens=item.get("outputTokenLimit"),
                    temperature=item.get("temperature"),
                    top_p=item.get("topP"),
                    capabilities=ModelCapability(streaming="streamGenerateContent" in methods),
                    sources={
                        "model_id": "provider_api",
                        "context_window": "provider_api",
                        "max_output_tokens": "provider_api",
                        "supported_methods": "provider_api",
                    },
                    raw=item,
                )
            )
        return models

    async def test_chat(self, request: TestRequest) -> dict:
        # Gemini's native API is not OpenAI-compatible. For final LiteLLM testing, use LiteLLM proxy.
        # This direct smoke test calls generateContent in the simplest possible way.
        if not request.api_key:
            return {"ok": False, "message": "Gemini API key is required."}
        model = request.model or "gemini-2.5-flash"
        base = (request.base_url or self.default_api_base).rstrip("/")
        text = request.messages[-1].get("content", "Reply with only OK.") if request.messages else "Reply with only OK."
        url = f"{base}/models/{model}:generateContent?key={request.api_key}"
        payload = {"contents": [{"parts": [{"text": text}]}], "generationConfig": {"maxOutputTokens": request.max_tokens}}
        try:
            data = await self.post_json(url, payload=payload)
            content = None
            try:
                content = data["candidates"][0]["content"]["parts"][0].get("text")
            except Exception:  # noqa: BLE001
                content = None
            if not content:
                return {"ok": False, "message": "Gemini call succeeded but no text content was returned (possibly blocked by safety filters or empty).", "raw": data}
            return {"ok": True, "message": "Gemini test succeeded.", "content": content, "raw": data}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "message": str(exc)}
