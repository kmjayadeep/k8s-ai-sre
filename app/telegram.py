import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

from app.actions import approve_action, reject_action
from app.log import log_event
from app.stores import get_incident


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
    lines = [
        f"Incident {incident.get('incident_id', 'unknown')}",
        f"Target: {incident.get('kind')} {incident.get('namespace')}/{incident.get('name')}",
        f"Answer:\n{incident.get('answer', 'No answer stored.')[:2400]}",
    ]
    proposed_actions = incident.get("proposed_actions", [])
    if proposed_actions:
        lines.append("Actions:")
        for action in proposed_actions[:4]:
            if not isinstance(action, dict):
                continue
            lines.append(f"- {action.get('action_id')}: {action.get('action_type')} {action.get('namespace')}/{action.get('name')}")
    else:
        lines.append("Actions:\n- none")
    return "\n".join(lines)


def _format_status(incident: dict[str, str]) -> str:
    action_ids = incident.get("action_ids", [])
    action_summary = ", ".join(action_ids[:5]) if action_ids else "none"
    return (
        f"Incident {incident.get('incident_id', 'unknown')}\n"
        f"Target: {incident.get('kind')} {incident.get('namespace')}/{incident.get('name')}\n"
        f"Source: {incident.get('source', 'manual')}\n"
        f"Notification: {incident.get('notification_status', 'unknown')}\n"
        f"Action IDs: {action_summary}"
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
