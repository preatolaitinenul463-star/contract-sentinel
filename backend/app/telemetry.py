"""OpenTelemetry instrumentation for Contract Sentinel.

Initialises tracing, metrics, and log correlation so that every request
(including SSE pipeline runs) gets a trace_id / run_id that flows through
logs, SSE events, and audit records.

Call ``init_telemetry(app)`` once during FastAPI lifespan startup.
"""

from __future__ import annotations

import os
import uuid
from contextvars import ContextVar
from typing import Optional

from loguru import logger

# ── context‑vars for run_id (our domain concept) ──
_current_run_id: ContextVar[Optional[str]] = ContextVar("current_run_id", default=None)


def new_run_id() -> str:
    """Generate and store a new run_id in the current async context."""
    rid = uuid.uuid4().hex[:16]
    _current_run_id.set(rid)
    return rid


def get_run_id() -> Optional[str]:
    return _current_run_id.get()


def set_run_id(rid: str) -> None:
    _current_run_id.set(rid)


# ── Trace ID helper (works even if OTEL is not installed) ──

def get_trace_id() -> Optional[str]:
    """Return the W3C hex trace‑id of the current span, or None."""
    try:
        from opentelemetry import trace
        span = trace.get_current_span()
        ctx = span.get_span_context()
        if ctx and ctx.trace_id:
            return format(ctx.trace_id, "032x")
    except Exception:
        pass
    return None


# ── Metrics helpers (thin wrappers so callers don't need to import otel) ──

_meter = None


def _get_meter():
    global _meter
    if _meter is not None:
        return _meter
    try:
        from opentelemetry import metrics as otel_metrics
        _meter = otel_metrics.get_meter("sentinel")
    except Exception:
        _meter = None
    return _meter


def record_counter(name: str, value: int = 1, attributes: dict | None = None):
    """Increment a counter metric."""
    meter = _get_meter()
    if meter is None:
        return
    try:
        counter = meter.create_counter(name)
        counter.add(value, attributes or {})
    except Exception:
        pass


def record_histogram(name: str, value: float, attributes: dict | None = None):
    """Record a histogram observation."""
    meter = _get_meter()
    if meter is None:
        return
    try:
        hist = meter.create_histogram(name)
        hist.record(value, attributes or {})
    except Exception:
        pass


# ── Main initialisation ──

def init_telemetry(app):
    """Wire up OpenTelemetry auto‑instrumentation for FastAPI, httpx,
    SQLAlchemy and Redis.  Safe to call even when OTEL packages are
    missing – it will simply log a warning and return."""

    otel_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    if not otel_endpoint:
        logger.info("OTEL_EXPORTER_OTLP_ENDPOINT not set – telemetry disabled")
        return

    try:
        from opentelemetry import trace, metrics as otel_metrics
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        from opentelemetry.sdk.resources import Resource, SERVICE_NAME
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter

        resource = Resource.create({SERVICE_NAME: os.environ.get("OTEL_SERVICE_NAME", "sentinel-backend")})

        # Tracing
        tracer_provider = TracerProvider(resource=resource)
        tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=otel_endpoint, insecure=True)))
        trace.set_tracer_provider(tracer_provider)

        # Metrics
        metric_reader = PeriodicExportingMetricReader(OTLPMetricExporter(endpoint=otel_endpoint, insecure=True), export_interval_millis=15000)
        meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
        otel_metrics.set_meter_provider(meter_provider)

        # Auto‑instrument FastAPI
        try:
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
            FastAPIInstrumentor.instrument_app(app)
        except Exception as e:
            logger.warning(f"FastAPI OTEL instrumentation failed: {e}")

        # Auto‑instrument httpx
        try:
            from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
            HTTPXClientInstrumentor().instrument()
        except Exception as e:
            logger.debug(f"httpx OTEL instrumentation skipped: {e}")

        # Auto‑instrument SQLAlchemy
        try:
            from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
            SQLAlchemyInstrumentor().instrument()
        except Exception as e:
            logger.debug(f"SQLAlchemy OTEL instrumentation skipped: {e}")

        # Auto‑instrument Redis
        try:
            from opentelemetry.instrumentation.redis import RedisInstrumentor
            RedisInstrumentor().instrument()
        except Exception as e:
            logger.debug(f"Redis OTEL instrumentation skipped: {e}")

        logger.info(f"OpenTelemetry initialised → {otel_endpoint}")

    except ImportError as e:
        logger.warning(f"OpenTelemetry packages not installed ({e}) – telemetry disabled")
    except Exception as e:
        logger.error(f"OpenTelemetry init error: {e}")
