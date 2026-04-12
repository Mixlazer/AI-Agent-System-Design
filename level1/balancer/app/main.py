import asyncio
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse

from .config import settings
from .balancer import balancer
from .telemetry import init_telemetry, meter, request_counter, latency_hist, active_requests

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

PROVIDER_TIMEOUT = 300.0  # 5 minutes for complex queries


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_telemetry()
    balancer.start_queue_processor()
    logger.info("LLM Balancer started with queue processor")
    yield


app = FastAPI(title="Smart LLM Balancer", lifespan=lifespan)


@app.get("/health")
async def health():
    """Health check with queue statistics"""
    queue_stats = balancer.get_queue_stats()
    return {
        "status": "ok",
        "providers": [p.name for p in balancer.list_providers()],
        "queue_stats": queue_stats,
        "strategy": settings.balancer_strategy
    }


@app.get("/queue/stats")
async def queue_stats():
    """Get detailed queue statistics"""
    return balancer.get_queue_stats()


@app.get("/v1/models")
async def list_models():
    return {"data": [
        {"id": model, "object": "model", "owned_by": provs[0]}
        for model, provs in balancer.list_models().items()
    ]}


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """
    Smart LLM proxy with complexity-based routing.
    
    Routing logic:
    - Complex queries (long prompts, code, analysis) → Priority 0 (most powerful)
    - Medium queries → Priority 1
    - Simple queries → Priority 2 (simplest)
    
    Fallback: If target model busy and queue < 10, use next available.
    Emergency: If queue >= 10, any model can handle any query.
    """
    body = await request.body()
    payload = json.loads(body)
    model = payload.get("model", "")
    stream = payload.get("stream", False)
    
    # Detect complexity from payload
    complexity = balancer.detect_complexity(payload)
    
    # Smart provider selection with complexity-based routing
    provider = await balancer.select_provider(model, payload)
    
    if not provider:
        logger.error(f"No provider available for model: {model}, complexity: {complexity}")
        raise HTTPException(status_code=503, detail=f"No provider available for model: {model}")

    # Log routing decision
    queue_size = balancer.estimate_queue_size()
    logger.info(
        f"[{request.headers.get('x-request-id', uuid.uuid4().hex[:8])}] "
        f"Complexity={complexity} → Provider={provider.name} (priority={provider.priority}, queue={queue_size})"
    )

    url = f"{provider.url}/v1/chat/completions"
    headers = {"Content-Type": "application/json"}
    if provider.api_key:
        headers["Authorization"] = f"Bearer {provider.api_key}"

    start = time.time()
    balancer.track_active_request(provider.name, 1)
    active_requests.add(1, {"provider": provider.name, "model": model, "complexity": complexity})
    request_counter.add(1, {"provider": provider.name, "model": model, "complexity": complexity})

    try:
        async with httpx.AsyncClient(timeout=PROVIDER_TIMEOUT) as client:
            if stream:
                return await _handle_stream(client, url, headers, body, provider, model, start, complexity)
            else:
                resp = await client.post(url, content=body, headers=headers)
                elapsed = time.time() - start
                
                # Log response
                response_data = json.loads(resp.content)
                response_text = response_data.get("choices", [{}])[0].get("message", {}).get("content", "")
                logger.info(
                    f"[{request.headers.get('x-request-id', uuid.uuid4().hex[:8])}] "
                    f"Response received from {provider.name}: {response_text[:100]}... "
                    f"(latency={elapsed:.2f}s)"
                )
                
                latency_hist.record(elapsed, {"provider": provider.name, "model": model, "complexity": complexity})
                active_requests.add(-1, {"provider": provider.name})
                balancer.track_active_request(provider.name, -1)
                
                return Response(
                    content=resp.content,
                    status_code=resp.status_code,
                    media_type=resp.headers.get("content-type", "application/json"),
                )
                
    except httpx.TimeoutException:
        elapsed = time.time() - start
        latency_hist.record(elapsed, {"provider": provider.name, "model": model, "complexity": complexity})
        active_requests.add(-1, {"provider": provider.name})
        balancer.track_active_request(provider.name, -1)
        logger.error(f"Provider {provider.name} timed out after {elapsed:.2f}s")
        raise HTTPException(status_code=504, detail=f"Provider {provider.name} timed out")
        
    except Exception as e:
        elapsed = time.time() - start
        latency_hist.record(elapsed, {"provider": provider.name, "model": model, "complexity": complexity})
        active_requests.add(-1, {"provider": provider.name})
        balancer.track_active_request(provider.name, -1)
        logger.error(f"Error from {provider.name}: {e}")
        raise HTTPException(status_code=502, detail=str(e))


async def _handle_stream(client, url, headers, body, provider, model, start, complexity="medium"):
    req = client.build_request("POST", url, content=body, headers=headers)
    resp = await client.send(req, stream=True)

    async def stream_generator():
        try:
            async for chunk in resp.aiter_bytes():
                yield chunk
        finally:
            elapsed = time.time() - start
            latency_hist.record(elapsed, {"provider": provider.name, "model": model, "complexity": complexity})
            active_requests.add(-1, {"provider": provider.name})
            balancer.track_active_request(provider.name, -1)
            logger.info(f"Stream completed from {provider.name} (latency={elapsed:.2f}s)")
            await resp.aclose()

    return StreamingResponse(
        stream_generator(),
        status_code=resp.status_code,
        media_type=resp.headers.get("content-type", "text/event-stream"),
    )


@app.get("/metrics")
async def metrics():
    from opentelemetry.prometheus import PrometheusMetricReader
    # OTel SDK exports via prometheus reader on its own HTTP server
    return JSONResponse({"status": "metrics served on :9464"})
