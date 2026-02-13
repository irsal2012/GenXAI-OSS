"""Enterprise metrics adapter."""

try:
    from genxai_enterprise.observability.metrics import record_workflow_execution
except Exception:  # pragma: no cover - fallback for missing enterprise package
    def record_workflow_execution(*_args, **_kwargs) -> None:
        return None

from app.application.services.brainstorm_service import MetricsRecorder


class EnterpriseMetricsRecorder(MetricsRecorder):
    """Adapter for genxai_enterprise metrics."""

    def record(self, workflow_name: str, duration: float, status: str) -> None:
        record_workflow_execution(workflow_name, duration, status)