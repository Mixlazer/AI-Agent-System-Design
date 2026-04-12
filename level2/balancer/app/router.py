"""Advanced LLM/Agent balancer with latency-based and health-aware routing."""
import asyncio
import itertools
import random
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

import httpx


@dataclass
class ProviderState:
    name: str
    url: str
    api_key: str = ""
    models: List[str] = field(default_factory=list)
    weight: float = 1.0
    priority: int = 0
    price_per_token_input: float = 0.0
    price_per_token_output: float = 0.0
    healthy: bool = True
    avg_latency: float = 0.0
    total_requests: int = 0
    total_errors: int = 0
    consecutive_errors: int = 0


class AdvancedBalancer:
    def __init__(self):
        self._providers: Dict[str, ProviderState] = {}
        self._model_index: Dict[str, List[str]] = {}
        self._rr_counters: Dict[str, int] = {}
        self._lock = asyncio.Lock()

    async def update_providers(self, providers: List[dict]):
        """Sync providers from registry."""
        async with self._lock:
            self._providers.clear()
            self._model_index.clear()
            for p in providers:
                state = ProviderState(
                    name=p["name"], url=p["url"], api_key=p.get("api_key", ""),
                    models=p.get("models", []), weight=p.get("weight", 1.0),
                    priority=p.get("priority", 0),
                    price_per_token_input=p.get("price_per_token_input", 0.0),
                    price_per_token_output=p.get("price_per_token_output", 0.0),
                    healthy=p.get("healthy", True),
                    avg_latency=p.get("avg_latency", 0.0),
                    total_requests=p.get("total_requests", 0),
                    total_errors=p.get("total_errors", 0),
                )
                self._providers[p["name"]] = state
                for m in state.models:
                    self._model_index.setdefault(m, []).append(p["name"])

    async def select_provider(self, model: str, strategy: str = "latency") -> Optional[ProviderState]:
        async with self._lock:
            pnames = self._model_index.get(model, [])
            candidates = [self._providers[n] for n in pnames if self._providers[n].healthy]
            if not candidates:
                # fallback: all providers for that model (even unhealthy)
                candidates = [self._providers[n] for n in pnames]
            if not candidates:
                # fallback: any healthy provider
                candidates = [p for p in self._providers.values() if p.healthy]
            if not candidates:
                return None

            if strategy == "round_robin":
                return self._select_rr(model, candidates)
            elif strategy == "weighted":
                return self._select_weighted(candidates)
            elif strategy == "latency":
                return self._select_latency(candidates)
            elif strategy == "health":
                return self._select_health(candidates)
            else:
                return self._select_latency(candidates)

    def _select_rr(self, model: str, candidates: List[ProviderState]) -> ProviderState:
        idx = self._rr_counters.get(model, 0)
        chosen = candidates[idx % len(candidates)]
        self._rr_counters[model] = idx + 1
        return chosen

    def _select_weighted(self, candidates: List[ProviderState]) -> ProviderState:
        weights = [c.weight for c in candidates]
        return random.choices(candidates, weights=weights, k=1)[0]

    def _select_latency(self, candidates: List[ProviderState]) -> ProviderState:
        """Select provider with lowest average latency. Prefer providers with actual data."""
        def sort_key(p: ProviderState) -> float:
            if p.avg_latency == 0.0:
                return 999.0  # no data yet, put at end
            return p.avg_latency
        return min(candidates, key=sort_key)

    def _select_health(self, candidates: List[ProviderState]) -> ProviderState:
        """Health-aware: prioritize by (healthy, priority, -consecutive_errors, latency)."""
        def sort_key(p: ProviderState) -> Tuple:
            return (not p.healthy, -p.priority, p.consecutive_errors, p.avg_latency or 999.0)
        return min(candidates, key=sort_key)

    async def record_success(self, name: str, latency: float):
        async with self._lock:
            p = self._providers.get(name)
            if not p:
                return
            p.total_requests += 1
            alpha = 0.3
            p.avg_latency = alpha * latency + (1 - alpha) * p.avg_latency
            p.consecutive_errors = 0
            p.healthy = True

    async def record_error(self, name: str):
        async with self._lock:
            p = self._providers.get(name)
            if not p:
                return
            p.total_requests += 1
            p.total_errors += 1
            p.consecutive_errors += 1
            if p.consecutive_errors >= 3:
                p.healthy = False

    def list_providers(self) -> List[ProviderState]:
        return list(self._providers.values())


balancer = AdvancedBalancer()
