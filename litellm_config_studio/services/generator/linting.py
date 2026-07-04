from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any
import re
import yaml


def lint_yaml_text(text: str) -> dict[str, Any]:
    result: dict[str, Any] = {"ok": True, "errors": [], "warnings": [], "summary": {}, "hints": []}
    try:
        data = yaml.safe_load(text) or {}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "errors": [f"YAML parse error: {exc}"], "warnings": [], "summary": {}, "hints": []}

    if not isinstance(data, dict):
        result["ok"] = False
        result["errors"].append("Top-level YAML must be a mapping/object.")
        return result

    model_list = data.get("model_list") or []
    if not isinstance(model_list, list):
        result["ok"] = False
        result["errors"].append("model_list must be a list.")
        return result

    names = [item.get("model_name") for item in model_list if isinstance(item, dict)]
    counts = Counter(names)
    duplicates = {name: count for name, count in counts.items() if name and count > 1}
    env_refs: set[str] = set()
    hardcoded_keys = 0
    missing_api_base = []
    wildcard_entries = []
    extra_body_count = 0
    deployments_by_name = defaultdict(list)
    models_by_name = defaultdict(set)
    rpm_missing = []

    for idx, item in enumerate(model_list):
        if not isinstance(item, dict):
            result["warnings"].append(f"model_list[{idx}] is not an object.")
            continue
        name = item.get("model_name")
        params = item.get("litellm_params") or {}
        if not isinstance(params, dict):
            result["errors"].append(f"model_list[{idx}].litellm_params must be an object.")
            continue
        deployments_by_name[name].append(params)
        api_key = params.get("api_key")
        if isinstance(api_key, str):
            if api_key.startswith("os.environ/"):
                env_refs.add(api_key.split("/", 1)[1])
            elif api_key:
                hardcoded_keys += 1
        else:
            result["warnings"].append(f"{name or idx}: missing api_key.")
        model = params.get("model", "")
        if isinstance(model, str):
            models_by_name[name].add(model)
            if "*" in model or (isinstance(name, str) and "*" in name):
                wildcard_entries.append(name or model)
            if model.startswith("openai/") and "api_base" not in params and "api_key" in params:
                if not any(model.startswith(prefix) for prefix in ("openai/gpt", "openai/o", "openai/text-embedding", "openai/dall-e")):
                    missing_api_base.append(name or model)
        if "extra_body" in params:
            extra_body_count += 1
        if name in duplicates and not (item.get("rpm") or item.get("tpm")):
            rpm_missing.append(name)

    if duplicates:
        result["warnings"].append(f"Duplicate model_name groups detected for load balancing: {duplicates}")
        if rpm_missing:
            result["hints"].append("Load-balanced groups without rpm/tpm can still work, but limits help LiteLLM route more safely.")
    if hardcoded_keys:
        result["warnings"].append(f"Found {hardcoded_keys} hardcoded api_key value(s). Prefer os.environ/KEY_NAME.")
    if missing_api_base:
        result["warnings"].append(f"Some openai/* custom models may need api_base: {missing_api_base[:10]}")
    if wildcard_entries:
        result["hints"].append("Wildcard entries are compact but some clients may display literal wildcard names. Test /v1/models with your target client.")
    for name, model_ids in models_by_name.items():
        if name and len(model_ids) > 1:
            result["warnings"].append(f"Model name {name!r} maps to multiple upstream models: {sorted(model_ids)}")

    litellm_settings = data.get("litellm_settings") or {}
    router_settings = data.get("router_settings") or {}
    general_settings = data.get("general_settings") or {}
    if isinstance(litellm_settings, dict) and isinstance(litellm_settings.get("default_litellm_params"), dict):
        if "extra_body" in litellm_settings["default_litellm_params"]:
            result["warnings"].append("Global default_litellm_params.extra_body can conflict with model-specific extra_body. Prefer model-specific bodies.")
    if model_list and not router_settings:
        result["warnings"].append("No router_settings found. Consider num_retries and cooldown_time for production.")
    if isinstance(router_settings, dict):
        if router_settings.get("routing_strategy") in {"simple-shuffle", None} and any("gemini" in str(x).lower() for x in models_by_name.values()):
            result["hints"].append("For prompt-cache-heavy Gemini/Vertex workloads, consider app-level prompt_cache_key/sticky routing instead of pure random distribution.")
        if router_settings.get("num_retries", 0) == 0:
            result["hints"].append("num_retries is 0. Production configs usually benefit from at least 1-2 retries.")
    if general_settings and not general_settings.get("enable_health_check_routing"):
        result["hints"].append("background_health_checks is configured but enable_health_check_routing is not enabled.")

    result["summary"] = {
        "model_entries": len(model_list),
        "unique_model_names": len(counts),
        "duplicate_groups": duplicates,
        "wildcard_entries": wildcard_entries,
        "env_refs": sorted(env_refs),
        "extra_body_entries": extra_body_count,
        "has_router_settings": bool(router_settings),
        "has_litellm_settings": bool(litellm_settings),
        "has_general_settings": bool(general_settings),
    }
    result["ok"] = not result["errors"]
    return result


def analyze_existing_config(text: str) -> dict[str, Any]:
    lint = lint_yaml_text(text)
    analysis = dict(lint)
    suggestions: list[str] = []
    summary = lint.get("summary", {})
    if summary.get("duplicate_groups"):
        suggestions.append("Duplicate model_name entries look like load-balanced deployments. Keep explicit mode for WebUI visibility, or convert to generated groups.")
    if not summary.get("has_router_settings"):
        suggestions.append("Add router_settings with simple-shuffle, num_retries, and cooldown_time.")
    if re.search(r"api_key:\s*(?!os\.environ/)", text):
        suggestions.append("Replace hardcoded API keys with os.environ/KEY_NAME.")
    if summary.get("extra_body_entries"):
        suggestions.append("Live-test each model-specific extra_body preset; provider-specific thinking controls vary by model.")
    if summary.get("wildcard_entries"):
        suggestions.append("Test /v1/models in your target client; wildcard routes may not expand into individual dropdown items.")
    if not summary.get("has_general_settings") and summary.get("duplicate_groups"):
        suggestions.append("Consider health-check routing for configs with many API keys/deployments.")
    analysis["suggestions"] = suggestions
    return analysis
