from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

CACHE_DIR = Path.home() / ".cache" / "litellm-config-studio"


def cache_get(namespace: str, key: str, ttl_seconds: int = 86400) -> Any | None:
    path = _path(namespace, key)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if time.time() - float(payload.get("created_at", 0)) > ttl_seconds:
            return None
        return payload.get("value")
    except Exception:  # noqa: BLE001
        return None


def cache_set(namespace: str, key: str, value: Any) -> None:
    path = _path(namespace, key)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"created_at": time.time(), "namespace": namespace, "key": key, "value": value}
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _path(namespace: str, key: str) -> Path:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
    return CACHE_DIR / namespace / f"{digest}.json"
