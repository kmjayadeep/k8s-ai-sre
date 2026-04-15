from __future__ import annotations


SECTION_ORDER = ("summary", "most likely cause", "confidence", "proposed actions")


def _brief_payload(incident: dict[str, object]) -> dict[str, object]:
    candidate = incident.get("brief")
    if not isinstance(candidate, dict):
        return {}
    return candidate


def _strip_reasoning_blocks(text: str) -> str:
    if not text:
        return ""
    result: list[str] = []
    cursor = 0
    lower = text.lower()
    while True:
        think_index = lower.find("<think>", cursor)
        thinking_index = lower.find("<thinking>", cursor)
        open_index = -1
        open_tag = ""
        close_tag = ""
        for index, tag, closing in (
            (think_index, "<think>", "</think>"),
            (thinking_index, "<thinking>", "</thinking>"),
        ):
            if index == -1:
                continue
            if open_index == -1 or index < open_index:
                open_index = index
                open_tag = tag
                close_tag = closing
        if open_index == -1:
            result.append(text[cursor:])
            break
        result.append(text[cursor:open_index])
        close_index = lower.find(close_tag, open_index + len(open_tag))
        if close_index == -1:
            break
        cursor = close_index + len(close_tag)
    cleaned = "".join(result)
    cleaned = cleaned.replace("</think>", "").replace("</thinking>", "")
    return cleaned.strip()


def _extract_section(answer: str, section_name: str) -> str:
    if not answer:
        return ""
    content = _strip_reasoning_blocks(answer)
    lowered = content.lower()
    marker = f"{section_name.lower()}:"
    start = lowered.find(marker)
    if start == -1:
        return ""
    start += len(marker)
    end = len(content)
    for candidate in SECTION_ORDER:
        if candidate == section_name.lower():
            continue
        candidate_index = lowered.find(f"{candidate}:", start)
        if candidate_index != -1:
            end = min(end, candidate_index)
    return " ".join(content[start:end].strip().split())


def _to_single_line(text: str, max_chars: int = 260) -> str:
    single_line = " ".join(text.split())
    if len(single_line) <= max_chars:
        return single_line
    return single_line[: max_chars - 3].rstrip() + "..."


def quick_summary_lines(incident: dict[str, object]) -> list[str]:
    brief = _brief_payload(incident)
    summary = _to_single_line(str(brief.get("summary", "")).strip(), max_chars=260)
    cause = _to_single_line(str(brief.get("root_cause", "")).strip(), max_chars=260)

    answer = str(incident.get("answer", "") or "")
    if not summary:
        summary = _extract_section(answer, "summary")
    if not cause:
        cause = _extract_section(answer, "most likely cause")

    if not summary:
        summary = _to_single_line(_strip_reasoning_blocks(answer), max_chars=260)
    if not summary:
        summary = "No investigation summary available."

    if not cause:
        cause = "Not explicitly identified."

    return [
        f"Quick summary: {_to_single_line(summary, max_chars=260)}",
        f"Root cause: {_to_single_line(cause, max_chars=260)}",
    ]


def action_item_lines(incident: dict[str, object]) -> list[str]:
    brief = _brief_payload(incident)
    brief_items = brief.get("action_items", [])
    summarized_items: list[str] = []
    if isinstance(brief_items, list):
        for item in brief_items[:4]:
            text = _to_single_line(str(item).strip(), max_chars=260)
            if text:
                summarized_items.append(text)

    proposed_actions = incident.get("proposed_actions", [])
    if not proposed_actions and not summarized_items:
        return ["Action items:", "1. No proposed automated remediation. Continue manual triage."]

    lines = ["Action items:"]
    item_number = 0
    for item in summarized_items:
        item_number += 1
        lines.append(f"{item_number}. {item}")

    for action in proposed_actions[:4]:
        if not isinstance(action, dict):
            continue
        action_id = str(action.get("action_id", "unknown"))
        action_type = str(action.get("action_type", "unknown"))
        namespace = str(action.get("namespace", "unknown"))
        name = str(action.get("name", "unknown"))
        item_number += 1
        lines.append(f"{item_number}. Automated option: {action_type} {namespace}/{name}")
        lines.append(f"   approve: /approve {action_id}")
        lines.append(f"   reject: /reject {action_id}")
    if item_number == 0:
        return ["Action items:", "1. No valid proposed actions found in incident payload."]
    return lines
