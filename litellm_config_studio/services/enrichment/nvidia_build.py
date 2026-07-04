from __future__ import annotations

import ast
import json
import re
from typing import Any

import httpx
from bs4 import BeautifulSoup

from litellm_config_studio.services.cache.local_cache import cache_get, cache_set

from litellm_config_studio.models import ExtraBodyPreset, ModelCapability, ProviderModel


class NvidiaBuildEnricher:
    """Best-effort NVIDIA Build page enrichment.

    NVIDIA Build pages are product pages, not a stable public metadata API. This parser is
    intentionally conservative: it labels everything as webpage-derived and expects users to
    live-test generated extra_body presets before production use.
    """

    base_url = "https://build.nvidia.com"

    async def enrich(self, model: ProviderModel) -> ProviderModel:
        url = f"{self.base_url}/{model.model_id.strip('/')}"
        model.raw.setdefault("nvidia_build_url", url)
        try:
            async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()
                html = response.text
        except Exception as exc:  # noqa: BLE001
            model.warnings.append(f"Could not enrich from NVIDIA Build page: {exc}")
            return model

        text = BeautifulSoup(html, "html.parser").get_text("\n", strip=True)
        code_blocks = self._extract_code_blocks(html)

        model.sources["nvidia_build_page"] = "provider_webpage"
        model.description = model.description or self._extract_description(text)
        self._extract_context_window(model, html, text)
        self._extract_defaults(model, text, code_blocks)
        self._extract_capabilities(model, text)
        model.extra_body_presets = self._extract_extra_body_presets(html, text, code_blocks)
        self._extract_warnings(model, text)
        return model

    def _extract_code_blocks(self, html: str) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        blocks: list[str] = []
        for tag in soup.find_all(["code", "pre"]):
            content = tag.get_text("\n", strip=True)
            if content and len(content) > 20:
                blocks.append(content)
        # Also scan scripts/embedded text for code-ish snippets.
        for match in re.finditer(r"extra_body\s*=\s*\{.*?\}\s*\)?", html, flags=re.S):
            blocks.append(match.group(0))
        # Next.js/app pages often embed snippets in JSON strings; make a normalized text pass too.
        decoded = html.replace('\\n', '\n').replace('\\"', '"').replace("\\'", "'")
        for match in re.finditer(r"extra_body\s*=\s*\{.*?\}\s*\)?", decoded, flags=re.S):
            blocks.append(match.group(0))
        return list(dict.fromkeys(blocks))[:50]

    def _extract_context_window(self, model: ProviderModel, html: str, text: str) -> None:
        import re
        if model.context_window: return
        
        m1 = re.search(r'Maximum context length of ([0-9]+)\s*(million|k|m)\s*tokens', text, re.I)
        if m1:
            val = int(m1.group(1))
            mult = m1.group(2).lower()
            if mult in ('million', 'm'):
                model.context_window = val * 1000000
            elif mult == 'k':
                model.context_window = val * 1000
            return
            
        m2 = re.search(r'([0-9]+)\s*(?:[KkMm])(?:-token)?\s*context', html, re.I)
        if m2:
            full = m2.group(0).lower()
            val = int(m2.group(1))
            if 'm' in full:
                model.context_window = val * 1000000
            elif 'k' in full:
                model.context_window = val * 1000

    def _extract_description(self, text: str) -> str | None:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        # Skip short navigation-ish lines. Pick the first plausible long sentence.
        for line in lines:
            if len(line) > 80 and not line.lower().startswith(("import ", "from ", "curl ")):
                return line[:600]
        return None

    def _extract_defaults(self, model: ProviderModel, text: str, code_blocks: list[str]) -> None:
        haystack = "\n".join(code_blocks) + "\n" + text
        patterns = {
            "max_output_tokens": [r"max_tokens\s*=\s*(\d+)", r"\"max_tokens\"\s*:\s*(\d+)", r"Max Tokens\s*(\d+)"],
            "temperature": [r"temperature\s*=\s*([0-9.]+)", r"\"temperature\"\s*:\s*([0-9.]+)"],
            "top_p": [r"top_p\s*=\s*([0-9.]+)", r"\"top_p\"\s*:\s*([0-9.]+)"],
        }
        for field, field_patterns in patterns.items():
            for pat in field_patterns:
                m = re.search(pat, haystack, flags=re.I)
                if not m:
                    continue
                val = m.group(1)
                try:
                    parsed: int | float = int(val) if field == "max_output_tokens" else float(val)
                    setattr(model, field, parsed)
                    model.sources[field] = "provider_webpage"
                    break
                except ValueError:
                    continue

    def _extract_capabilities(self, model: ProviderModel, text: str) -> None:
        low = text.lower()
        caps = model.capabilities or ModelCapability()
        if "function calling" in low or "tool calling" in low:
            caps.function_calling = True
        if "structured output" in low or "json schema" in low:
            caps.structured_output = True
        if "vision" in low or "image" in low or "multimodal" in low or "omni" in low:
            caps.vision = True
        if "thinking" in low or "reasoning" in low or "reasoning_effort" in low or "enable_thinking" in low:
            caps.thinking = True
            caps.reasoning = True
        if "stream" in low:
            caps.streaming = True
        model.capabilities = caps
        model.sources["capabilities"] = "provider_webpage"

    def _extract_warnings(self, model: ProviderModel, text: str) -> None:
        warning_patterns = [
            r"deprecated[^.\n]*(?:\.|\n)",
            r"deprecation[^.\n]*(?:\.|\n)",
            r"will be removed[^.\n]*(?:\.|\n)",
            r"not recommended[^.\n]*(?:\.|\n)",
            r"available until[^.\n]*(?:\.|\n)",
        ]
        found: list[str] = []
        for pat in warning_patterns:
            for m in re.finditer(pat, text, flags=re.I):
                item = " ".join(m.group(0).split())
                if item and item not in found:
                    found.append(item)
        model.warnings.extend(found[:5])

    def _extract_extra_body_presets(self, html: str, text: str, code_blocks: list[str]) -> list[ExtraBodyPreset]:
        presets: list[ExtraBodyPreset] = []
        combined = "\n".join(code_blocks) + "\n" + text

        for body in self._parse_python_extra_body(combined):
            name, label = self._name_preset(body)
            presets.append(ExtraBodyPreset(name=name, label=label, body=body, source="provider_webpage"))

        # Fallback pattern detection if parsing code failed or returned empty custom dicts.
        import re
        if not any(p.name != "custom_extra_body" for p in presets):
            # We search html here because the reasoning_effort variants might be hidden in JS ternary operators
            # and omitted from the visible text/code blocks if the UI default is "none".
            efforts = set(re.findall(r'\\?"reasoning_effort\\?"\s*:\s*\\?"([^"\\]+)\\?"', html, re.I))
            for eff in efforts:
                if eff.lower() == "none": continue
                presets.append(
                    ExtraBodyPreset(
                        name=f"thinking_{eff.lower()}",
                        label=f"Thinking: {eff.lower()} effort",
                        body={"chat_template_kwargs": {"thinking": True, "reasoning_effort": eff}},
                        source="provider_webpage",
                        notes="Extracted from UI state; live-test before use.",
                    )
                )
            if not efforts:
                if re.search(r'\\?"enable_thinking\\?"\s*:\s*true', html, re.I):
                    presets.append(
                        ExtraBodyPreset(
                            name="thinking_enabled",
                            label="Thinking enabled",
                            body={"chat_template_kwargs": {"enable_thinking": True}},
                            source="provider_webpage",
                            notes="Extracted from UI state; live-test before use.",
                        )
                    )
                elif re.search(r'\\?"thinking\\?"\s*:\s*true', html, re.I):
                    presets.append(
                        ExtraBodyPreset(
                            name="thinking_enabled",
                            label="Thinking enabled",
                            body={"chat_template_kwargs": {"thinking": True}},
                            source="provider_webpage",
                            notes="Extracted from UI state; live-test before use.",
                        )
                    )
                elif "low_effort" in html.lower():
                    presets.append(
                        ExtraBodyPreset(
                            name="low_effort_reasoning",
                            label="Low-effort reasoning",
                            body={"chat_template_kwargs": {"enable_thinking": True, "low_effort": True}},
                            source="provider_webpage",
                            notes="Detected from page text; live-test before use.",
                        )
                    )

        # Deduplicate by JSON body.
        seen: set[str] = set()
        unique: list[ExtraBodyPreset] = []
        for preset in presets:
            key = json.dumps(preset.body, sort_keys=True)
            if key not in seen:
                seen.add(key)
                unique.append(preset)
        return unique[:10]

    def _parse_python_extra_body(self, text: str) -> list[dict[str, Any]]:
        bodies: list[dict[str, Any]] = []
        # Extract balanced dict after extra_body= or "extra_body":.
        for marker in ["extra_body=", "extra_body =", "\"extra_body\":", "'extra_body':"]:
            start = 0
            while True:
                idx = text.find(marker, start)
                if idx == -1:
                    break
                brace_idx = text.find("{", idx)
                if brace_idx == -1:
                    break
                snippet = self._balanced_braces(text, brace_idx)
                if snippet:
                    parsed = self._parse_dict_snippet(snippet)
                    if isinstance(parsed, dict):
                        bodies.append(parsed)
                start = brace_idx + 1
        return bodies

    def _balanced_braces(self, text: str, start: int) -> str | None:
        depth = 0
        in_str: str | None = None
        escape = False
        for i in range(start, min(len(text), start + 5000)):
            ch = text[i]
            if in_str:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == in_str:
                    in_str = None
                continue
            if ch in ("'", '"'):
                in_str = ch
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
        return None

    def _parse_dict_snippet(self, snippet: str) -> Any:
        normalized = snippet.strip()
        # Try Python literal first because NVIDIA code samples are Python.
        try:
            return ast.literal_eval(normalized)
        except Exception:  # noqa: BLE001
            pass
        # Try JSON-ish normalization.
        try:
            normalized = normalized.replace("True", "true").replace("False", "false").replace("None", "null")
            return json.loads(normalized)
        except Exception:  # noqa: BLE001
            return None

    def _name_preset(self, body: dict[str, Any]) -> tuple[str, str]:
        kwargs = body.get("chat_template_kwargs") if isinstance(body, dict) else None
        if not isinstance(kwargs, dict):
            return "custom_extra_body", "Custom extra_body"
        if kwargs.get("reasoning_effort"):
            effort = str(kwargs["reasoning_effort"]).lower()
            return f"thinking_{effort}", f"Thinking: {effort} effort"
        if kwargs.get("low_effort"):
            return "low_effort_reasoning", "Low-effort reasoning"
        if kwargs.get("enable_thinking") is True or kwargs.get("thinking") is True:
            return "thinking_enabled", "Thinking enabled"
        if kwargs.get("enable_thinking") is False or kwargs.get("thinking") is False:
            return "thinking_disabled", "Thinking disabled"
        return "custom_extra_body", "Custom extra_body"
