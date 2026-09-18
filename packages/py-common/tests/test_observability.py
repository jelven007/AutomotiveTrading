from opentelemetry.sdk.resources import SERVICE_NAME
from qt_common.observability import build_tracer_provider


def test_tracer_provider_contains_service_identity() -> None:
    provider = build_tracer_provider("strategy")

    assert provider.resource.attributes[SERVICE_NAME] == "strategy"
