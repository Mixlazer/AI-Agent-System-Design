from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List

from .guardrails import check_guardrails, GuardrailResult


class CheckRequest(BaseModel):
    text: str


class CheckResponse(BaseModel):
    safe: bool
    violations: List[str]
    sanitized_content: str


app = FastAPI(title="Guardrails Service")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/check", response_model=CheckResponse)
async def check(req: CheckRequest):
    result = check_guardrails(req.text)
    return CheckResponse(
        safe=result.safe,
        violations=result.violations,
        sanitized_content=result.sanitized_content,
    )
