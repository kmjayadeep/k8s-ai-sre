import json
import os
import urllib.error
import urllib.parse
import urllib.request

from app.telegram_text import format_target_lines
from app.telegram_brief import action_item_lines, quick_summary_lines


def _inline_keyboard(incident: dict[str, object]) -> list[list[dict[str, str]]]:
    proposed_actions = incident.get("proposed_actions", [])
    keyboard: list[list[dict[str, str]]] = []
    for action in proposed_actions[:4]:
        if not isinstance(action, dict):
            continue
        action_id = str(action.get("action_id", "")).strip()
        if not action_id:
            continue
        keyboard.append(
            [
                {"text": f"Approve {action_id}", "callback_data": f"approve:{action_id}"},
                {"text": f"Reject {action_id}", "callback_data": f"reject:{action_id}"},
            ]
        )
    return keyboard


def send_telegram_notification(incident: dict[str, object]) -> str:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        return "Telegram is not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to enable notifications."

    lines = [
        f"Incident {incident.get('incident_id', 'unknown')}",
        *format_target_lines(incident),
        *quick_summary_lines(incident),
        *action_item_lines(incident),
    ]
    message = "\n".join(lines)[:3900]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload_data = {"chat_id": chat_id, "text": message}
    keyboard = _inline_keyboard(incident)
    if keyboard:
        payload_data["reply_markup"] = json.dumps({"inline_keyboard": keyboard})
    payload = urllib.parse.urlencode(payload_data).encode("utf-8")
    request = urllib.request.Request(url, data=payload, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        return f"Failed to send Telegram notification: {exc}"

    if not body.get("ok"):
        return f"Telegram API returned error: {body}"
    return "Telegram notification sent."
