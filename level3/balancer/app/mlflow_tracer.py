"""MLFlow tracing integration."""
import os

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
    provider_name: str, model: str, latency: float,
    ttft=None, input_tokens=0, output_tokens=0,
    cost=0.0, success=True, strategy="",
    guardrail_violations=None,
):
    if not MLFLOW_AVAILABLE:
        return
    try:
        with mlflow.start_span(name=f"llm_call_{provider_name}") as span:
            attrs = {
                "provider": provider_name,
                "model": model,
                "latency": latency,
                "ttft": ttft or 0.0,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost": cost,
                "success": success,
                "strategy": strategy,
            }
            if guardrail_violations:
                attrs["guardrail_violations"] = ",".join(guardrail_violations)
            span.set_attributes(attrs)
    except Exception:
        pass
