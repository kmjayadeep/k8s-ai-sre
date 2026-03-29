import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from action_store import get_action, is_action_expired, update_action_status
from incident_store import get_incident
from logger import log_event
from tools import delete_pod


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
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def _send_message(chat_id: str, text: str) -> str:
    body = _telegram_api("sendMessage", {"chat_id": chat_id, "text": text[:4000]})
    if not body.get("ok"):
        return f"Failed to send Telegram reply: {body}"
    return "Telegram reply sent."


def _format_incident(incident: dict[str, str]) -> str:
    return (
        f"Incident {incident.get('incident_id', 'unknown')}\n"
        f"Target: {incident.get('kind')} {incident.get('namespace')}/{incident.get('name')}\n"
        f"Answer:\n{incident.get('answer', 'No answer stored.')[:3000]}"
    )


def _format_status(incident: dict[str, str]) -> str:
    return (
        f"Incident {incident.get('incident_id', 'unknown')}\n"
        f"Target: {incident.get('kind')} {incident.get('namespace')}/{incident.get('name')}\n"
        f"Source: {incident.get('source', 'manual')}\n"
        f"Notification: {incident.get('notification_status', 'unknown')}"
    )


def _handle_command(text: str) -> str:
    parts = text.strip().split(maxsplit=1)
    command = parts[0] if parts else ""
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
        action = get_action(argument)
        if action is None:
            return f"Action {argument} not found."
        if action.get("status") != "pending":
            return f"Action {argument} is already {action.get('status')}."
        if is_action_expired(action):
            update_action_status(argument, "expired")
            return f"Action {argument} has expired."
        if action.get("type") == "delete-pod":
            result = delete_pod(action["namespace"], action["name"], confirm=True)
            update_action_status(argument, "approved")
            return result
        return f"Unsupported action type: {action.get('type')}."

    if command == "/reject" and argument:
        action = update_action_status(argument, "rejected")
        if action is None:
            return f"Action {argument} not found."
        return f"Rejected action {argument}."

    return "Commands: /incident <incident-id>, /status <incident-id>, /approve <action-id>, /reject <action-id>"


def poll_telegram_updates_once() -> str:
    token = _telegram_token()
    if not token:
        return "Telegram is not configured. Set TELEGRAM_BOT_TOKEN."

    offset = _load_offset()
    query = {}
    if offset is not None:
        query["offset"] = str(offset)
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
        reply = _handle_command(text)
        _send_message(chat_id, reply)
        handled += 1

    log_event("telegram_poll_processed", handled=handled)
    return f"Processed {handled} Telegram command(s)."
