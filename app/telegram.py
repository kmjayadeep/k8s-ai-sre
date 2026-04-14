import json
import os
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

from app.actions import approve_action, reject_action
from app.error_taxonomy import telegram_error_message
from app.log import log_event
from app.stores import get_incident
from app.telegram_text import format_target_lines


TELEGRAM_OFFSET_PATH = Path("/tmp/k8s-ai-sre-telegram-offset.json")
COMMAND_HELP_TEXT = "Commands: /incident <incident-id>, /status <incident-id>, /approve <action-id>, /reject <action-id>"
TELEGRAM_COMMAND_EXECUTION_FAILED = telegram_error_message(
    "telegram_command_execution_failed",
    "Command failed due to an internal error. Please retry and check service logs.",
)
TELEGRAM_CALLBACK_EXECUTION_FAILED = telegram_error_message(
    "telegram_callback_execution_failed",
    "Action failed due to an internal error. Please retry and check service logs.",
)
TELEGRAM_CALLBACK_PAYLOAD_INVALID = telegram_error_message(
    "telegram_callback_payload_invalid",
    "Unsupported action button payload.",
)


def _usage(command: str) -> str:
    if command == "/incident":
        return "Usage: /incident <incident-id>"
    if command == "/status":
        return "Usage: /status <incident-id>"
    if command == "/approve":
        return "Usage: /approve <action-id>"
    if command == "/reject":
        return "Usage: /reject <action-id>"
    return COMMAND_HELP_TEXT


def _telegram_token() -> str | None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    return token or None


def _allowed_chat_ids() -> set[str]:
    return {item.strip() for item in os.getenv("TELEGRAM_ALLOWED_CHAT_IDS", "").split(",") if item.strip()}


