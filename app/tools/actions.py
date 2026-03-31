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


def delete_pod(namespace: str, pod_name: str, confirm: bool) -> str:
    if not _allowed_to_write(namespace):
        return f"Refusing to delete pod {pod_name} in namespace {namespace}: namespace is not in WRITE_ALLOWED_NAMESPACES."
    if not confirm:
        return f"Refusing to delete pod {pod_name} in namespace {namespace} without explicit approval."

    ok, output = _run_kubectl(["kubectl", "delete", "pod", pod_name, "-n", namespace])
    if not ok:
        return f"Failed to delete pod {pod_name} in namespace {namespace}: {output}"
    return output


def rollout_restart_deployment(namespace: str, deployment_name: str, confirm: bool) -> str:
    if not _allowed_to_write(namespace):
        return (
            f"Refusing to restart deployment {deployment_name} in namespace {namespace}: "
            f"namespace is not in WRITE_ALLOWED_NAMESPACES."
        )
    if not confirm:
        return f"Refusing to restart deployment {deployment_name} in namespace {namespace} without explicit approval."

    ok, output = _run_kubectl(["kubectl", "rollout", "restart", f"deployment/{deployment_name}", "-n", namespace])
    if not ok:
        return f"Failed to restart deployment {deployment_name} in namespace {namespace}: {output}"
    return output


def scale_deployment(namespace: str, deployment_name: str, replicas: int, confirm: bool) -> str:
    if not _allowed_to_write(namespace):
        return (
            f"Refusing to scale deployment {deployment_name} in namespace {namespace}: "
            f"namespace is not in WRITE_ALLOWED_NAMESPACES."
        )
    if not confirm:
        return f"Refusing to scale deployment {deployment_name} in namespace {namespace} to {replicas} replicas without explicit approval."

    ok, output = _run_kubectl(
        ["kubectl", "scale", f"deployment/{deployment_name}", "-n", namespace, f"--replicas={replicas}"]
    )
    if not ok:
        return f"Failed to scale deployment {deployment_name} in namespace {namespace}: {output}"
    return output


def rollout_undo_deployment(namespace: str, deployment_name: str, confirm: bool) -> str:
    if not _allowed_to_write(namespace):
        return (
            f"Refusing to undo deployment {deployment_name} in namespace {namespace}: "
            f"namespace is not in WRITE_ALLOWED_NAMESPACES."
        )
    if not confirm:
        return f"Refusing to undo deployment {deployment_name} in namespace {namespace} without explicit approval."

    target_ok, target_output = _run_kubectl(["kubectl", "get", "deployment", deployment_name, "-n", namespace])
    if not target_ok:
        return (
            f"Refusing to undo deployment {deployment_name} in namespace {namespace}: "
            f"target deployment is not readable or does not exist ({target_output})."
        )

    ok, output = _run_kubectl(["kubectl", "rollout", "undo", f"deployment/{deployment_name}", "-n", namespace])
    if not ok:
        return f"Failed to undo deployment {deployment_name} in namespace {namespace}: {output}"
    return output
