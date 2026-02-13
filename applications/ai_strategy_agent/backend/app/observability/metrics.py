"""Metrics export entrypoint."""

try:
    from genxai_enterprise.observability.metrics import get_prometheus_metrics
except Exception:  # pragma: no cover - fallback for missing enterprise package
    def get_prometheus_metrics() -> bytes:
        return b"# enterprise metrics unavailable\n"


def export_metrics() -> bytes:
    return get_prometheus_metrics()