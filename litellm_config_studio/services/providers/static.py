from __future__ import annotations

from litellm_config_studio.models import ProviderInfo
from litellm_config_studio.services.providers.base import ProviderAdapter


class StaticProviderAdapter(ProviderAdapter):
    def __init__(self, provider_id: str, display_name: str, env_prefix: str, notes: str = "Manual/partial metadata in MVP.", capability_notes: list[str] | None = None):
        self.provider_id = provider_id
        self.display_name = display_name
        self.default_env_prefix = env_prefix
        self.default_api_base = None
        self.notes = notes
        self.capability_notes = capability_notes or []

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            provider_id=self.provider_id,
            display_name=self.display_name,
            model_fetch="Manual/adapter pending",
            rich_metadata="Manual/adapter pending",
            thinking_mode="Unknown/model-specific",
            wildcard="Provider-specific",
            default_env_prefix=self.default_env_prefix,
            default_api_base=self.default_api_base,
            notes=self.notes,
            capability_notes=self.capability_notes,
        )
