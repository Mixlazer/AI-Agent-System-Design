from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from typing import List

from .models import AgentCard, LLMProviderRegistration, LLMProviderInfo
from .registry import agent_registry, llm_provider_registry


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="A2A Agent & LLM Provider Registry", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/a2a/agents", response_model=AgentCard)
async def register_agent(card: AgentCard):
    return agent_registry.register(card)


@app.delete("/a2a/agents/{name}")
async def deregister_agent(name: str):
    if not agent_registry.deregister(name):
        raise HTTPException(404, f"Agent '{name}' not found")
    return {"status": "deregistered"}


@app.get("/a2a/agents", response_model=List[AgentCard])
async def list_agents():
    return agent_registry.list_all()


@app.get("/a2a/agents/{name}", response_model=AgentCard)
async def get_agent(name: str):
    agent = agent_registry.get(name)
    if not agent:
        raise HTTPException(404, f"Agent '{name}' not found")
    return agent


@app.post("/llm/providers", response_model=LLMProviderInfo)
async def register_provider(reg: LLMProviderRegistration):
    return await llm_provider_registry.register(reg)


@app.delete("/llm/providers/{name}")
async def deregister_provider(name: str):
    if not await llm_provider_registry.deregister(name):
        raise HTTPException(404, f"Provider '{name}' not found")
    return {"status": "deregistered"}


@app.get("/llm/providers", response_model=List[LLMProviderInfo])
async def list_providers():
    return await llm_provider_registry.list_all()


@app.get("/llm/providers/{name}", response_model=LLMProviderInfo)
async def get_provider(name: str):
    p = await llm_provider_registry.get(name)
    if not p:
        raise HTTPException(404, f"Provider '{name}' not found")
    return p


@app.get("/llm/providers/healthy", response_model=List[LLMProviderInfo])
async def list_healthy_providers():
    return await llm_provider_registry.list_healthy()


@app.post("/llm/providers/{name}/restore")
async def restore_provider(name: str):
    await llm_provider_registry.restore_provider(name)
    return {"status": "restored"}
