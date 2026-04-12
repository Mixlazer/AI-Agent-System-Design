"""A2A Agent Registry and LLM Provider Registry."""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from .models import AgentCard, LLMProviderRegistration, LLMProviderInfo


class AgentRegistry:
    def __init__(self):
        self._agents: Dict[str, AgentCard] = {}

    def register(self, card: AgentCard) -> AgentCard:
        self._agents[card.name] = card
        return card

    def deregister(self, name: str) -> bool:
        return self._agents.pop(name, None) is not None

    def get(self, name: str) -> Optional[AgentCard]:
        return self._agents.get(name)

    def list_all(self) -> List[AgentCard]:
        return list(self._agents.values())


class LLMProviderRegistry:
    def __init__(self):
        self._providers: Dict[str, LLMProviderInfo] = {}
        self._lock = asyncio.Lock()

    async def register(self, reg: LLMProviderRegistration) -> LLMProviderInfo:
        async with self._lock:
            info = LLMProviderInfo(**reg.model_dump())
            if reg.name in self._providers:
                # preserve runtime stats
                old = self._providers[reg.name]
                info.healthy = old.healthy
                info.avg_latency = old.avg_latency
                info.total_requests = old.total_requests
                info.total_errors = old.total_errors
                info.last_error_time = old.last_error_time
                info.registered_at = old.registered_at
            self._providers[reg.name] = info
            return info

    async def deregister(self, name: str) -> bool:
        async with self._lock:
            return self._providers.pop(name, None) is not None

    async def get(self, name: str) -> Optional[LLMProviderInfo]:
        return self._providers.get(name)

    async def list_all(self) -> List[LLMProviderInfo]:
        return list(self._providers.values())

    async def list_healthy(self) -> List[LLMProviderInfo]:
        return [p for p in self._providers.values() if p.healthy]

    async def record_success(self, name: str, latency: float, input_tokens: int = 0, output_tokens: int = 0):
        async with self._lock:
            p = self._providers.get(name)
            if not p:
                return
            p.total_requests += 1
            # exponential moving average for latency
            alpha = 0.3
            p.avg_latency = alpha * latency + (1 - alpha) * p.avg_latency
            p.healthy = True

    async def record_error(self, name: str):
        async with self._lock:
            p = self._providers.get(name)
            if not p:
                return
            p.total_requests += 1
            p.total_errors += 1
            p.last_error_time = datetime.utcnow()
            # mark unhealthy after 3 consecutive recent errors
            recent_errors = p.total_errors
            if recent_errors >= 3:
                p.healthy = False

    async def restore_provider(self, name: str):
        """Manually restore an unhealthy provider."""
        async with self._lock:
            p = self._providers.get(name)
            if p:
                p.healthy = True
                p.total_errors = 0

    async def get_providers_for_model(self, model: str) -> List[LLMProviderInfo]:
        return [p for p in self._providers.values() if model in p.models and p.healthy]


agent_registry = AgentRegistry()
llm_provider_registry = LLMProviderRegistry()
