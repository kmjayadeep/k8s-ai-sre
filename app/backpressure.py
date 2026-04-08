from asyncio import Queue, QueueEmpty, QueueFull
from datetime import datetime, UTC
from threading import Lock
from typing import Any

from app.log import log_event


# Queueing and backpressure configuration
MAX_QUEUE_SIZE = 50
MAX_CONCURRENT_INVESTIGATIONS = 5

# Module-level state
_investigation_queue: Queue[tuple[str, str, str, str]] | None = None
_investigation_locks: dict[str, Lock] = {}
_investigation_locks_lock = Lock()
_active_investigations: dict[str, datetime] = {}
_active_investigations_lock = Lock()


def _get_queue() -> Queue[tuple[str, str, str, str]]:
    global _investigation_queue
    if _investigation_queue is None:
        _investigation_queue = Queue(maxsize=MAX_QUEUE_SIZE)
    return _investigation_queue


def _get_investigation_lock(kind: str, namespace: str, name: str) -> Lock:
    key = f"{namespace}/{kind}/{name}"
    with _investigation_locks_lock:
        if key not in _investigation_locks:
            _investigation_locks[key] = Lock()
        return _investigation_locks[key]


def _is_investigation_active(kind: str, namespace: str, name: str) -> bool:
    key = f"{namespace}/{kind}/{name}"
    with _active_investigations_lock:
        return key in _active_investigations


def _mark_investigation_active(kind: str, namespace: str, name: str) -> None:
    key = f"{namespace}/{kind}/{name}"
    with _active_investigations_lock:
        _active_investigations[key] = datetime.now(UTC)


def _mark_investigation_done(kind: str, namespace: str, name: str) -> None:
    key = f"{namespace}/{kind}/{name}"
    with _active_investigations_lock:
        _active_investigations.pop(key, None)


def enqueue_investigation(kind: str, namespace: str, name: str) -> tuple[bool, str]:
    """
    Enqueue an investigation request for backpressure.
    
    Returns:
        (True, "queued") if enqueued successfully
        (False, "active") if investigation for this target is already running
        (False, "queue_full") if queue is full
    """
    if _is_investigation_active(kind, namespace, name):
        log_event("investigation_backpressure", kind=kind, namespace=namespace, name=name, reason="already_active")
        return False, "active"

    try:
        _get_queue().put_nowait((kind, namespace, name, datetime.now(UTC).isoformat()))
        log_event("investigation_queued", kind=kind, namespace=namespace, name=name)
        return True, "queued"
    except QueueFull:
        log_event("investigation_backpressure", kind=kind, namespace=namespace, name=name, reason="queue_full")
        return False, "queue_full"


def get_queue_depth() -> int:
    """Return current number of queued investigation requests."""
    return _get_queue().qsize()


def get_active_investigation_count() -> int:
    """Return current number of active investigations."""
    with _active_investigations_lock:
        return len(_active_investigations)


def get_queue_status() -> dict[str, Any]:
    """Return current queue and backpressure status."""
    return {
        "queue_depth": get_queue_depth(),
        "max_queue_size": MAX_QUEUE_SIZE,
        "active_investigations": get_active_investigation_count(),
        "max_concurrent_investigations": MAX_CONCURRENT_INVESTIGATIONS,
        "queue_utilization": get_queue_depth() / MAX_QUEUE_SIZE if MAX_QUEUE_SIZE > 0 else 0,
    }


def _reset_queue() -> None:
    """Reset the queue (for testing purposes)."""
    global _investigation_queue
    _investigation_queue = None
