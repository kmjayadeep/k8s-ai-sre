from agents import function_tool

from app.actions import format_action_metadata, propose_action


@function_tool
def propose_delete_pod(namespace: str, pod_name: str) -> str:
    action = propose_action("delete-pod", namespace, pod_name)
    return format_action_metadata(action)


@function_tool
def propose_rollout_restart(namespace: str, deployment_name: str) -> str:
    action = propose_action("rollout-restart", namespace, deployment_name)
    return format_action_metadata(action)


@function_tool
def propose_scale(namespace: str, deployment_name: str, replicas: int) -> str:
    action = propose_action("scale", namespace, deployment_name, {"replicas": replicas})
    return format_action_metadata(action)


@function_tool
def propose_rollout_undo(namespace: str, deployment_name: str) -> str:
    action = propose_action("rollout-undo", namespace, deployment_name)
    return format_action_metadata(action)
