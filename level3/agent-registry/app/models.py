from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class SupportedMethod(BaseModel):
    name: str
    description: str
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None


class AgentCardCreate(BaseModel):
    name: str
    description: str
    version: str = "1.0.0"
    supported_methods: List[SupportedMethod] = []
    endpoint_url: str
    health_endpoint: str = "/health"
    tags: List[str] = []


class AgentCard(AgentCardCreate):
    agent_id: str = Field(default_factory=lambda: str(uuid4()))
    registered_at: datetime = Field(default_factory=datetime.utcnow)
    last_heartbeat: Optional[datetime] = None
    status: str = "unknown"
