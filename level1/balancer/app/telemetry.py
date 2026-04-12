import os
from opentelemetry import metrics, trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource

# Try prometheus reader for local /metrics endpoint
try:
    from opentelemetry.prometheus import PrometheusMetricReader
    _prom_reader = PrometheusMetricReader()
except ImportError:
    _prom_reader = None


def init_telemetry():
    resource = Resource.create({"service.name": "llm-balancer"})

    # Traces
    tracer_provider = TracerProvider(resource=resource)
    otlp_trace = OTLPSpanExporter(
        endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317"),
        insecure=True,
    )
    tracer_provider.add_span_processor(BatchSpanProcessor(otlp_trace))
    trace.set_tracer_provider(tracer_provider)

    # Metrics
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


meter = metrics.get_meter("llm-balancer")

request_counter = meter.create_counter(
    "llm_requests_total",
    description="Total number of LLM requests",
    unit="1",
)

latency_hist = meter.create_histogram(
    "llm_request_latency_seconds",
    description="Request latency in seconds",
    unit="s",
)

active_requests = meter.create_up_down_counter(
    "llm_active_requests",
    description="Currently active LLM requests",
    unit="1",
)
