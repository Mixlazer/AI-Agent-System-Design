import asyncio
import os
from datetime import datetime

HEARTBEAT_TTL = int(os.getenv("HEARTBEAT_TTL_SECONDS", "60"))
CLEANUP_TIMEOUT = int(os.getenv("AGENT_REMOVAL_TIMEOUT_SECONDS", "300"))
INTERVAL = int(os.getenv("CLEANUP_INTERVAL_SECONDS", "30"))


async def run_health_checker(store) -> None:
    while True:
        await asyncio.sleep(INTERVAL)
        now = datetime.utcnow()
        agents = await store.list()
        for agent in agents:
            if agent.last_heartbeat is None:
                continue
            age_seconds = (now - agent.last_heartbeat).total_seconds()
            if age_seconds > CLEANUP_TIMEOUT:
                await store.delete(agent.agent_id)
            elif age_seconds > HEARTBEAT_TTL:
                await store.patch_status(agent.agent_id, "unhealthy")
