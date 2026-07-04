from __future__ import annotations

from typing import Any

from litellm_config_studio.models import ProviderInfo, ProviderModel, TestRequest
from litellm_config_studio.services.providers.base import ProviderAdapter


class OpenAICompatibleAdapter(ProviderAdapter):
    provider_id = "custom_openai"
    display_name = "Custom OpenAI-compatible"
    default_env_prefix = "CUSTOM_OPENAI_API_KEY"
    default_api_base = "http://localhost:8000/v1"

    def __init__(self, provider_id: str | None = None, display_name: str | None = None, default_api_base: str | None = None, default_env_prefix: str | None = None):
        if provider_id:
            self.provider_id = provider_id
        if display_name:
            self.display_name = display_name
        if default_api_base:
            self.default_api_base = default_api_base
        if default_env_prefix:
            self.default_env_prefix = default_env_prefix

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            provider_id=self.provider_id,
            display_name=self.display_name,
            model_fetch="Full/Partial via /v1/models",
            rich_metadata="Usually partial",
            thinking_mode="Provider-specific",
            wildcard="Possible with openai/* or explicit aliases",
            default_env_prefix=self.default_env_prefix,
            default_api_base=self.default_api_base,
            notes="Works with vLLM, LM Studio, Ollama OpenAI mode, NVIDIA hosted endpoint, and many OpenAI-compatible gateways.",
        )

    async def fetch_models(self, api_key: str | None = None, base_url: str | None = None) -> list[ProviderModel]:
        base = (base_url or self.default_api_base or "").rstrip("/")
        if not base:
            raise ValueError("Base URL is required for custom OpenAI-compatible model fetch.")
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        data = await self.get_json(f"{base}/models", headers=headers)
        items = data.get("data", data if isinstance(data, list) else [])
        models: list[ProviderModel] = []
        for item in items:
            if isinstance(item, str):
                model_id = item
                raw: dict[str, Any] = {"id": item}
            else:
                model_id = item.get("id") or item.get("name") or item.get("model")
                raw = item
            if not model_id:
                continue
            models.append(
                ProviderModel(
                    provider_id=self.provider_id,
                    model_id=model_id,
                    display_name=raw.get("name") if isinstance(raw, dict) else None,
                    litellm_model=f"openai/{model_id}",
                    api_base=base,
                    raw=raw if isinstance(raw, dict) else {"id": model_id},
                    sources={"model_id": "provider_api"},
                )
            )
        return models

    async def test_chat(self, request: TestRequest) -> dict[str, Any]:
        base = (request.base_url or self.default_api_base or "").rstrip("/")
        if not base:
            return {"ok": False, "message": "Base URL is required."}
        payload: dict[str, Any] = {
            "model": request.model,
            "messages": request.messages,
            "max_tokens": request.max_tokens,
        }
        if request.extra_body:
            payload.update(request.extra_body)
        headers = {"Content-Type": "application/json"}
        if request.api_key:
            headers["Authorization"] = f"Bearer {request.api_key}"
        try:
            data = await self.post_json(f"{base}/chat/completions", payload=payload, headers=headers)
            content = None
            if isinstance(data, dict):
                choices = data.get("choices") or []
                if choices:
                    msg = choices[0].get("message") or {}
                    content = msg.get("content")
            return {"ok": True, "message": "Chat test succeeded.", "content": content, "raw": data}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "message": str(exc)}
