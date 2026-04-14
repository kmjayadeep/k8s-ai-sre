from __future__ import annotations

import json


def _as_line(value: object, default: str) -> str:
    text = " ".join(str(value or "").split())
    return text if text else default


def _as_items(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value:
        text = " ".join(str(item or "").split())
        if text:
            items.append(text)
    return items


def _extract_json_object(raw_output: str) -> dict[str, object] | None:
    text = raw_output.strip()
    if not text:
        return None

    candidates: list[str] = [text]
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            payload, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return None


def parse_investigation_brief(raw_output: str) -> dict[str, object]:
    payload = _extract_json_object(raw_output)
    if payload is None:
        return {}

    summary = _as_line(payload.get("summary"), "")
    root_cause = _as_line(payload.get("root_cause"), "")
    confidence = _as_line(payload.get("confidence"), "")
    action_items = _as_items(payload.get("action_items"))

    if not summary and not root_cause and not confidence and not action_items:
        return {}

    return {
        "summary": summary,
        "root_cause": root_cause,
        "confidence": confidence,
        "action_items": action_items,
    }
