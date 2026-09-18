import logging
import sys

import structlog
from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.trace import get_tracer_provider, set_tracer_provider


def configure_observability(app: FastAPI, service_name: str, log_level: str) -> None:
    logging.basicConfig(format="%(message)s", level=log_level, stream=sys.stdout)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
    )
    if not isinstance(get_tracer_provider(), TracerProvider):
        resource = Resource.create({"service.name": service_name})
        set_tracer_provider(TracerProvider(resource=resource))
    FastAPIInstrumentor.instrument_app(app)