def _positive_float_from_env(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    if value <= 0:
        return default
    return value


def _poll_timeout_seconds() -> float:
    return _positive_float_from_env("TELEGRAM_POLL_TIMEOUT_SECONDS", 30.0)


def _http_timeout_seconds(poll_timeout_seconds: float | None = None) -> float:
    poll_timeout = poll_timeout_seconds if poll_timeout_seconds is not None else _poll_timeout_seconds()
    http_timeout = _positive_float_from_env("TELEGRAM_HTTP_TIMEOUT_SECONDS", 35.0)
    if http_timeout > poll_timeout:
        return http_timeout
    return max(35.0, poll_timeout + 5.0)


def _timeout_text(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return str(value)


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
    timeout_seconds = _http_timeout_seconds()
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def _send_message(chat_id: str, text: str) -> str:
    body = _telegram_api("sendMessage", {"chat_id": chat_id, "text": text[:4000]})
    if not body.get("ok"):
        return f"Failed to send Telegram reply: {body}"
    return "Telegram reply sent."


def _answer_callback_query(callback_query_id: str, text: str) -> str:
    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text[:180]
    body = _telegram_api("answerCallbackQuery", payload)
    if not body.get("ok"):
        return f"Failed to acknowledge Telegram callback: {body}"
    return "Telegram callback acknowledged."


def _format_incident(incident: dict[str, object]) -> str:
    answer_text = str(incident.get("answer", "No answer stored."))[:2400]
    lines = [
        f"Incident {incident.get('incident_id', 'unknown')}",
        *format_target_lines(incident),
        f"Answer:\n{answer_text}",
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


def _format_status(incident: dict[str, object]) -> str:
    action_ids = incident.get("action_ids", [])
    action_summary = ", ".join(action_ids[:5]) if action_ids else "none"
    target_text = "\n".join(format_target_lines(incident))
    return (
        f"Incident {incident.get('incident_id', 'unknown')}\n"
        f"{target_text}\n"
        f"Source: {incident.get('source', 'manual')}\n"
        f"Notification: {incident.get('notification_status', 'unknown')}\n"
        f"Action IDs: {action_summary}"
    )


def _handle_command(text: str, approver_id: str = "unknown", approval_source: str = "telegram") -> str:
    parts = text.strip().split(maxsplit=1)
    command = parts[0] if parts else ""
    if "@" in command:
        command = command.split("@", 1)[0]
    argument = parts[1] if len(parts) > 1 else ""

    if command == "/incident":
        if not argument:
            return _usage(command)
        incident = get_incident(argument)
        if incident is None:
            return f"Incident {argument} not found."
        return _format_incident(incident)

    if command == "/status":
        if not argument:
            return _usage(command)
        incident = get_incident(argument)
        if incident is None:
            return f"Incident {argument} not found."
        return _format_status(incident)

    if command == "/approve":
        if not argument:
            return _usage(command)
        return approve_action(argument, approver_id=approver_id, approval_source=approval_source)

    if command == "/reject":
        if not argument:
            return _usage(command)
        return reject_action(argument, approver_id=approver_id, approval_source=approval_source)

    return COMMAND_HELP_TEXT


def _handle_callback(data: str) -> str:
    verb, separator, action_id = data.strip().partition(":")
    if not separator or not action_id:
        return TELEGRAM_CALLBACK_PAYLOAD_INVALID
    if verb == "approve":
        return approve_action(action_id)
    if verb == "reject":
        return reject_action(action_id)
    return TELEGRAM_CALLBACK_PAYLOAD_INVALID


def poll_telegram_updates_once() -> str:
    token = _telegram_token()
    if not token:
        return "Telegram is not configured. Set TELEGRAM_BOT_TOKEN."

    offset = _load_offset()
    query = {}
    if offset is not None:
        query["offset"] = str(offset)
    query["timeout"] = _timeout_text(_poll_timeout_seconds())
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
        callback_query = update.get("callback_query", {})
        callback_message = callback_query.get("message", {})
        callback_chat = callback_message.get("chat", {})
        callback_chat_id = str(callback_chat.get("id", ""))
        callback_data = str(callback_query.get("data", "")).strip()
        callback_id = str(callback_query.get("id", "")).strip()
        if callback_query and callback_chat_id and callback_data:
            allowed_chat_ids = _allowed_chat_ids()
            if allowed_chat_ids and callback_chat_id not in allowed_chat_ids:
                log_event("telegram_callback_ignored_unauthorized", chat_id=callback_chat_id, data=callback_data)
                continue
            log_event("telegram_callback_received", chat_id=callback_chat_id, data=callback_data)
            try:
                reply = _handle_callback(callback_data)
            except Exception as exc:
                log_event("telegram_callback_failed", chat_id=callback_chat_id, data=callback_data, error=str(exc))
                reply = TELEGRAM_CALLBACK_EXECUTION_FAILED
            send_status = _send_message(callback_chat_id, reply)
            log_event("telegram_reply_result", chat_id=callback_chat_id, status=send_status)
            if callback_id:
                ack_status = _answer_callback_query(callback_id, reply)
                log_event("telegram_callback_ack_result", callback_id=callback_id, status=ack_status)
            handled += 1
            continue
        message = update.get("message", {})
        chat = message.get("chat", {})
        actor = message.get("from", {})
        text = message.get("text", "").strip()
        chat_id = str(chat.get("id", ""))
        actor_id = str(actor.get("id", "")).strip()
        actor_username = str(actor.get("username", "")).strip()
        if actor_username:
            approver_id = f"telegram:{actor_username}"
        elif actor_id:
            approver_id = f"telegram:{actor_id}"
        elif chat_id:
            approver_id = f"telegram-chat:{chat_id}"
        else:
            approver_id = "telegram:unknown"
        allowed_chat_ids = _allowed_chat_ids()
        if allowed_chat_ids and chat_id not in allowed_chat_ids:
            log_event("telegram_command_ignored_unauthorized", chat_id=chat_id, text=text)
            continue
        if not chat_id or not text.startswith("/"):
            continue
        log_event("telegram_command_received", chat_id=chat_id, text=text)
        try:
            reply = _handle_command(text, approver_id=approver_id, approval_source="telegram")
        except Exception as exc:
            log_event("telegram_command_failed", chat_id=chat_id, text=text, error=str(exc))
            reply = TELEGRAM_COMMAND_EXECUTION_FAILED
        send_status = _send_message(chat_id, reply)
        log_event("telegram_reply_result", chat_id=chat_id, status=send_status)
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
