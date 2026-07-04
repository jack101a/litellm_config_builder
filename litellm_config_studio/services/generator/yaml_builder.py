from __future__ import annotations

from typing import Any
import json
import textwrap
import yaml

from litellm_config_studio.models import GenerationRequest, SelectedModel, WildcardRoute


class NoAliasDumper(yaml.SafeDumper):
    def ignore_aliases(self, data):
        return True


def build_config_dict(req: GenerationRequest) -> dict[str, Any]:
    config: dict[str, Any] = {"model_list": []}

    for selected in req.selected_models:
        if not selected.env_names:
            config["model_list"].append(_deployment_entry(selected, None, req.provider_routing))
        else:
            for env_name in selected.env_names:
                config["model_list"].append(_deployment_entry(selected, env_name, req.provider_routing))

    for route in req.wildcard_routes:
        if not route.env_names:
            config["model_list"].append(_wildcard_entry(route, None, req.provider_routing))
        else:
            for env_name in route.env_names:
                config["model_list"].append(_wildcard_entry(route, env_name, req.provider_routing))

    router_settings: dict[str, Any] = {
        "routing_strategy": req.routing.routing_strategy,
        "num_retries": req.routing.num_retries,
        "cooldown_time": req.routing.cooldown_time,
    }
    if req.routing.timeout:
        router_settings["timeout"] = req.routing.timeout
    if req.routing.max_parallel_requests:
        router_settings["max_parallel_requests"] = req.routing.max_parallel_requests
    if req.routing.allowed_fails:
        router_settings["allowed_fails"] = req.routing.allowed_fails
    config["router_settings"] = router_settings

    litellm_settings: dict[str, Any] = {}
    if req.fallback_groups:
        fallbacks = []
        for group in req.fallback_groups:
            if group.primary and group.fallbacks:
                fallbacks.append({group.primary: [x for x in group.fallbacks if x]})
        if fallbacks:
            litellm_settings["fallbacks"] = fallbacks
    if req.routing.prompt_cache_mode != "off":
        litellm_settings.setdefault("success_callback", [])
        litellm_settings["prompt_cache_note"] = "Use prompt_cache_key in your application requests for cache-friendly routing."
    if litellm_settings:
        config["litellm_settings"] = litellm_settings

    if req.routing.background_health_checks or req.routing.enable_health_check_routing:
        config["general_settings"] = {
            "background_health_checks": req.routing.background_health_checks,
            "health_check_interval": req.routing.health_check_interval,
            "enable_health_check_routing": req.routing.enable_health_check_routing,
        }

    return config


def _deployment_entry(selected: SelectedModel, env_name: str | None, provider_routing: list[ProviderRouting]) -> dict[str, Any]:
    params: dict[str, Any] = {
        "model": selected.litellm_model,
    }
    if env_name:
        params["api_key"] = f"os.environ/{env_name}"
    if selected.api_base:
        params["api_base"] = selected.api_base
    if selected.max_tokens is not None:
        params["max_tokens"] = selected.max_tokens
    if selected.temperature is not None:
        params["temperature"] = selected.temperature
    if selected.top_p is not None:
        params["top_p"] = selected.top_p
    if selected.extra_body:
        params["extra_body"] = selected.extra_body

    entry: dict[str, Any] = {"model_name": selected.alias, "litellm_params": params}
    prov = next((p for p in provider_routing if p.provider_id == selected.provider_id), None)
    if prov:
        if prov.rpm is not None: entry["rpm"] = prov.rpm
        if prov.tpm is not None: entry["tpm"] = prov.tpm
    return entry


def _wildcard_entry(route: WildcardRoute, env_name: str | None, provider_routing: list[ProviderRouting]) -> dict[str, Any]:
    params: dict[str, Any] = {
        "model": route.litellm_model,
    }
    if env_name:
        params["api_key"] = f"os.environ/{env_name}"
    if route.api_base:
        params["api_base"] = route.api_base
    entry: dict[str, Any] = {"model_name": route.alias, "litellm_params": params}
    prov = next((p for p in provider_routing if p.provider_id == route.provider_id), None)
    if prov:
        if prov.rpm is not None: entry["rpm"] = prov.rpm
        if prov.tpm is not None: entry["tpm"] = prov.tpm
    return entry


def build_yaml(req: GenerationRequest) -> str:
    return yaml.dump(build_config_dict(req), Dumper=NoAliasDumper, sort_keys=False, allow_unicode=True, width=120)


def collect_env_names(req: GenerationRequest) -> list[str]:
    seen: list[str] = []
    for model in req.selected_models:
        for env in model.env_names:
            if env not in seen:
                seen.append(env)
    for route in req.wildcard_routes:
        for env in route.env_names:
            if env not in seen:
                seen.append(env)
    if req.litellm_master_key_env not in seen:
        seen.append(req.litellm_master_key_env)
    return seen


def build_env_example(req: GenerationRequest) -> str:
    lines: list[str] = [
        "# Generated by LiteLLM Config Studio",
        "# Put real values in .env, keep this .env.example safe to share.",
    ]
    for name in collect_env_names(req):
        if name == req.litellm_master_key_env:
            lines.append(f"{name}=sk-your-litellm-key")
        else:
            lines.append(f"{name}=")
    return "\n".join(lines) + "\n"


