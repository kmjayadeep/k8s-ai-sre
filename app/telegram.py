import json
import os
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

from app.actions import approve_action, reject_action
from app.log import log_event
from app.stores import get_incident, is_action_expired, list_actions_for_incident


TELEGRAM_OFFSET_PATH = Path("/tmp/k8s-ai-sre-telegram-offset.json")


def _telegram_token() -> str | None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    return token or None


def _allowed_chat_ids() -> set[str]:
    return {item.strip() for item in os.getenv("TELEGRAM_ALLOWED_CHAT_IDS", "").split(",") if item.strip()}


def _load_offset() -> int | None:
    if not TELEGRAM_OFFSET_PATH.exists():
        return None
    payload = json.loads(TELEGRAM_OFFSET_PATH.read_text(encoding="utf-8"))
    return payload.get("offset")


def _save_offset(offset: int) -> None:
    TELEGRAM_OFFSET_PATH.write_text(json.dumps({"offset": offset}, indent=2), encoding="utf-8")


def _telegram_api(method: str, data: dict[str, str] | None = None) -> dict:
    token = _telegram_token()
    if not token:
        raise RuntimeError("Telegram is not configured. Set TELEGRAM_BOT_TOKEN.")
    url = f"https://api.telegram.org/bot{token}/{method}"
    encoded = None
    if data is not None:
        encoded = urllib.parse.urlencode(data).encode("utf-8")
    request = urllib.request.Request(url, data=encoded, method="POST" if data else "GET")
    timeout_seconds = float(os.getenv("TELEGRAM_HTTP_TIMEOUT_SECONDS", "35"))
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def _send_message(chat_id: str, text: str) -> str:
    body = _telegram_api("sendMessage", {"chat_id": chat_id, "text": text[:4000]})
    if not body.get("ok"):
        return f"Failed to send Telegram reply: {body}"
    return "Telegram reply sent."


def _format_incident(incident: dict[str, object]) -> str:
    lines = [
        f"Incident {incident.get('incident_id', 'unknown')}",
        f"Target: {incident.get('kind')} {incident.get('namespace')}/{incident.get('name')}",
        f"Answer:\n{incident.get('answer', 'No answer stored.')[:2400]}",
    ]
    actions = _incident_actions(incident)
    if actions:
        lines.append("Actions:")
        for action in actions[:4]:
            lines.append(_format_action_line(action))
            if action.get("status") == "pending" and not is_action_expired(action):
                lines.append(f"  approve: /approve {action.get('id')}")
                lines.append(f"  reject: /reject {action.get('id')}")
    else:
        lines.append("Actions:\n- none")
    return "\n".join(lines)


def _format_status(incident: dict[str, object]) -> str:
    lines = [
        f"Incident {incident.get('incident_id', 'unknown')}\n"
        f"Target: {incident.get('kind')} {incident.get('namespace')}/{incident.get('name')}\n"
        f"Source: {incident.get('source', 'manual')}\n"
        f"Notification: {incident.get('notification_status', 'unknown')}"
    ]
    actions = _incident_actions(incident)
    if actions:
        lines.append("Actions:")
        lines.extend(_format_action_line(action) for action in actions[:5])
    else:
        lines.append("Actions: none")
    return "\n".join(lines)


def _incident_actions(incident: dict[str, object]) -> list[dict[str, object]]:
    incident_id = str(incident.get("incident_id", "")).strip()
    if not incident_id:
        return []

    live_actions = list_actions_for_incident(incident_id)
    if live_actions:
        return sorted(live_actions, key=lambda action: str(action.get("id", "")))

    incident_actions = incident.get("actions", [])
    fallback_actions: list[dict[str, object]] = []
    if isinstance(incident_actions, list):
        for action in incident_actions:
            if not isinstance(action, dict):
                continue
            fallback_actions.append(
                {
                    "id": action.get("action_id", action.get("id", "unknown")),
                    "type": action.get("action_type", action.get("type", "unknown")),
                    "namespace": action.get("namespace", "unknown"),
                    "name": action.get("name", "unknown"),
                    "status": action.get("status", "pending"),
                    "expires_at": action.get("expires_at"),
                }
            )
    if fallback_actions:
        return sorted(fallback_actions, key=lambda action: str(action.get("id", "")))

    proposed_actions = incident.get("proposed_actions", [])
    fallback_actions = []
    for action in proposed_actions:
        if not isinstance(action, dict):
            continue
        fallback_actions.append(
            {
                "id": action.get("action_id", "unknown"),
                "type": action.get("action_type", "unknown"),
                "namespace": action.get("namespace", "unknown"),
                "name": action.get("name", "unknown"),
                "status": "pending",
            }
        )
    return fallback_actions


