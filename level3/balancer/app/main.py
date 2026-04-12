import asyncio
import json
import time
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, Response, HTTPException, Query
from fastapi.responses import StreamingResponse, JSONResponse

from .config import REGISTRY_URL, PROVIDER_TIMEOUT, GUARDRAILS_URL, AUTH_URL
from .router import balancer
from .telemetry import (
    init_telemetry, request_counter, latency_hist,
    active_requests, ttft_hist, tpot_hist,
    token_input_counter, token_output_counter, cost_counter,
    guardrail_rejections,
)
from .mlflow_tracer import init_mlflow, trace_request

SYNC_INTERVAL = 10


# ── Auth Middleware ────────────────────────────────────────

async def _verify_token(request: Request) -> dict:
    """Verify token with auth service. Returns token info or raises 401."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header:
        raise HTTPException(401, "Missing Authorization header")

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(
                f"{AUTH_URL}/verify",
                headers={"Authorization": auth_header},
            )
            if resp.status_code != 200:
                raise HTTPException(401, "Invalid or expired token")
            return resp.json()
        except httpx.ConnectError:
            raise HTTPException(503, "Auth service unavailable")


def _require_scope(token_info: dict, scope: str):
    scopes = token_info.get("scopes", [])
    if scope not in scopes and "admin" not in scopes:
        raise HTTPException(403, f"Missing scope: {scope}")


# ── Guardrails Check ──────────────────────────────────────

async def _check_guardrails(text: str) -> dict:
    """Check text against guardrails service."""
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.post(
                f"{GUARDRAILS_URL}/check",
                json={"text": text},
            )
            if resp.status_code == 200:
                return resp.json()
        except httpx.ConnectError:
            pass
    # If guardrails is down, allow by default
    return {"safe": True, "violations": [], "sanitized_content": text}


# ── Provider Sync ─────────────────────────────────────────

async def _sync_providers():
    async with httpx.AsyncClient(timeout=10) as client:
        while True:
            try:
                resp = await client.get(f"{REGISTRY_URL}/llm/providers")
                if resp.status_code == 200:
                    await balancer.update_providers(resp.json())
            except Exception:
                pass
            await asyncio.sleep(SYNC_INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_telemetry()
    init_mlflow()
    task = asyncio.create_task(_sync_providers())
    yield
    task.cancel()


app = FastAPI(title="LLM Balancer V3 — Guardrails + Auth", lifespan=lifespan)


@app.get("/health")
async def health():
    providers = balancer.list_providers()
    return {
        "status": "ok",
        "providers": [{"name": p.name, "healthy": p.healthy, "avg_latency": p.avg_latency} for p in providers],
    }


@app.get("/v1/models")
async def list_models(request: Request):
    token_info = await _verify_token(request)
    _require_scope(token_info, "llm:read")

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(f"{REGISTRY_URL}/llm/providers")
            providers = resp.json()
        except Exception:
            providers = []
    models_set = set()
    for p in providers:
        for m in p.get("models", []):
            models_set.add(m)
    return {"data": [{"id": m, "object": "model"} for m in models_set]}


@app.post("/v1/chat/completions")
async def chat_completions(
    request: Request,
    strategy: str = Query("latency", description="round_robin|weighted|latency|health"),
):
    # Auth check
    token_info = await _verify_token(request)
    _require_scope(token_info, "llm:write")

    body = await request.body()
    payload = json.loads(body)
    model = payload.get("model", "")
    stream = payload.get("stream", False)
    messages = payload.get("messages", [])

    # Guardrails: check all user messages
    for msg in messages:
        if msg.get("role") == "user":
            gr_result = await _check_guardrails(msg.get("content", ""))
            if not gr_result.get("safe", True):
                guardrail_rejections.add(1, {"provider": "guardrail", "model": model})
                violations = gr_result.get("violations", [])
                trace_request("guardrail", model, 0, success=False,
                              guardrail_violations=violations, strategy=strategy)
                raise HTTPException(
                    status_code=422,
                    detail={"message": "Request blocked by guardrails", "violations": violations},
                )
            # Replace with sanitized content if secrets were found
            if gr_result.get("sanitized_content") != msg.get("content", ""):
                msg["content"] = gr_result["sanitized_content"]

    # Re-serialize potentially modified payload
    body = json.dumps(payload).encode()

    provider = await balancer.select_provider(model, strategy=strategy)
    if not provider:
        raise HTTPException(status_code=404, detail=f"No provider for model: {model}")

    url = f"{provider.url}/v1/chat/completions"
    headers = {"Content-Type": "application/json"}
    if provider.api_key:
        headers["Authorization"] = f"Bearer {provider.api_key}"

    start = time.time()
    active_requests.add(1, {"provider": provider.name})
    request_counter.add(1, {"provider": provider.name, "model": model, "strategy": strategy})

    try:
        async with httpx.AsyncClient(timeout=PROVIDER_TIMEOUT) as client:
            if stream:
                return await _handle_stream(client, url, headers, body, provider, model, start, strategy)
            else:
                resp = await client.post(url, content=body, headers=headers)
                elapsed = time.time() - start
                latency_hist.record(elapsed, {"provider": provider.name, "model": model})
                active_requests.add(-1, {"provider": provider.name})

                resp_data = resp.json() if resp.status_code == 200 else {}
                usage = resp_data.get("usage", {})
                in_tok = usage.get("prompt_tokens", 0)
                out_tok = usage.get("completion_tokens", 0)
                token_input_counter.add(in_tok, {"provider": provider.name, "model": model})
                token_output_counter.add(out_tok, {"provider": provider.name, "model": model})
                ttft_hist.record(elapsed, {"provider": provider.name, "model": model})
                if out_tok > 0:
                    tpot_hist.record(elapsed / out_tok, {"provider": provider.name, "model": model})
                cost = in_tok * provider.price_per_token_input + out_tok * provider.price_per_token_output
                cost_counter.add(cost, {"provider": provider.name, "model": model})

                await balancer.record_success(provider.name, elapsed)
                trace_request(
                    provider.name, model, elapsed,
                    ttft=elapsed, input_tokens=in_tok, output_tokens=out_tok,
                    cost=cost, success=True, strategy=strategy,
                )
                return Response(content=resp.content, status_code=resp.status_code,
                                media_type=resp.headers.get("content-type", "application/json"))
    except httpx.TimeoutException:
        elapsed = time.time() - start
        latency_hist.record(elapsed, {"provider": provider.name, "model": model})
        active_requests.add(-1, {"provider": provider.name})
        await balancer.record_error(provider.name)
        trace_request(provider.name, model, elapsed, success=False, strategy=strategy)
        raise HTTPException(status_code=504, detail=f"Provider {provider.name} timed out")
    except Exception as e:
        elapsed = time.time() - start
        latency_hist.record(elapsed, {"provider": provider.name, "model": model})
        active_requests.add(-1, {"provider": provider.name})
        await balancer.record_error(provider.name)
        trace_request(provider.name, model, elapsed, success=False, strategy=strategy)
        raise HTTPException(status_code=502, detail=str(e))


async def _handle_stream(client, url, headers, body, provider, model, start, strategy):
    req = client.build_request("POST", url, content=body, headers=headers)
    resp = await client.send(req, stream=True)

    async def stream_generator():
        first_token = True
        output_tokens = 0
        try:
            async for line in resp.aiter_lines():
                if line.startswith("data: ") and line != "data: [DONE]":
                    try:
                        chunk = json.loads(line[6:])
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        if delta.get("content"):
                            if first_token:
                                ttft_hist.record(time.time() - start, {"provider": provider.name, "model": model})
                                first_token = False
                            output_tokens += 1
                    except json.JSONDecodeError:
                        pass
                yield line + "\n\n"
                if line == "data: [DONE]":
                    break
        finally:
            elapsed = time.time() - start
            latency_hist.record(elapsed, {"provider": provider.name, "model": model})
            active_requests.add(-1, {"provider": provider.name})
            token_output_counter.add(output_tokens, {"provider": provider.name, "model": model})
            if output_tokens > 0:
                tpot_hist.record(elapsed / output_tokens, {"provider": provider.name, "model": model})
            cost = output_tokens * provider.price_per_token_output
            cost_counter.add(cost, {"provider": provider.name, "model": model})
            await balancer.record_success(provider.name, elapsed)
            trace_request(provider.name, model, elapsed, output_tokens=output_tokens,
                          cost=cost, success=True, strategy=strategy)
            await resp.aclose()

    return StreamingResponse(stream_generator(), status_code=resp.status_code,
                             media_type="text/event-stream")


@app.get("/balancer/providers")
async def list_balancer_providers(request: Request):
    token_info = await _verify_token(request)
    _require_scope(token_info, "llm:read")
    providers = balancer.list_providers()
    return [{"name": p.name, "healthy": p.healthy, "avg_latency": p.avg_latency,
             "total_requests": p.total_requests, "total_errors": p.total_errors,
             "consecutive_errors": p.consecutive_errors} for p in providers]
