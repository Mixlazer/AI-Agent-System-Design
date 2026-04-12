"""Authorization service with token-based auth for agents and LLM access."""
import hashlib
import secrets
import time
from typing import Dict, Optional, List

from fastapi import FastAPI, HTTPException, Depends, Request
from pydantic import BaseModel
from datetime import datetime


class TokenInfo(BaseModel):
    token: str
    name: str
    scopes: List[str]  # e.g. ["agent:read", "llm:write", "admin"]
    created_at: str = ""
    expires_at: Optional[str] = None


class CreateTokenRequest(BaseModel):
    name: str
    scopes: List[str] = ["agent:read", "llm:write"]
    ttl_seconds: int = 86400  # 24h default


# In-memory token store (use DB in production)
_tokens: Dict[str, TokenInfo] = {}

# Pre-generate an admin token
_admin_token = secrets.token_hex(32)
_tokens[_admin_token] = TokenInfo(
    token=_admin_token,
    name="admin",
    scopes=["admin", "agent:read", "agent:write", "llm:read", "llm:write"],
    created_at=str(datetime.utcnow()),
)


app = FastAPI(title="Auth Service")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/tokens", response_model=TokenInfo)
async def create_token(req: CreateTokenRequest, request: Request):
    """Create a new token. Requires admin scope."""
    caller = _authenticate(request)
    if "admin" not in caller.scopes:
        raise HTTPException(403, "Only admin can create tokens")

    token = secrets.token_hex(32)
    now = datetime.utcnow()
    expires = None
    if req.ttl_seconds > 0:
        from datetime import timedelta
        expires = str(now + timedelta(seconds=req.ttl_seconds))

    info = TokenInfo(
        token=token,
        name=req.name,
        scopes=req.scopes,
        created_at=str(now),
        expires_at=expires,
    )
    _tokens[token] = info
    return info


@app.get("/tokens")
async def list_tokens(request: Request):
    caller = _authenticate(request)
    if "admin" not in caller.scopes:
        raise HTTPException(403, "Admin only")
    return list(_tokens.values())


@app.delete("/tokens/{token}")
async def revoke_token(token: str, request: Request):
    caller = _authenticate(request)
    if "admin" not in caller.scopes:
        raise HTTPException(403, "Admin only")
    if token not in _tokens:
        raise HTTPException(404, "Token not found")
    del _tokens[token]
    return {"status": "revoked"}


@app.get("/verify")
async def verify_token(request: Request):
    """Verify the caller's token and return its info."""
    caller = _authenticate(request)
    return {"name": caller.name, "scopes": caller.scopes}


def _authenticate(request: Request) -> TokenInfo:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
    else:
        token = auth

    info = _tokens.get(token)
    if not info:
        raise HTTPException(401, "Invalid token")

    if info.expires_at:
        exp = datetime.fromisoformat(info.expires_at)
        if datetime.utcnow() > exp:
            del _tokens[token]
            raise HTTPException(401, "Token expired")

    return info


def require_scope(scope: str):
    """Dependency factory for requiring a specific scope."""
    def _check(request: Request):
        caller = _authenticate(request)
        if scope not in caller.scopes and "admin" not in caller.scopes:
            raise HTTPException(403, f"Missing scope: {scope}")
        return caller
    return _check


@app.on_event("startup")
def _print_admin_token():
    print(f"\n🔑 Admin token: {_admin_token}\n")
