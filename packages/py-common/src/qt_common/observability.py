from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def build_tracer_provider(service_name: str) -> TracerProvider:
    resource = Resource.create({SERVICE_NAME: service_name})
    return TracerProvider(resource=resource)


def initialize_tracing(
    service_name: str,
    exporter_endpoint: str | None = None,
) -> TracerProvider:
    provider = build_tracer_provider(service_name)
    if exporter_endpoint is not None:
        exporter = OTLPSpanExporter(endpoint=exporter_endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    return provider
