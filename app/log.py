import json
import sys
from datetime import UTC, datetime

from loguru import logger

from app.metrics import observe_event


logger.remove()
logger.add(sys.stdout, format="{message}")


def log_event(event: str, **fields: object) -> None:
    payload = {
        "ts": datetime.now(UTC).isoformat(),
        "event": event,
        **fields,
    }
    observe_event(event, payload)
    logger.info(json.dumps(payload, sort_keys=True))
