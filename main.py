import asyncio
import sys

from agents import set_tracing_disabled
from action_store import create_action, get_action, is_action_expired, update_action_status
from investigate import investigate_target
from logger import log_event
from server import run_server
from telegram_bot import poll_telegram_updates_once
from tools import delete_pod, rollout_restart_deployment, rollout_undo_deployment, scale_deployment

set_tracing_disabled(True)


def get_target_from_args() -> tuple[str, str, str]:
    if len(sys.argv) == 4:
        kind, namespace, name = sys.argv[1], sys.argv[2], sys.argv[3]
        return kind, namespace, name
    return "deployment", "ai-sre-demo", "bad-deploy"


def is_delete_pod_command() -> bool:
    return len(sys.argv) >= 4 and sys.argv[1] == "delete-pod"


def is_rollout_restart_command() -> bool:
    return len(sys.argv) >= 4 and sys.argv[1] == "rollout-restart"


def is_scale_command() -> bool:
    return len(sys.argv) >= 5 and sys.argv[1] == "scale"


def is_rollout_undo_command() -> bool:
    return len(sys.argv) >= 4 and sys.argv[1] == "rollout-undo"


def get_delete_pod_args() -> tuple[str, str, bool]:
    namespace = sys.argv[2]
    pod_name = sys.argv[3]
    confirm = len(sys.argv) >= 5 and sys.argv[4] == "--confirm"
    return namespace, pod_name, confirm


def get_rollout_restart_args() -> tuple[str, str, bool]:
    namespace = sys.argv[2]
    deployment_name = sys.argv[3]
    confirm = len(sys.argv) >= 5 and sys.argv[4] == "--confirm"
    return namespace, deployment_name, confirm


def get_scale_args() -> tuple[str, str, int, bool]:
    namespace = sys.argv[2]
    deployment_name = sys.argv[3]
    replicas = int(sys.argv[4])
    confirm = len(sys.argv) >= 6 and sys.argv[5] == "--confirm"
    return namespace, deployment_name, replicas, confirm


def get_rollout_undo_args() -> tuple[str, str, bool]:
    namespace = sys.argv[2]
    deployment_name = sys.argv[3]
    confirm = len(sys.argv) >= 5 and sys.argv[4] == "--confirm"
    return namespace, deployment_name, confirm


def is_propose_delete_pod_command() -> bool:
    return len(sys.argv) == 4 and sys.argv[1] == "propose-delete-pod"


def is_propose_rollout_restart_command() -> bool:
    return len(sys.argv) == 4 and sys.argv[1] == "propose-rollout-restart"


def is_propose_scale_command() -> bool:
    return len(sys.argv) == 5 and sys.argv[1] == "propose-scale"


def is_propose_rollout_undo_command() -> bool:
    return len(sys.argv) == 4 and sys.argv[1] == "propose-rollout-undo"


def is_approve_command() -> bool:
    return len(sys.argv) == 3 and sys.argv[1] == "approve"


def is_reject_command() -> bool:
    return len(sys.argv) == 3 and sys.argv[1] == "reject"


def is_serve_command() -> bool:
    return len(sys.argv) >= 2 and sys.argv[1] == "serve"


def get_serve_port() -> int:
    if len(sys.argv) >= 3:
        return int(sys.argv[2])
    return 8080


def is_telegram_poll_command() -> bool:
    return len(sys.argv) >= 2 and sys.argv[1] == "telegram-poll"


