import os


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
