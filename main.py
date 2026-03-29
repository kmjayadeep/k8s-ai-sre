import asyncio
import sys

from agents import set_tracing_disabled
from app.actions import approve_action, format_action_created, propose_action, reject_action
from app.cli import parse_cli_args
from app.http import run_server
from app.investigate import investigate_target
from app.log import log_event
from app.telegram import poll_telegram_updates_once
from app.tools.actions import delete_pod, rollout_restart_deployment, rollout_undo_deployment, scale_deployment

set_tracing_disabled(True)


async def main():
    command = parse_cli_args(sys.argv)

    if command.name == "telegram-poll":
        log_event("telegram_poll_started")
        print(poll_telegram_updates_once())
        log_event("telegram_poll_completed")
        return

    if command.name == "propose-delete-pod":
        namespace, pod_name = command.args
        action = propose_action("delete-pod", namespace, pod_name)
        print(format_action_created(action, f"delete pod {pod_name} in namespace {namespace}"))
        return

    if command.name == "propose-rollout-restart":
        namespace, deployment_name = command.args
        action = propose_action("rollout-restart", namespace, deployment_name)
        print(format_action_created(action, f"restart deployment {deployment_name} in namespace {namespace}"))
        return

    if command.name == "propose-scale":
        namespace, deployment_name, replicas = command.args
        action = propose_action("scale", namespace, deployment_name, {"replicas": replicas})
        print(format_action_created(action, f"scale deployment {deployment_name} in namespace {namespace} to {replicas} replicas"))
        return

    if command.name == "propose-rollout-undo":
        namespace, deployment_name = command.args
        action = propose_action("rollout-undo", namespace, deployment_name)
        print(format_action_created(action, f"undo deployment {deployment_name} in namespace {namespace}"))
        return

    if command.name == "approve":
        (action_id,) = command.args
        print(approve_action(action_id))
        return

    if command.name == "reject":
        (action_id,) = command.args
        print(reject_action(action_id))
        return

    if command.name == "delete-pod":
        namespace, pod_name, confirm = command.args
        print(delete_pod(namespace, pod_name, confirm))
        return

    if command.name == "rollout-restart":
        namespace, deployment_name, confirm = command.args
        print(rollout_restart_deployment(namespace, deployment_name, confirm))
        return

    if command.name == "scale":
        namespace, deployment_name, replicas, confirm = command.args
        print(scale_deployment(namespace, deployment_name, replicas, confirm))
        return

    if command.name == "rollout-undo":
        namespace, deployment_name, confirm = command.args
        print(rollout_undo_deployment(namespace, deployment_name, confirm))
        return

    kind, namespace, name = command.args
    await investigate_target(kind, namespace, name)


if __name__ == "__main__":
    command = parse_cli_args(sys.argv)
    if command.name == "serve":
        (port,) = command.args
        run_server(port)
        raise SystemExit(0)
    asyncio.run(main())
