from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


SourceLabel = Literal[
    "provider_api",
    "provider_webpage",
    "litellm_known_map",
    "built_in_preset",
    "user_override",
    "live_test",
    "cache",
    "unknown",
]


class ApiKeyPlan(BaseModel):
    provider_id: str
    count: int = Field(default=1, ge=0, le=200)
    env_prefix: str
    pasted_keys: list[str] = Field(default_factory=list)

    def env_names(self) -> list[str]:
        clean_prefix = (self.env_prefix or "API_KEY").strip().upper().replace(" ", "_")
        if self.count <= 1:
            return [clean_prefix]
        return [f"{clean_prefix}_{i}" for i in range(1, self.count + 1)]


class ExtraBodyPreset(BaseModel):
    name: str
    label: str
    body: dict[str, Any]
    source: SourceLabel = "unknown"
    notes: str | None = None


class ModelCapability(BaseModel):
    chat: bool | None = True
    responses: bool | None = None
    reasoning: bool | None = None
    thinking: bool | None = None
    function_calling: bool | None = None
    structured_output: bool | None = None
    vision: bool | None = None
    streaming: bool | None = None
    embeddings: bool | None = None
    audio: bool | None = None
    image_generation: bool | None = None


class ProviderModel(BaseModel):
    provider_id: str
    model_id: str
    display_name: str | None = None
    litellm_model: str | None = None
    api_base: str | None = None
    description: str | None = None
    context_window: int | None = None
    max_output_tokens: int | None = None
    temperature: float | None = None
    top_p: float | None = None
    pricing: dict[str, Any] | None = None
    capabilities: ModelCapability = Field(default_factory=ModelCapability)
    extra_body_presets: list[ExtraBodyPreset] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    sources: dict[str, SourceLabel] = Field(default_factory=dict)
    raw: dict[str, Any] = Field(default_factory=dict)


class SelectedModel(BaseModel):
    provider_id: str
    model_id: str
    alias: str
    litellm_model: str
    api_base: str | None = None
    env_names: list[str]
    max_tokens: int | None = None
    temperature: float | None = None
    top_p: float | None = None
    rpm: int | None = None
    tpm: int | None = None
    extra_body: dict[str, Any] | None = None
    mode: Literal["explicit", "wildcard"] = "explicit"
    tags: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class WildcardRoute(BaseModel):
    provider_id: str
    alias: str
    litellm_model: str
    api_base: str | None = None
    env_names: list[str]
    rpm: int | None = None
    tpm: int | None = None
    notes: list[str] = Field(default_factory=list)


class FallbackGroup(BaseModel):
    primary: str
    fallbacks: list[str] = Field(default_factory=list)


class RoutingSettings(BaseModel):
    routing_strategy: str = "simple-shuffle"
    num_retries: int = Field(default=2, ge=0, le=20)
    cooldown_time: int = Field(default=60, ge=0, le=3600)
    timeout: int | None = Field(default=None, ge=1, le=3600)
    max_parallel_requests: int | None = Field(default=None, ge=1, le=10000)
    background_health_checks: bool = False
    health_check_interval: int = Field(default=60, ge=10, le=3600)
    enable_health_check_routing: bool = False
    allowed_fails: int | None = Field(default=None, ge=1, le=100)
    prompt_cache_mode: Literal["off", "advisory", "sticky"] = "off"


class ProviderRouting(BaseModel):
    provider_id: str
    rpm: int | None = None
    tpm: int | None = None


class GenerationRequest(BaseModel):
    selected_models: list[SelectedModel]
    wildcard_routes: list[WildcardRoute] = Field(default_factory=list)
    fallback_groups: list[FallbackGroup] = Field(default_factory=list)
    routing: RoutingSettings = Field(default_factory=RoutingSettings)
    provider_routing: list[ProviderRouting] = Field(default_factory=list)
    litellm_master_key_env: str = "LITELLM_MASTER_KEY"
    include_docker_compose: bool = True
    include_import_script: bool = True
    include_models_report: bool = True
    generation_mode: Literal["explicit", "wildcard", "hybrid"] = "explicit"


class TestRequest(BaseModel):
    provider_id: str
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None
    messages: list[dict[str, str]] = Field(default_factory=lambda: [{"role": "user", "content": "Reply with only OK."}])
    max_tokens: int = 10
    extra_body: dict[str, Any] | None = None


class BulkKeyTestRequest(BaseModel):
    provider_id: str
    api_keys: list[str]
    base_url: str | None = None


class ProviderInfo(BaseModel):
    provider_id: str
    display_name: str
    model_fetch: str
    rich_metadata: str
    thinking_mode: str
    wildcard: str
    default_env_prefix: str
    default_api_base: str | None = None
    notes: str | None = None
    capability_notes: list[str] = Field(default_factory=list)
