from __future__ import annotations

from asyncio import Lock
from datetime import datetime
from typing import Dict, List, Optional

from .models import Provider, ProviderCreate


class ProviderStore:
    def __init__(self):
        self._items: Dict[str, Provider] = {}
        self._lock = Lock()

    async def create(self, payload: ProviderCreate) -> Provider:
        async with self._lock:
            provider = Provider(**payload.model_dump())
            self._items[provider.provider_id] = provider
            return provider

    async def list(self, model: Optional[str] = None, status: Optional[str] = None) -> List[Provider]:
        async with self._lock:
            items = list(self._items.values())
        if model:
            items = [p for p in items if model in p.models]
        if status:
            items = [p for p in items if p.status == status]
        return items

    async def get(self, provider_id: str) -> Optional[Provider]:
        async with self._lock:
            return self._items.get(provider_id)

    async def update(self, provider_id: str, payload: ProviderCreate) -> Optional[Provider]:
        async with self._lock:
            current = self._items.get(provider_id)
            if not current:
                return None
            updated = current.model_copy(update=payload.model_dump())
            self._items[provider_id] = updated
            return updated

    async def delete(self, provider_id: str) -> None:
        async with self._lock:
            self._items.pop(provider_id, None)

    async def patch_status(self, provider_id: str, status: str) -> Optional[Provider]:
        async with self._lock:
            current = self._items.get(provider_id)
            if not current:
                return None
            updated = current.model_copy(update={"status": status, "last_health_check": datetime.utcnow()})
            self._items[provider_id] = updated
            return updated

    async def patch_metrics(self, provider_id: str, payload: dict) -> Optional[Provider]:
        async with self._lock:
            current = self._items.get(provider_id)
            if not current:
                return None
            merged = {
                "avg_latency_ms": payload.get("avg_latency_ms", current.avg_latency_ms),
                "p95_latency_ms": payload.get("p95_latency_ms", current.p95_latency_ms),
                "error_rate": payload.get("error_rate", current.error_rate),
                "last_health_check": datetime.utcnow(),
            }
            updated = current.model_copy(update=merged)
            self._items[provider_id] = updated
            return updated

    async def count(self) -> int:
        async with self._lock:
            return len(self._items)
