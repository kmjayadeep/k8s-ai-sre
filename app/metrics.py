from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime
from threading import Lock
from typing import Any


_BUCKETS = (0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0)


@dataclass
class _Histogram:
    buckets: tuple[float, ...]
    bucket_counts: list[int]
    count: int = 0
    total: float = 0.0

    @classmethod
    def create(cls, buckets: tuple[float, ...]) -> "_Histogram":
        return cls(buckets=buckets, bucket_counts=[0 for _ in buckets])

    def observe(self, value: float) -> None:
        self.count += 1
        self.total += value
        for idx, bucket in enumerate(self.buckets):
            if value <= bucket:
                self.bucket_counts[idx] += 1


_lock = Lock()
_investigation_started: dict[tuple[str, str, str], deque[float]] = defaultdict(deque)
_action_proposed_at: dict[str, float] = {}
_investigation_latency = _Histogram.create(_BUCKETS)
_approval_latency = _Histogram.create(_BUCKETS)
_proposal_total = 0
_execution_outcomes: dict[str, int] = defaultdict(int)


def _to_ts(fields: dict[str, Any]) -> float:
    ts = fields.get("ts")
    if isinstance(ts, str):
        return datetime.fromisoformat(ts).timestamp()
    return datetime.now().timestamp()


def _observe_histogram(hist: _Histogram, metric: str, lines: list[str]) -> None:
    running = 0
    for bucket, count in zip(hist.buckets, hist.bucket_counts):
        running += count
        lines.append(f'{metric}_bucket{{le="{bucket}"}} {running}')
    lines.append(f'{metric}_bucket{{le="+Inf"}} {hist.count}')
    lines.append(f"{metric}_sum {hist.total}")
    lines.append(f"{metric}_count {hist.count}")


def observe_event(event: str, fields: dict[str, Any]) -> None:
    global _proposal_total
    ts = _to_ts(fields)
    with _lock:
        if event == "investigation_started":
            key = (
                str(fields.get("kind", "")),
                str(fields.get("namespace", "")),
                str(fields.get("name", "")),
            )
            _investigation_started[key].append(ts)
            return

        if event == "investigation_completed":
            key = (
                str(fields.get("kind", "")),
                str(fields.get("namespace", "")),
                str(fields.get("name", "")),
            )
            starts = _investigation_started.get(key)
            if starts:
                started_at = starts.popleft()
                _investigation_latency.observe(max(0.0, ts - started_at))
            return

        if event == "action_proposed":
            _proposal_total += 1
            action_id = fields.get("action_id")
            if isinstance(action_id, str) and action_id:
                _action_proposed_at[action_id] = ts
            return

        if event in {"action_approved", "action_failed", "action_rejected"}:
            status = event.replace("action_", "", 1)
            _execution_outcomes[status] += 1
            action_id = fields.get("action_id")
            if isinstance(action_id, str) and action_id:
                proposed_at = _action_proposed_at.pop(action_id, None)
                if proposed_at is not None:
                    _approval_latency.observe(max(0.0, ts - proposed_at))


def render_prometheus_metrics() -> str:
    with _lock:
        lines: list[str] = [
            "# HELP k8s_ai_sre_action_proposals_total Number of proposed remediation actions.",
            "# TYPE k8s_ai_sre_action_proposals_total counter",
            f"k8s_ai_sre_action_proposals_total {_proposal_total}",
            "# HELP k8s_ai_sre_action_execution_outcomes_total Number of action execution terminal outcomes.",
            "# TYPE k8s_ai_sre_action_execution_outcomes_total counter",
        ]
        for status in ("approved", "failed", "rejected"):
            lines.append(
                f'k8s_ai_sre_action_execution_outcomes_total{{status="{status}"}} {_execution_outcomes.get(status, 0)}'
            )

        lines.extend(
            [
                "# HELP k8s_ai_sre_investigation_latency_seconds Investigation duration in seconds.",
                "# TYPE k8s_ai_sre_investigation_latency_seconds histogram",
            ]
        )
        _observe_histogram(_investigation_latency, "k8s_ai_sre_investigation_latency_seconds", lines)
        lines.extend(
            [
                "# HELP k8s_ai_sre_approval_latency_seconds Latency between action proposal and terminal decision.",
                "# TYPE k8s_ai_sre_approval_latency_seconds histogram",
            ]
        )
        _observe_histogram(_approval_latency, "k8s_ai_sre_approval_latency_seconds", lines)
        lines.append("")
        return "\n".join(lines)


def reset_metrics_for_tests() -> None:
    global _proposal_total, _investigation_latency, _approval_latency
    with _lock:
        _investigation_started.clear()
        _action_proposed_at.clear()
        _execution_outcomes.clear()
        _proposal_total = 0
        _investigation_latency = _Histogram.create(_BUCKETS)
        _approval_latency = _Histogram.create(_BUCKETS)
