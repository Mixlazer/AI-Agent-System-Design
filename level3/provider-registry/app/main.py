import json
import os

from fastapi import FastAPI, HTTPException

from .models import Provider, ProviderCreate
from .store import ProviderStore

app = FastAPI(title="Provider Registry")
store = ProviderStore()


@app.on_event("startup")
async def startup() -> None:
    config_path = os.getenv("PROVIDERS_CONFIG", "/app/providers.json")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as fh:
            providers = json.load(fh)
        for item in providers:
            await store.create(ProviderCreate(**item))


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "providers_count": await store.count()}


@app.post("/providers", status_code=201, response_model=Provider)
async def register_provider(provider: ProviderCreate) -> Provider:
    return await store.create(provider)


@app.get("/providers", response_model=list[Provider])
async def list_providers(model: str | None = None, status: str | None = None) -> list[Provider]:
    return await store.list(model=model, status=status)


@app.get("/providers/{provider_id}", response_model=Provider)
async def get_provider(provider_id: str) -> Provider:
    provider = await store.get(provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return provider


@app.put("/providers/{provider_id}", response_model=Provider)
async def update_provider(provider_id: str, payload: ProviderCreate) -> Provider:
    provider = await store.update(provider_id, payload)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return provider


@app.delete("/providers/{provider_id}", status_code=204)
async def delete_provider(provider_id: str) -> None:
    await store.delete(provider_id)


@app.patch("/providers/{provider_id}/status")
async def patch_status(provider_id: str, payload: dict) -> dict:
    provider = await store.patch_status(provider_id, payload.get("status", "unhealthy"))
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return {"ok": True}


@app.patch("/providers/{provider_id}/metrics")
async def patch_metrics(provider_id: str, payload: dict) -> dict:
    provider = await store.patch_metrics(provider_id, payload)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return {"ok": True}


@app.get("/providers/by-model/{model_name}", response_model=list[Provider])
async def providers_by_model(model_name: str) -> list[Provider]:
    providers = await store.list(model=model_name, status="healthy")
    return sorted(providers, key=lambda p: (p.priority, p.avg_latency_ms))