async def main():
    if is_telegram_poll_command():
        log_event("telegram_poll_started")
        print(poll_telegram_updates_once())
        log_event("telegram_poll_completed")
        return

    if is_propose_delete_pod_command():
        namespace, pod_name = sys.argv[2], sys.argv[3]
        action = create_action("delete-pod", namespace, pod_name)
        log_event("action_proposed", action_id=action["id"], action_type="delete-pod", namespace=namespace, name=pod_name)
        print(
            f"Created action {action['id']} to delete pod {pod_name} in namespace {namespace}.\n"
            f"Approve with: uv run main.py approve {action['id']}\n"
            f"Reject with: uv run main.py reject {action['id']}"
        )
        return

    if is_propose_rollout_restart_command():
        namespace, deployment_name = sys.argv[2], sys.argv[3]
        action = create_action("rollout-restart", namespace, deployment_name)
        log_event("action_proposed", action_id=action["id"], action_type="rollout-restart", namespace=namespace, name=deployment_name)
        print(
            f"Created action {action['id']} to restart deployment {deployment_name} in namespace {namespace}.\n"
            f"Approve with: uv run main.py approve {action['id']}\n"
            f"Reject with: uv run main.py reject {action['id']}"
        )
        return

    if is_propose_scale_command():
        namespace, deployment_name, replicas = sys.argv[2], sys.argv[3], int(sys.argv[4])
        action = create_action("scale", namespace, deployment_name, {"replicas": replicas})
        log_event("action_proposed", action_id=action["id"], action_type="scale", namespace=namespace, name=deployment_name, replicas=replicas)
        print(
            f"Created action {action['id']} to scale deployment {deployment_name} in namespace {namespace} to {replicas} replicas.\n"
            f"Approve with: uv run main.py approve {action['id']}\n"
            f"Reject with: uv run main.py reject {action['id']}"
        )
        return

    if is_propose_rollout_undo_command():
        namespace, deployment_name = sys.argv[2], sys.argv[3]
        action = create_action("rollout-undo", namespace, deployment_name)
        log_event("action_proposed", action_id=action["id"], action_type="rollout-undo", namespace=namespace, name=deployment_name)
        print(
            f"Created action {action['id']} to undo deployment {deployment_name} in namespace {namespace}.\n"
            f"Approve with: uv run main.py approve {action['id']}\n"
            f"Reject with: uv run main.py reject {action['id']}"
        )
        return

    if is_approve_command():
        action_id = sys.argv[2]
        action = get_action(action_id)
        if action is None:
            print(f"Action {action_id} not found.")
            return
        if action["status"] != "pending":
            print(f"Action {action_id} is already {action['status']}.")
            return
        if is_action_expired(action):
            update_action_status(action_id, "expired")
            log_event("action_expired", action_id=action_id)
            print(f"Action {action_id} has expired.")
            return
        if action["type"] == "delete-pod":
            result = delete_pod(action["namespace"], action["name"], confirm=True)
            update_action_status(action_id, "approved")
            log_event("action_approved", action_id=action_id, action_type=action["type"], namespace=action["namespace"], name=action["name"])
            print(result)
            return
        if action["type"] == "rollout-restart":
            result = rollout_restart_deployment(action["namespace"], action["name"], confirm=True)
            update_action_status(action_id, "approved")
            log_event("action_approved", action_id=action_id, action_type=action["type"], namespace=action["namespace"], name=action["name"])
            print(result)
            return
        if action["type"] == "scale":
            replicas = int(action.get("params", {}).get("replicas", 1))
            result = scale_deployment(action["namespace"], action["name"], replicas, confirm=True)
            update_action_status(action_id, "approved")
            log_event("action_approved", action_id=action_id, action_type=action["type"], namespace=action["namespace"], name=action["name"], replicas=replicas)
            print(result)
            return
        if action["type"] == "rollout-undo":
            result = rollout_undo_deployment(action["namespace"], action["name"], confirm=True)
            update_action_status(action_id, "approved")
            log_event("action_approved", action_id=action_id, action_type=action["type"], namespace=action["namespace"], name=action["name"])
            print(result)
            return
        print(f"Unsupported action type: {action['type']}")
        return

    if is_reject_command():
        action_id = sys.argv[2]
        action = update_action_status(action_id, "rejected")
        if action is None:
            print(f"Action {action_id} not found.")
            return
        log_event("action_rejected", action_id=action_id)
        print(f"Rejected action {action_id}.")
        return

    if is_delete_pod_command():
        namespace, pod_name, confirm = get_delete_pod_args()
        print(delete_pod(namespace, pod_name, confirm))
        return

    if is_rollout_restart_command():
        namespace, deployment_name, confirm = get_rollout_restart_args()
        print(rollout_restart_deployment(namespace, deployment_name, confirm))
        return

    if is_scale_command():
        namespace, deployment_name, replicas, confirm = get_scale_args()
        print(scale_deployment(namespace, deployment_name, replicas, confirm))
        return

    if is_rollout_undo_command():
        namespace, deployment_name, confirm = get_rollout_undo_args()
        print(rollout_undo_deployment(namespace, deployment_name, confirm))
        return

    kind, namespace, name = get_target_from_args()
    await investigate_target(kind, namespace, name)

if __name__ == "__main__":
    if is_serve_command():
        run_server(get_serve_port())
        raise SystemExit(0)
    asyncio.run(main())
