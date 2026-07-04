from __future__ import annotations

from io import BytesIO
import zipfile

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from litellm_config_studio.models import ApiKeyPlan, BulkKeyTestRequest, GenerationRequest, ProviderModel, TestRequest
from litellm_config_studio.services.compatibility import get_compatibility_report
from litellm_config_studio.services.generator.linting import analyze_existing_config, lint_yaml_text
from litellm_config_studio.services.generator.yaml_builder import (
    build_config_dict,
    build_docker_compose,
    build_env_example,
    build_import_script,
    build_models_report,
    build_preflight_report,
    build_test_curl,
    build_yaml,
)
from litellm_config_studio.services.providers.registry import REGISTRY

router = APIRouter(prefix="/api")


class FetchModelsRequest(BaseModel):
    provider_id: str
    api_key: str | None = None
    base_url: str | None = None
    enrich_nvidia: bool = False
    enrich_limit: int = 20


class EnrichModelRequest(BaseModel):
    provider_id: str
    model: ProviderModel


class LintRequest(BaseModel):
    yaml_text: str


class ExportZipRequest(BaseModel):
    files: dict[str, str]


@router.get("/providers")
def providers() -> dict:
    return {"providers": [adapter.info().model_dump() for adapter in REGISTRY.values()]}


@router.get("/compatibility")
def compatibility() -> dict:
    return get_compatibility_report()


@router.post("/key-plan")
def key_plan(plan: ApiKeyPlan) -> dict:
    return {"env_names": plan.env_names()}


@router.post("/models/fetch")
async def fetch_models(req: FetchModelsRequest) -> dict:
    adapter = REGISTRY.get(req.provider_id)
    if not adapter:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {req.provider_id}")
    try:
        models = await adapter.fetch_models(api_key=req.api_key or None, base_url=req.base_url or None)
        if req.provider_id == "nvidia" and req.enrich_nvidia:
            limit = max(0, min(req.enrich_limit, 100))
            enriched = []
            for model in models[:limit]:
                enriched.append(await adapter.enrich_model(model))
            models = enriched + models[len(enriched) :]
        return {"ok": True, "count": len(models), "models": [m.model_dump() for m in models]}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "message": str(exc), "count": 0, "models": []}


@router.post("/models/enrich")
async def enrich_model(req: EnrichModelRequest) -> dict:
    adapter = REGISTRY.get(req.provider_id)
    if not adapter:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {req.provider_id}")
    try:
        model = await adapter.enrich_model(req.model)
        return {"ok": True, "model": model.model_dump()}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "message": str(exc), "model": req.model.model_dump()}


@router.post("/test/key")
async def test_key(req: TestRequest) -> dict:
    adapter = REGISTRY.get(req.provider_id)
    if not adapter:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {req.provider_id}")
    return await adapter.test_key(api_key=req.api_key or None, base_url=req.base_url or None)


@router.post("/test/keys")
async def test_keys(req: BulkKeyTestRequest) -> dict:
    adapter = REGISTRY.get(req.provider_id)
    if not adapter:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {req.provider_id}")
    results = []
    for idx, key in enumerate(req.api_keys, start=1):
        res = await adapter.test_key(api_key=key or None, base_url=req.base_url or None)
        results.append({"index": idx, **res})
    return {"ok": any(r.get("ok") for r in results), "results": results}


@router.post("/test/chat")
async def test_chat(req: TestRequest) -> dict:
    adapter = REGISTRY.get(req.provider_id)
    if not adapter:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {req.provider_id}")
    return await adapter.test_chat(req)


@router.post("/test/estimate")
def estimate_tests(req: GenerationRequest) -> dict:
    deployment_count = sum(len(m.env_names) for m in req.selected_models) + sum(len(r.env_names) for r in req.wildcard_routes)
    return {
        "selected_models": len(req.selected_models),
        "wildcard_routes": len(req.wildcard_routes),
        "deployments": deployment_count,
        "cheap_smoke_calls": max(1, len(req.selected_models)),
        "full_deployment_calls": deployment_count,
        "warning": "Live tests call provider APIs. Start with cheap smoke tests before full deployment tests.",
    }


@router.post("/generate")
def generate(req: GenerationRequest) -> dict:
    yaml_text = build_yaml(req)
    files = {
        "config.yaml": yaml_text,
        ".env.example": build_env_example(req),
        "test-curl.sh": build_test_curl(req),
        "docker-compose.yml": build_docker_compose() if req.include_docker_compose else "",
        "litellm-import.py": build_import_script(req) if req.include_import_script else "",
        "preflight-report.md": build_preflight_report(req),
        "models-report.json": build_models_report(req) if req.include_models_report else "",
    }
    return {
        "ok": True,
        "config": build_config_dict(req),
        "files": files,
        "lint": lint_yaml_text(yaml_text),
    }


@router.post("/export-zip")
def export_zip(req: ExportZipRequest):
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in req.files.items():
            if content is None:
                continue
            safe = name.strip().lstrip("/").replace("..", "_") or "output.txt"
            zf.writestr(safe, content)
    buffer.seek(0)
    headers = {"Content-Disposition": 'attachment; filename="litellm-config-studio-export.zip"'}
    return StreamingResponse(buffer, media_type="application/zip", headers=headers)


@router.post("/lint")
def lint(req: LintRequest) -> dict:
    return lint_yaml_text(req.yaml_text)


@router.post("/analyze-config")
def analyze(req: LintRequest) -> dict:
    return analyze_existing_config(req.yaml_text)
