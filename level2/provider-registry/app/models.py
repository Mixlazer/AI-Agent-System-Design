from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class ProviderCreate(BaseModel):
    name: str
    provider_type: str
    base_url: str
    api_key: Optional[str] = None
    models: List[str] = []
    price_per_input_token: float = 0.0
    price_per_output_token: float = 0.0
    rate_limit_rpm: int = 60
    rate_limit_tpm: int = 100000
    priority: int = 1
    weight: float = 1.0
    timeout_seconds: int = 120
    max_retries: int = 3


class Provider(ProviderCreate):
    provider_id: str = Field(default_factory=lambda: str(uuid4()))
    status: str = "healthy"
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    error_rate: float = 0.0
    registered_at: datetime = Field(default_factory=datetime.utcnow)
    last_health_check: Optional[datetime] = None