def _format_action_line(action: dict[str, object]) -> str:
    status = str(action.get("status", "unknown"))
    if status == "pending" and is_action_expired(action):
        status = "expired"
    return f"- {action.get('id')}: {action.get('type')} {action.get('namespace')}/{action.get('name')} [{status}]"


def _handle_command(text: str) -> str:
    parts = text.strip().split(maxsplit=1)
    command = parts[0] if parts else ""
    if "@" in command:
        command = command.split("@", 1)[0]
    argument = parts[1] if len(parts) > 1 else ""

    if command == "/incident" and argument:
        incident = get_incident(argument)
        if incident is None:
            return f"Incident {argument} not found."
        return _format_incident(incident)

    if command == "/status" and argument:
        incident = get_incident(argument)
        if incident is None:
            return f"Incident {argument} not found."
        return _format_status(incident)

    if command == "/approve" and argument:
        return approve_action(argument)

    if command == "/reject" and argument:
        return reject_action(argument)

    return "Commands: /incident <incident-id>, /status <incident-id>, /approve <action-id>, /reject <action-id>"


def poll_telegram_updates_once() -> str:
    token = _telegram_token()
    if not token:
        return "Telegram is not configured. Set TELEGRAM_BOT_TOKEN."

    offset = _load_offset()
    query = {}
    if offset is not None:
        query["offset"] = str(offset)
    query["timeout"] = os.getenv("TELEGRAM_POLL_TIMEOUT_SECONDS", "30")
    url_suffix = "getUpdates"
    if query:
        url_suffix += "?" + urllib.parse.urlencode(query)
    body = _telegram_api(url_suffix)
    if not body.get("ok"):
        return f"Failed to fetch Telegram updates: {body}"

    results = body.get("result", [])
    if not results:
        return "No new Telegram updates."

    handled = 0
    for update in results:
        update_id = update.get("update_id")
        if update_id is not None:
            _save_offset(update_id + 1)
        message = update.get("message", {})
        chat = message.get("chat", {})
        text = message.get("text", "").strip()
        chat_id = str(chat.get("id", ""))
        allowed_chat_ids = _allowed_chat_ids()
        if allowed_chat_ids and chat_id not in allowed_chat_ids:
            continue
        if not chat_id or not text.startswith("/"):
            continue
        log_event("telegram_command_received", chat_id=chat_id, text=text)
        try:
            reply = _handle_command(text)
        except Exception as exc:
            log_event("telegram_command_failed", chat_id=chat_id, text=text, error=str(exc))
            reply = f"Command failed: {exc}"
        _send_message(chat_id, reply)
        handled += 1

    log_event("telegram_poll_processed", handled=handled)
    return f"Processed {handled} Telegram command(s)."


def poll_telegram_updates_forever(stop_event: threading.Event | None = None) -> None:
    poll_interval = float(os.getenv("TELEGRAM_POLL_INTERVAL_SECONDS", "1"))
    backoff_seconds = float(os.getenv("TELEGRAM_POLL_BACKOFF_SECONDS", "5"))
    log_event("telegram_poll_loop_started")

    while stop_event is None or not stop_event.is_set():
        try:
            result = poll_telegram_updates_once()
            log_event("telegram_poll_loop_tick", result=result)
        except Exception as exc:
            log_event("telegram_poll_loop_failed", error=str(exc))
            time.sleep(backoff_seconds)
            continue

        if stop_event is not None and stop_event.is_set():
            break
        time.sleep(poll_interval)

    log_event("telegram_poll_loop_stopped")


def start_telegram_polling_thread() -> threading.Thread | None:
    if not _telegram_token():
        log_event("telegram_poll_not_started", reason="token_missing")
        return None
    if os.getenv("TELEGRAM_POLL_ENABLED", "true").lower() not in {"1", "true", "yes", "on"}:
        log_event("telegram_poll_not_started", reason="disabled")
        return None

    thread = threading.Thread(target=poll_telegram_updates_forever, name="telegram-poll", daemon=True)
    thread.start()
    log_event("telegram_poll_thread_started")
    return thread
