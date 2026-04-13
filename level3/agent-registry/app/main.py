import asyncio
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException

from .health_checker import run_health_checker
from .models import AgentCard, AgentCardCreate
from .store import AgentStore

store = AgentStore()


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(run_health_checker(store))
    yield
    task.cancel()


app = FastAPI(title="A2A Agent Registry", lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    agents = await store.list()
    healthy = [item for item in agents if item.status == "healthy"]
    return {"status": "ok", "agents_count": len(agents), "healthy_count": len(healthy)}


@app.post("/agents", status_code=201, response_model=AgentCard)
async def register_agent(card: AgentCardCreate) -> AgentCard:
    return await store.create(card)


@app.get("/agents", response_model=list[AgentCard])
async def list_agents(tag: str | None = None, status: str | None = None) -> list[AgentCard]:
    return await store.list(tag=tag, status=status)


@app.get("/agents/{agent_id}", response_model=AgentCard)
async def get_agent(agent_id: str) -> AgentCard:
    agent = await store.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@app.put("/agents/{agent_id}", response_model=AgentCard)
async def update_agent(agent_id: str, payload: AgentCardCreate) -> AgentCard:
    agent = await store.update(agent_id, payload)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@app.delete("/agents/{agent_id}", status_code=204)
async def delete_agent(agent_id: str) -> None:
    await store.delete(agent_id)


@app.post("/agents/{agent_id}/heartbeat")
async def heartbeat(agent_id: str) -> dict:
    agent = await store.update_heartbeat(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    await store.patch_status(agent_id, "healthy")
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


# ── A2A-compatible routes (same handlers, /a2a prefix) ────
@app.get("/a2a/agents", response_model=list[AgentCard])
async def a2a_list_agents(tag: str | None = None, status: str | None = None) -> list[AgentCard]:
    return await store.list(tag=tag, status=status)


@app.get("/a2a/agents/{agent_id}", response_model=AgentCard)
async def a2a_get_agent(agent_id: str) -> AgentCard:
    agent = await store.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent
