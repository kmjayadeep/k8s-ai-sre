import os
import subprocess


def _run_kubectl(command: list[str]) -> tuple[bool, str]:
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    output = result.stdout.strip() or result.stderr.strip()
    return result.returncode == 0, output


def _allowed_to_write(namespace: str) -> bool:
    allowed_namespaces = {
        item.strip()
        for item in os.getenv("WRITE_ALLOWED_NAMESPACES", "").split(",")
        if item.strip()
    }
    return not allowed_namespaces or namespace in allowed_namespaces


def _deployment_exists(namespace: str, deployment_name: str) -> tuple[bool, str]:
    return _run_kubectl(["kubectl", "get", "deployment", deployment_name, "-n", namespace])


def _pod_exists(namespace: str, pod_name: str) -> tuple[bool, str]:
    return _run_kubectl(["kubectl", "get", "pod", pod_name, "-n", namespace])


def _can_i(namespace: str, verb: str, resource: str) -> tuple[bool, str]:
    ok, output = _run_kubectl(["kubectl", "auth", "can-i", verb, resource, "-n", namespace])
    normalized = output.strip().lower()
    if ok and normalized == "yes":
        return True, output
    if ok and normalized == "no":
        return False, "authorization denied by cluster RBAC"
    if not ok:
        return False, f"authorization check failed ({output})"
    return False, f"authorization check ambiguous ({output})"


def _rbac_refusal(action: str, name: str, namespace: str, reason: str) -> str:
    return f"Refusing to {action} {name} in namespace {namespace}: {reason}."


def delete_pod(namespace: str, pod_name: str, confirm: bool) -> str:
    if not _allowed_to_write(namespace):
        return _rbac_refusal("delete pod", pod_name, namespace, "namespace is not in WRITE_ALLOWED_NAMESPACES")
    if not confirm:
        return _rbac_refusal("delete pod", pod_name, namespace, "explicit approval is required")
    allowed, detail = _can_i(namespace, "delete", "pods")
    if not allowed:
        return _rbac_refusal("delete pod", pod_name, namespace, detail)
    exists, output = _pod_exists(namespace, pod_name)
    if not exists:
        return _rbac_refusal("delete pod", pod_name, namespace, f"pod was not found or not readable ({output})")

    ok, output = _run_kubectl(["kubectl", "delete", "pod", pod_name, "-n", namespace])
    if not ok:
        return f"Failed to delete pod {pod_name} in namespace {namespace}: {output}"
    return output


def rollout_restart_deployment(namespace: str, deployment_name: str, confirm: bool) -> str:
    if not _allowed_to_write(namespace):
        return _rbac_refusal("restart deployment", deployment_name, namespace, "namespace is not in WRITE_ALLOWED_NAMESPACES")
    if not confirm:
        return _rbac_refusal("restart deployment", deployment_name, namespace, "explicit approval is required")
    allowed, detail = _can_i(namespace, "patch", "deployments")
    if not allowed:
        return _rbac_refusal("restart deployment", deployment_name, namespace, detail)
    exists, output = _deployment_exists(namespace, deployment_name)
    if not exists:
        return _rbac_refusal(
            "restart deployment",
            deployment_name,
            namespace,
            f"deployment was not found or not readable ({output})",
        )

    ok, output = _run_kubectl(["kubectl", "rollout", "restart", f"deployment/{deployment_name}", "-n", namespace])
    if not ok:
        return f"Failed to restart deployment {deployment_name} in namespace {namespace}: {output}"
    return output


def scale_deployment(namespace: str, deployment_name: str, replicas: int, confirm: bool) -> str:
    if not _allowed_to_write(namespace):
        return _rbac_refusal("scale deployment", deployment_name, namespace, "namespace is not in WRITE_ALLOWED_NAMESPACES")
    if not confirm:
        return _rbac_refusal("scale deployment", deployment_name, namespace, "explicit approval is required")
    if replicas < 0:
        return _rbac_refusal("scale deployment", deployment_name, namespace, "replicas must be >= 0")
    allowed, detail = _can_i(namespace, "patch", "deployments/scale")
    if not allowed:
        return _rbac_refusal("scale deployment", deployment_name, namespace, detail)

    exists, output = _deployment_exists(namespace, deployment_name)
    if not exists:
        return _rbac_refusal(
            "scale deployment",
            deployment_name,
            namespace,
            f"deployment was not found or not readable ({output})",
        )

    ok, output = _run_kubectl(
        ["kubectl", "scale", f"deployment/{deployment_name}", "-n", namespace, f"--replicas={replicas}"]
    )
    if not ok:
        return f"Failed to scale deployment {deployment_name} in namespace {namespace}: {output}"
    return output


def rollout_undo_deployment(namespace: str, deployment_name: str, confirm: bool) -> str:
    if not _allowed_to_write(namespace):
        return _rbac_refusal("undo deployment", deployment_name, namespace, "namespace is not in WRITE_ALLOWED_NAMESPACES")
    if not confirm:
        return _rbac_refusal("undo deployment", deployment_name, namespace, "explicit approval is required")
    allowed, detail = _can_i(namespace, "patch", "deployments")
    if not allowed:
        return _rbac_refusal("undo deployment", deployment_name, namespace, detail)

    exists, output = _deployment_exists(namespace, deployment_name)
    if not exists:
        return _rbac_refusal(
            "undo deployment",
            deployment_name,
            namespace,
            f"deployment was not found or not readable ({output})",
        )

    ok, output = _run_kubectl(["kubectl", "rollout", "undo", f"deployment/{deployment_name}", "-n", namespace])
    if not ok:
        return f"Failed to undo deployment {deployment_name} in namespace {namespace}: {output}"
    return output
