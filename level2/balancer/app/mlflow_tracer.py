"""MLFlow tracing integration for Agent and LLM calls."""
import os
import time
from typing import Optional

try:
    import mlflow
    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False


def init_mlflow():
    if not MLFLOW_AVAILABLE:
        return
    tracking_uri = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment("llm-balancer-traces")


def trace_request(
    provider_name: str,
    model: str,
    latency: float,
    ttft: Optional[float] = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cost: float = 0.0,
    success: bool = True,
    strategy: str = "",
):
    if not MLFLOW_AVAILABLE:
        return
    try:
        with mlflow.start_span(name=f"llm_call_{provider_name}") as span:
            span.set_attributes({
                "provider": provider_name,
                "model": model,
                "latency": latency,
                "ttft": ttft or 0.0,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost": cost,
                "success": success,
                "strategy": strategy,
            })
    except Exception:
        pass  # don't fail requests due to tracing issues
