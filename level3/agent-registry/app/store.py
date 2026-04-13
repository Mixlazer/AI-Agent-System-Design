from __future__ import annotations

from asyncio import Lock
from datetime import datetime
from typing import Dict, List, Optional

from .models import AgentCard, AgentCardCreate


class AgentStore:
    def __init__(self):
        self._items: Dict[str, AgentCard] = {}
        self._lock = Lock()

    async def create(self, payload: AgentCardCreate) -> AgentCard:
        async with self._lock:
            card = AgentCard(**payload.model_dump())
            self._items[card.agent_id] = card
            return card

    async def list(self, tag: Optional[str] = None, status: Optional[str] = None) -> List[AgentCard]:
        async with self._lock:
            items = list(self._items.values())
        if tag:
            items = [a for a in items if tag in a.tags]
        if status:
            items = [a for a in items if a.status == status]
        return items

    async def get(self, agent_id: str) -> Optional[AgentCard]:
        async with self._lock:
            return self._items.get(agent_id)

    async def update(self, agent_id: str, payload: AgentCardCreate) -> Optional[AgentCard]:
        async with self._lock:
            current = self._items.get(agent_id)
            if not current:
                return None
            updated = current.model_copy(update=payload.model_dump())
            self._items[agent_id] = updated
            return updated

    async def delete(self, agent_id: str) -> None:
        async with self._lock:
            self._items.pop(agent_id, None)

    async def patch_status(self, agent_id: str, status: str) -> Optional[AgentCard]:
        async with self._lock:
            current = self._items.get(agent_id)
            if not current:
                return None
            updated = current.model_copy(update={"status": status})
            self._items[agent_id] = updated
            return updated

    async def update_heartbeat(self, agent_id: str) -> Optional[AgentCard]:
        async with self._lock:
            current = self._items.get(agent_id)
            if not current:
                return None
            updated = current.model_copy(update={"last_heartbeat": datetime.utcnow()})
            self._items[agent_id] = updated
            return updated
