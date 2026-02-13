try:
    from genxai_enterprise.observability.metrics import (
        get_prometheus_metrics,
        record_workflow_execution,
    )
except Exception:  # pragma: no cover - fallback for missing enterprise package
    def get_prometheus_metrics() -> bytes:
        return b"# enterprise metrics unavailable\n"

    def record_workflow_execution(*_args, **_kwargs) -> None:
        return None


def export_metrics() -> bytes:
    return get_prometheus_metrics()


def record_planning_run(duration: float, status: str = "success") -> None:
    record_workflow_execution("travel_planning", duration, status)
