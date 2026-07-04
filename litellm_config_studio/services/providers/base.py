from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
import httpx

from litellm_config_studio.models import ProviderInfo, ProviderModel, TestRequest


class ProviderError(RuntimeError):
    pass


class ProviderAdapter(ABC):
    provider_id: str
    display_name: str
    default_env_prefix: str
    default_api_base: str | None = None

    @abstractmethod
    def info(self) -> ProviderInfo:
        raise NotImplementedError

    async def fetch_models(self, api_key: str | None = None, base_url: str | None = None) -> list[ProviderModel]:
        return []

    async def enrich_model(self, model: ProviderModel) -> ProviderModel:
        return model

    async def test_key(self, api_key: str | None = None, base_url: str | None = None) -> dict[str, Any]:
        try:
            models = await self.fetch_models(api_key=api_key, base_url=base_url)
            return {"ok": True, "message": f"Fetched {len(models)} models.", "count": len(models)}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "message": str(exc), "count": 0}

    async def test_chat(self, request: TestRequest) -> dict[str, Any]:
        raise ProviderError(f"Chat test is not implemented for {self.provider_id}")

    @staticmethod
    async def get_json(url: str, headers: dict[str, str] | None = None, timeout: float = 20.0) -> Any:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()

    @staticmethod
    async def post_json(url: str, payload: dict[str, Any], headers: dict[str, str] | None = None, timeout: float = 60.0) -> Any:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
