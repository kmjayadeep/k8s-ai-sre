import json
import os
import urllib.error
import urllib.parse
import urllib.request


def _format_proposed_actions(incident: dict[str, object]) -> str:
    proposed_actions = incident.get("proposed_actions", [])
    if not proposed_actions:
        return "Proposed actions:\n- none"

    lines = ["Proposed actions:"]
    for action in proposed_actions[:4]:
        if not isinstance(action, dict):
            continue
        action_id = action.get("action_id", "unknown")
        action_type = action.get("action_type", "unknown")
        namespace = action.get("namespace", "unknown")
        name = action.get("name", "unknown")
        lines.append(f"- {action_id}: {action_type} {namespace}/{name}")
        lines.append(f"  approve: /approve {action_id}")
        lines.append(f"  reject: /reject {action_id}")
    return "\n".join(lines)


def send_telegram_notification(incident: dict[str, str]) -> str:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        return "Telegram is not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to enable notifications."

    message = (
        f"Incident {incident.get('incident_id', 'unknown')}\n"
        f"Target: {incident.get('kind')} {incident.get('namespace')}/{incident.get('name')}\n"
        f"Answer:\n{incident.get('answer', '')[:2200]}\n\n"
        f"{_format_proposed_actions(incident)}"
    )
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = urllib.parse.urlencode({"chat_id": chat_id, "text": message}).encode("utf-8")
    request = urllib.request.Request(url, data=payload, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        return f"Failed to send Telegram notification: {exc}"

    if not body.get("ok"):
        return f"Telegram API returned error: {body}"
    return "Telegram notification sent."
