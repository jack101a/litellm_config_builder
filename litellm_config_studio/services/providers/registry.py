from __future__ import annotations

from litellm_config_studio.services.providers.base import ProviderAdapter
from litellm_config_studio.services.providers.gemini import GeminiAdapter
from litellm_config_studio.services.providers.groq import GroqAdapter
from litellm_config_studio.services.providers.nvidia import NvidiaAdapter
from litellm_config_studio.services.providers.openai_compatible import OpenAICompatibleAdapter
from litellm_config_studio.services.providers.openrouter import OpenRouterAdapter
from litellm_config_studio.services.providers.static import StaticProviderAdapter


def build_registry() -> dict[str, ProviderAdapter]:
    adapters: list[ProviderAdapter] = [
        NvidiaAdapter(),
        OpenRouterAdapter(),
        GeminiAdapter(),
        GroqAdapter(),
        OpenAICompatibleAdapter(provider_id="openai", display_name="OpenAI / ChatGPT", default_api_base="https://api.openai.com/v1", default_env_prefix="OPENAI_API_KEY"),
        OpenAICompatibleAdapter(provider_id="custom_openai", display_name="Custom OpenAI-compatible", default_api_base="http://localhost:8000/v1", default_env_prefix="CUSTOM_OPENAI_API_KEY"),
        StaticProviderAdapter("anthropic", "Anthropic / Claude", "ANTHROPIC_API_KEY", "Claude adapter is planned; explicit LiteLLM config generation already works."),
        StaticProviderAdapter("mistral", "Mistral", "MISTRAL_API_KEY"),
        StaticProviderAdapter("deepseek", "DeepSeek", "DEEPSEEK_API_KEY"),
        StaticProviderAdapter("xai", "xAI", "XAI_API_KEY"),
        StaticProviderAdapter("together", "Together AI", "TOGETHER_API_KEY"),
        StaticProviderAdapter("fireworks", "Fireworks AI", "FIREWORKS_API_KEY"),
        StaticProviderAdapter("cohere", "Cohere", "COHERE_API_KEY"),
        StaticProviderAdapter("perplexity", "Perplexity", "PERPLEXITY_API_KEY"),
        OpenAICompatibleAdapter(provider_id="ollama", display_name="Ollama OpenAI mode", default_api_base="http://localhost:11434/v1", default_env_prefix="OLLAMA_API_KEY"),
        OpenAICompatibleAdapter(provider_id="lmstudio", display_name="LM Studio", default_api_base="http://localhost:1234/v1", default_env_prefix="LMSTUDIO_API_KEY"),
        OpenAICompatibleAdapter(provider_id="vllm", display_name="vLLM", default_api_base="http://localhost:8000/v1", default_env_prefix="VLLM_API_KEY"),
    ]
    return {a.provider_id: a for a in adapters}


REGISTRY = build_registry()
