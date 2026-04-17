from datetime import datetime
from threading import Lock
from typing import Any

from prometheus_client import Counter, Histogram, CollectorRegistry, generate_latest

BUCKETS = (0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0)

# Module-level registry and metric handles — swapped for test isolation
_registry: CollectorRegistry
_proposals_total: Counter
_execution_outcomes: Counter
_investigation_latency: Histogram
_approval_latency: Histogram
_alertmanager_ingestion_events: Counter
_alertmanager_reconciliation_runs: Counter


def _make_metrics(reg: CollectorRegistry) -> None:
    global _proposals_total, _execution_outcomes, _investigation_latency, _approval_latency
    global _alertmanager_ingestion_events, _alertmanager_reconciliation_runs
    _proposals_total = Counter(
        "k8s_ai_sre_action_proposals_total",
        "Number of proposed remediation actions.",
        registry=reg,
    )
    _execution_outcomes = Counter(
        "k8s_ai_sre_action_execution_outcomes_total",
        "Number of action execution terminal outcomes.",
        ["status"],
        registry=reg,
    )
    _investigation_latency = Histogram(
        "k8s_ai_sre_investigation_latency_seconds",
        "Investigation duration in seconds.",
        buckets=BUCKETS,
        registry=reg,
    )
    _approval_latency = Histogram(
        "k8s_ai_sre_approval_latency_seconds",
        "Latency between action proposal and terminal decision.",
        buckets=BUCKETS,
        registry=reg,
    )
    _alertmanager_ingestion_events = Counter(
        "k8s_ai_sre_alertmanager_ingestion_events_total",
        "Alertmanager ingestion outcomes by receiver and target.",
        ["receiver", "target", "outcome"],
        registry=reg,
    )
    _alertmanager_reconciliation_runs = Counter(
        "k8s_ai_sre_alertmanager_reconciliation_runs_total",
        "Alertmanager reconciliation run outcomes.",
        ["status"],
        registry=reg,
    )


_registry = CollectorRegistry()
_make_metrics(_registry)

_lock = Lock()
_investigation_started: dict[tuple[str, str, str], list[float]] = {}
_action_proposed_at: dict[str, float] = {}


def _to_ts(fields: dict[str, Any]) -> float:
    ts = fields.get("ts")
    if isinstance(ts, str):
        return datetime.fromisoformat(ts).timestamp()
    return datetime.now().timestamp()


def observe_event(event: str, fields: dict[str, Any]) -> None:
    ts = _to_ts(fields)
    with _lock:
        if event == "investigation_started":
            key = (
                str(fields.get("kind", "")),
                str(fields.get("namespace", "")),
                str(fields.get("name", "")),
            )
            if key not in _investigation_started:
                _investigation_started[key] = []
            _investigation_started[key].append(ts)
            return

        if event == "investigation_completed":
            key = (
                str(fields.get("kind", "")),
                str(fields.get("namespace", "")),
                str(fields.get("name", "")),
            )
            starts = _investigation_started.pop(key, [])
            if starts:
                _investigation_latency.observe(max(0.0, ts - starts[0]))
            return

        if event == "action_proposed":
            _proposals_total.inc()
            action_id = fields.get("action_id")
            if isinstance(action_id, str) and action_id:
                _action_proposed_at[action_id] = ts
            return

        if event in {"action_approved", "action_failed", "action_rejected"}:
            status = event.replace("action_", "", 1)
            _execution_outcomes.labels(status=status).inc()
            action_id = fields.get("action_id")
            if isinstance(action_id, str) and action_id:
                proposed_at = _action_proposed_at.pop(action_id, None)
                if proposed_at is not None:
                    _approval_latency.observe(max(0.0, ts - proposed_at))


def record_alertmanager_ingestion_event(receiver: str, target: str, outcome: str) -> None:
    _alertmanager_ingestion_events.labels(
        receiver=(receiver or "unknown"),
        target=(target or "unknown"),
        outcome=(outcome or "unknown"),
    ).inc()


def record_alertmanager_reconciliation_run(status: str) -> None:
    _alertmanager_reconciliation_runs.labels(status=(status or "unknown")).inc()


def render_prometheus_metrics() -> bytes:
    return generate_latest(_registry)


def reset_metrics_for_tests() -> None:
    """Swap to a fresh registry with new metric handles, clearing all accumulated state."""
    global _registry, _investigation_started, _action_proposed_at
    _investigation_started.clear()
    _action_proposed_at.clear()
    _registry = CollectorRegistry()
    _make_metrics(_registry)
