import json

from agents import function_tool

from app.actions import action_metadata, propose_action


@function_tool
def propose_delete_pod(namespace: str, pod_name: str) -> str:
    action = propose_action("delete-pod", namespace, pod_name)
    return json.dumps(action_metadata(action), sort_keys=True)


@function_tool
def propose_rollout_restart(namespace: str, deployment_name: str) -> str:
    action = propose_action("rollout-restart", namespace, deployment_name)
    return json.dumps(action_metadata(action), sort_keys=True)


@function_tool
def propose_scale(namespace: str, deployment_name: str, replicas: int) -> str:
    action = propose_action("scale", namespace, deployment_name, {"replicas": replicas})
    return json.dumps(action_metadata(action), sort_keys=True)


@function_tool
def propose_rollout_undo(namespace: str, deployment_name: str) -> str:
    action = propose_action("rollout-undo", namespace, deployment_name)
    return json.dumps(action_metadata(action), sort_keys=True)