def build_test_curl(req: GenerationRequest) -> str:
    model_name = req.selected_models[0].alias if req.selected_models else (req.wildcard_routes[0].alias if req.wildcard_routes else "your-model-alias")
    return textwrap.dedent(
        f"""
        #!/usr/bin/env bash
        set -euo pipefail

        : "${{{req.litellm_master_key_env}:=sk-your-litellm-key}}"
        : "${{LITELLM_BASE_URL:=http://localhost:4000}}"

        curl "$LITELLM_BASE_URL/v1/models" \\
          -H "Authorization: Bearer ${req.litellm_master_key_env}"

        echo "\n--- chat smoke test ---"
        curl "$LITELLM_BASE_URL/v1/chat/completions" \\
          -H "Authorization: Bearer ${req.litellm_master_key_env}" \\
          -H "Content-Type: application/json" \\
          -d '{json.dumps({
              "model": model_name,
              "messages": [{"role": "user", "content": "Reply with only OK."}],
              "max_tokens": 10,
          }, indent=2)}'
        """
    ).strip() + "\n"


def build_docker_compose() -> str:
    return textwrap.dedent(
        """
        services:
          litellm:
            image: ghcr.io/berriai/litellm:main-latest
            ports:
              - "4000:4000"
            env_file:
              - .env
            volumes:
              - ./config.yaml:/app/config.yaml:ro
            command: ["--config", "/app/config.yaml", "--port", "4000", "--host", "0.0.0.0"]
        """
    ).strip() + "\n"


def build_import_script(req: GenerationRequest) -> str:
    payloads = build_config_dict(req).get("model_list", [])
    return textwrap.dedent(
        f"""
        #!/usr/bin/env python3
        import os
        import sys
        import requests

        BASE_URL = os.environ.get("LITELLM_BASE_URL", "http://localhost:4000")
        MASTER_KEY = os.environ.get("{req.litellm_master_key_env}")

        if not MASTER_KEY:
            print("Missing {req.litellm_master_key_env}", file=sys.stderr)
            sys.exit(1)

        MODELS = {json.dumps(payloads, indent=2)}

        headers = {{"Authorization": f"Bearer {{MASTER_KEY}}", "Content-Type": "application/json"}}
        for model in MODELS:
            response = requests.post(f"{{BASE_URL}}/model/new", json=model, headers=headers, timeout=30)
            if response.ok:
                print(f"✓ added {{model.get('model_name')}}")
            else:
                print(f"✗ failed {{model.get('model_name')}}: {{response.status_code}} {{response.text}}")
        """
    ).strip() + "\n"


def build_models_report(req: GenerationRequest) -> str:
    items = {
        "generation_mode": req.generation_mode,
        "selected_models": [m.model_dump() for m in req.selected_models],
        "wildcard_routes": [r.model_dump() for r in req.wildcard_routes],
        "fallback_groups": [f.model_dump() for f in req.fallback_groups],
        "routing": req.routing.model_dump(),
    }
    return json.dumps(items, indent=2, ensure_ascii=False) + "\n"


def build_preflight_report(req: GenerationRequest) -> str:
    deployment_count = sum(len(m.env_names) for m in req.selected_models) + sum(len(r.env_names) for r in req.wildcard_routes)
    unique_env = collect_env_names(req)
    lines = [
        "# LiteLLM Config Studio Preflight Report",
        "",
        f"Generation mode: {req.generation_mode}",
        f"Selected explicit models: {len(req.selected_models)}",
        f"Wildcard routes: {len(req.wildcard_routes)}",
        f"Generated deployments: {deployment_count}",
        f"API/env keys referenced: {len([x for x in unique_env if x != req.litellm_master_key_env])}",
        "",
        "## Routing",
        f"- Strategy: `{req.routing.routing_strategy}`",
        f"- Retries: `{req.routing.num_retries}`",
        f"- Cooldown: `{req.routing.cooldown_time}s`",
        f"- Timeout: `{req.routing.timeout or 'default'}`",
        f"- Background health checks: `{req.routing.background_health_checks}`",
        f"- Health-check routing: `{req.routing.enable_health_check_routing}`",
        f"- Prompt-cache mode: `{req.routing.prompt_cache_mode}`",
        "",
        "## Explicit Models",
    ]
    for m in req.selected_models:
        lines.append(f"- `{m.alias}` -> `{m.litellm_model}` using {len(m.env_names)} key(s)")
        if m.rpm:
            lines.append(f"  - RPM per deployment: `{m.rpm}`")
        if m.tpm:
            lines.append(f"  - TPM per deployment: `{m.tpm}`")
        if m.extra_body:
            lines.append("  - Includes model-specific `extra_body`. Live-test before production.")
        for note in m.notes:
            lines.append(f"  - Note: {note}")
    if req.wildcard_routes:
        lines.extend(["", "## Wildcard Routes"])
        for r in req.wildcard_routes:
            lines.append(f"- `{r.alias}` -> `{r.litellm_model}` using {len(r.env_names)} key(s)")
            lines.append("  - Wildcard routes may not appear as individual models in every client dropdown. Test `/v1/models`.")
    if req.fallback_groups:
        lines.extend(["", "## Fallbacks"])
        for group in req.fallback_groups:
            lines.append(f"- `{group.primary}` -> {', '.join(f'`{x}`' for x in group.fallbacks)}")
    return "\n".join(lines) + "\n"
