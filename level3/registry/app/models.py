from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum


class AgentMethod(str, Enum):
    chat = "chat"
    generate = "generate"
    embed = "embed"
    stream = "stream"


class AgentCard(BaseModel):
    name: str = Field(..., description="Unique agent name")
    description: str = ""
    methods: List[AgentMethod] = [AgentMethod.chat]
    url: str = ""
    models: List[str] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)


class LLMProviderRegistration(BaseModel):
    name: str
    url: str
    api_key: str = ""
    models: List[str] = []
    price_per_token_input: float = 0.0
    price_per_token_output: float = 0.0
    rate_limit: int = 0
    priority: int = 0
    weight: float = 1.0


class LLMProviderInfo(LLMProviderRegistration):
    healthy: bool = True
    avg_latency: float = 0.0
    total_requests: int = 0
    total_errors: int = 0
    last_error_time: Optional[datetime] = None
    registered_at: datetime = Field(default_factory=datetime.utcnow)
