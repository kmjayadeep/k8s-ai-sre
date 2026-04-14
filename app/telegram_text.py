import os
import re


_THINK_BLOCK_RE = re.compile(r"<\s*(think|thinking)\b[^>]*>.*?<\s*/\s*\1\s*>", re.IGNORECASE | re.DOTALL)
_THINK_OPEN_RE = re.compile(r"<\s*(think|thinking)\b[^>]*>", re.IGNORECASE)
_THINK_CLOSE_RE = re.compile(r"<\s*/\s*(think|thinking)\s*>", re.IGNORECASE)


def _first_non_empty(*values: object) -> str | None:
    for value in values:
        candidate = str(value or "").strip()
        if candidate:
            return candidate
    return None


def resolve_cluster_name(incident: dict[str, object]) -> str | None:
    return _first_non_empty(
        incident.get("cluster_name"),
        os.getenv("K8S_CLUSTER_NAME"),
        os.getenv("CLUSTER_NAME"),
        os.getenv("KUBE_CLUSTER_NAME"),
        os.getenv("KUBERNETES_CLUSTER_NAME"),
    )


def format_target_lines(incident: dict[str, object]) -> list[str]:
    lines = [f"Target: {incident.get('kind')} {incident.get('namespace')}/{incident.get('name')}"]
    cluster_name = resolve_cluster_name(incident)
    if cluster_name:
        lines.append(f"Cluster: {cluster_name}")
    return lines


def sanitize_telegram_answer(answer: object) -> str:
    text = str(answer or "")
    text = _THINK_BLOCK_RE.sub("", text)
    open_match = _THINK_OPEN_RE.search(text)
    if open_match:
        text = text[: open_match.start()]
    text = _THINK_CLOSE_RE.sub("", text)
    return text.strip()
