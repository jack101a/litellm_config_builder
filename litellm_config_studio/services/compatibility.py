from __future__ import annotations

import importlib.metadata
import platform
import shutil
import subprocess
from typing import Any


PACKAGE_NAMES = ["fastapi", "uvicorn", "httpx", "pydantic", "PyYAML", "beautifulsoup4"]


def get_compatibility_report() -> dict[str, Any]:
    report: dict[str, Any] = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packages": {},
        "litellm": {
            "installed": False,
            "version": None,
            "path": shutil.which("litellm"),
            "raw": None,
            "warnings": [],
        },
        "recommendations": [],
    }
    for name in PACKAGE_NAMES:
        try:
            report["packages"][name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            report["packages"][name] = None

    if report["litellm"]["path"]:
        try:
            proc = subprocess.run([report["litellm"]["path"], "--version"], capture_output=True, text=True, timeout=8)
            raw = (proc.stdout or proc.stderr or "").strip()
            report["litellm"]["raw"] = raw
            report["litellm"]["installed"] = proc.returncode == 0 or bool(raw)
            report["litellm"]["version"] = _extract_version(raw)
        except Exception as exc:  # noqa: BLE001
            report["litellm"]["warnings"].append(f"Could not run litellm --version: {exc}")
    else:
        report["litellm"]["warnings"].append("LiteLLM CLI was not found on PATH. Generated configs can still be exported.")

    report["recommendations"].extend([
        "Use explicit model entries for production aliases, budgets, and clean Open WebUI dropdowns.",
        "Use wildcard routes for experimentation, then test /v1/models in the target client.",
        "Keep provider-specific extra_body on individual model aliases, not global defaults.",
        "Run cheap live tests before full deployment tests to control provider cost.",
    ])
    return report


def _extract_version(raw: str | None) -> str | None:
    if not raw:
        return None
    for token in raw.replace(",", " ").split():
        if any(ch.isdigit() for ch in token) and "." in token:
            return token.strip("v")
    return raw[:120]
