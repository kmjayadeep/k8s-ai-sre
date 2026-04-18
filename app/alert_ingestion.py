from collections import Counter, deque
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Lock
from typing import Any

from app.metrics import record_alertmanager_ingestion_event

DEFAULT_WINDOW_SIZE = 200
DEFAULT_DEGRADE_THRESHOLD = 0.2
DEFAULT_MIN_SAMPLES = 5


@dataclass(frozen=True)
class IngestionEvent:
    receiver: str
    target: str
    outcome: str
    timestamp: str
    detail: str | None = None


_lock = Lock()
_recent_events: deque[IngestionEvent] = deque(maxlen=DEFAULT_WINDOW_SIZE)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _safe_text(value: str | None, fallback: str = "unknown") -> str:
    candidate = (value or "").strip()
    return candidate or fallback


def record_ingestion_event(receiver: str, target: str, outcome: str, detail: str | None = None) -> None:
    normalized_receiver = _safe_text(receiver)
    normalized_target = _safe_text(target)
    normalized_outcome = _safe_text(outcome)
    event = IngestionEvent(
        receiver=normalized_receiver,
        target=normalized_target,
        outcome=normalized_outcome,
        timestamp=_now_iso(),
        detail=detail,
    )
    with _lock:
        _recent_events.append(event)
    record_alertmanager_ingestion_event(normalized_receiver, normalized_target, normalized_outcome)


def ingestion_status_snapshot(
    *,
    degrade_threshold: float = DEFAULT_DEGRADE_THRESHOLD,
    min_samples: int = DEFAULT_MIN_SAMPLES,
) -> dict[str, Any]:
    with _lock:
        events = list(_recent_events)

    total = len(events)
    failure_events = [event for event in events if event.outcome == "failed"]
    failed = len(failure_events)
    failure_rate = (failed / total) if total else 0.0
    degraded = total >= min_samples and failure_rate >= degrade_threshold

    receiver_counts: Counter[str] = Counter(event.receiver for event in failure_events)
    target_counts: Counter[str] = Counter(event.target for event in failure_events)
    last_failure = failure_events[-1] if failure_events else None

    return {
        "status": "degraded" if degraded else "ok",
        "window_size": total,
        "failed_deliveries": failed,
        "failure_rate": round(failure_rate, 4),
        "degrade_threshold": degrade_threshold,
        "min_samples": min_samples,
        "failed_by_receiver": dict(receiver_counts),
        "failed_by_target": dict(target_counts),
        "last_failure_at": last_failure.timestamp if last_failure else None,
        "last_failure_detail": last_failure.detail if last_failure else None,
    }


def reset_ingestion_state_for_tests() -> None:
    with _lock:
        _recent_events.clear()
