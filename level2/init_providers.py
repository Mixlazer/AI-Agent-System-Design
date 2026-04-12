"""Register LLM providers and A2A agents in the registry on startup."""
import httpx
import asyncio
import sys

REGISTRY_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8010"


async def main():
    async with httpx.AsyncClient(timeout=10) as client:
        # Register LLM providers
        providers = [
            {
                "name": "openrouter",
                "url": "http://openrouter:8001",
                "models": ["mock-model-a", "mock-model-b"],
                "price_per_token_input": 0.00001,
                "price_per_token_output": 0.00003,
                "rate_limit": 60,
                "priority": 1,
                "weight": 1.0,
            },
            {
                "name": "vllm",
                "url": "http://vllm:8002",
                "models": ["mock-model-a", "mock-model-c"],
                "price_per_token_input": 0.0,
                "price_per_token_output": 0.0,
                "rate_limit": 0,
                "priority": 2,
                "weight": 1.0,
            },
            {
                "name": "ollama",
                "url": "http://ollama:8003",
                "models": ["mock-model-b", "mock-model-c"],
                "price_per_token_input": 0.0,
                "price_per_token_output": 0.0,
                "rate_limit": 0,
                "priority": 3,
                "weight": 1.5,
            },
            {
                "name": "cloud",
                "url": "http://cloud:8004",
                "models": ["mock-model-a", "mock-model-b", "mock-model-c"],
                "price_per_token_input": 0.00005,
                "price_per_token_output": 0.00015,
                "rate_limit": 100,
                "priority": 0,
                "weight": 0.5,
            },
        ]
        for p in providers:
            resp = await client.post(f"{REGISTRY_URL}/llm/providers", json=p)
            print(f"Registered provider {p['name']}: {resp.status_code}")

        # Register sample A2A agents
        agents = [
            {
                "name": "assistant-agent",
                "description": "General-purpose assistant agent",
                "methods": ["chat", "stream"],
                "url": "http://balancer:8000",
                "models": ["mock-model-a", "mock-model-b"],
            },
            {
                "name": "code-agent",
                "description": "Code generation and review agent",
                "methods": ["chat", "generate"],
                "url": "http://balancer:8000",
                "models": ["mock-model-c"],
            },
        ]
        for a in agents:
            resp = await client.post(f"{REGISTRY_URL}/a2a/agents", json=a)
            print(f"Registered agent {a['name']}: {resp.status_code}")


if __name__ == "__main__":
    asyncio.run(main())
