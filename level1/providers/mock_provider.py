"""Universal mock LLM provider supporting OpenRouter, vLLM, Ollama, Cloud styles."""
import asyncio
import json
import time
import uuid
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse

PROVIDER_NAME = "mock"
DEFAULT_DELAY = 0.1

app = FastAPI(title=f"Mock LLM Provider - {PROVIDER_NAME}")


@app.get("/health")
async def health():
    return {"status": "ok", "provider": PROVIDER_NAME}


@app.get("/v1/models")
async def list_models():
    return {"data": [
        {"id": "mock-model-a", "object": "model", "owned_by": PROVIDER_NAME},
        {"id": "mock-model-b", "object": "model", "owned_by": PROVIDER_NAME},
    ]}


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    model = body.get("model", "mock-model-a")
    messages = body.get("messages", [])
    stream = body.get("stream", False)
    delay = float(body.get("temperature", 0.1)) * 0.5 + DEFAULT_DELAY

    last_msg = messages[-1]["content"] if messages else "Hello"

    if stream:
        return await _stream_response(model, last_msg, delay)
    else:
        await asyncio.sleep(delay)
        return JSONResponse({
            "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
            "object": "chat.completion",
            "model": model,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": f"[{PROVIDER_NAME}] Response to: {last_msg}"},
                "finish_reason": "stop"
            }],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
        })


async def _stream_response(model, content, delay):
    async def generate():
        words = f"[{PROVIDER_NAME}] Stream: {content}".split()
        for i, word in enumerate(words):
            chunk = {
                "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
                "object": "chat.completion.chunk",
                "model": model,
                "choices": [{
                    "index": 0,
                    "delta": {"content": word + " "},
                    "finish_reason": None if i < len(words) - 1 else "stop"
                }]
            }
            yield f"data: {json.dumps(chunk)}\n\n"
            await asyncio.sleep(delay / max(len(words), 1))
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8001
    uvicorn.run(app, host="0.0.0.0", port=port)
