import os
from opentelemetry import metrics, trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource

try:
    from opentelemetry.prometheus import PrometheusMetricReader
    _prom_reader = PrometheusMetricReader()
except ImportError:
    _prom_reader = None


def init_telemetry():
    resource = Resource.create({"service.name": "llm-balancer-v3"})

    tracer_provider = TracerProvider(resource=resource)
    otlp_trace = OTLPSpanExporter(
        endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317"),
        insecure=True,
    )
    tracer_provider.add_span_processor(BatchSpanProcessor(otlp_trace))
    trace.set_tracer_provider(tracer_provider)

    readers = []
    otlp_metric = OTLPMetricExporter(
        endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317"),
        insecure=True,
    )
    readers.append(PeriodicExportingMetricReader(otlp_metric, export_interval_millis=10000))
    if _prom_reader:
        readers.append(_prom_reader)

    meter_provider = MeterProvider(resource=resource, metric_readers=readers)
    metrics.set_meter_provider(meter_provider)


meter = metrics.get_meter("llm-balancer-v3")

request_counter = meter.create_counter("llm_requests_total", description="Total LLM requests", unit="1")
latency_hist = meter.create_histogram("llm_request_latency_seconds", description="Request latency", unit="s")
active_requests = meter.create_up_down_counter("llm_active_requests", description="Active requests", unit="1")
ttft_hist = meter.create_histogram("llm_ttft_seconds", description="Time to first token", unit="s")
tpot_hist = meter.create_histogram("llm_tpot_seconds", description="Time per output token", unit="s")
token_input_counter = meter.create_counter("llm_input_tokens_total", description="Total input tokens", unit="1")
token_output_counter = meter.create_counter("llm_output_tokens_total", description="Total output tokens", unit="1")
cost_counter = meter.create_counter("llm_request_cost_total", description="Total cost", unit="1")
guardrail_rejections = meter.create_counter("llm_guardrail_rejections_total", description="Guardrail rejections", unit="1")
