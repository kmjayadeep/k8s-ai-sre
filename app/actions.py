import json
from contextvars import ContextVar, Token

from app.log import log_event
from app.stores import create_action, get_action, is_action_expired, update_action, update_action_status
from app.tools import delete_pod, rollout_restart_deployment, rollout_undo_deployment, scale_deployment

_proposal_buffer: ContextVar[list[dict[str, object]] | None] = ContextVar("proposal_buffer", default=None)


def format_action_created(action: dict, description: str) -> str:
    return (
        f"Created action {action['id']} to {description}.\n"
        f"Approve with: uv run main.py approve {action['id']}\n"
        f"Reject with: uv run main.py reject {action['id']}"
    )


def action_metadata(action: dict) -> dict[str, object]:
    action_id = action["id"]
    return {
        "action_id": action_id,
        "action_type": action["type"],
        "namespace": action["namespace"],
        "name": action["name"],
        "params": action.get("params", {}),
        "expires_at": action["expires_at"],
        "approve_command": f"uv run main.py approve {action_id}",
        "reject_command": f"uv run main.py reject {action_id}",
    }


def format_action_metadata(action: dict) -> str:
    return json.dumps(action_metadata(action), sort_keys=True)


def _action_result_prefix(action: dict) -> str:
    incident_id = action.get("incident_id")
    if incident_id:
        return f"Incident {incident_id}\n"
    return ""


def begin_proposal_capture() -> Token:
    return _proposal_buffer.set([])


def finish_proposal_capture(token: Token) -> list[dict[str, object]]:
    proposals = _proposal_buffer.get() or []
    _proposal_buffer.reset(token)
    return proposals


def attach_actions_to_incident(action_ids: list[str], incident_id: str) -> None:
    for action_id in action_ids:
        update_action(action_id, {"incident_id": incident_id})


def propose_action(action_type: str, namespace: str, name: str, params: dict | None = None) -> dict:
    action = create_action(action_type, namespace, name, params)
    log_fields = {
        "action_id": action["id"],
        "action_type": action_type,
        "namespace": namespace,
        "name": name,
    }
    if params:
        log_fields.update(params)
    log_event("action_proposed", **log_fields)
    captured = _proposal_buffer.get()
    if captured is not None:
        captured.append(action_metadata(action))
    return action


def execute_action(action: dict) -> str:
    if action["type"] == "delete-pod":
        return delete_pod(action["namespace"], action["name"], confirm=True)
    if action["type"] == "rollout-restart":
        return rollout_restart_deployment(action["namespace"], action["name"], confirm=True)
    if action["type"] == "scale":
        replicas = int(action.get("params", {}).get("replicas", 1))
        return scale_deployment(action["namespace"], action["name"], replicas, confirm=True)
    if action["type"] == "rollout-undo":
        return rollout_undo_deployment(action["namespace"], action["name"], confirm=True)
    return f"Unsupported action type: {action['type']}"


def approve_action(action_id: str) -> str:
    action = get_action(action_id)
    if action is None:
        return f"Action {action_id} not found."
    if action["status"] != "pending":
        return _action_result_prefix(action) + f"Action {action_id} is already {action['status']}."
    if is_action_expired(action):
        update_action_status(action_id, "expired")
        log_event("action_expired", action_id=action_id)
        return _action_result_prefix(action) + f"Action {action_id} has expired."

    result = execute_action(action)
    update_action_status(action_id, "approved")
    log_fields = {
        "action_id": action_id,
        "action_type": action["type"],
        "namespace": action["namespace"],
        "name": action["name"],
    }
    log_fields.update(action.get("params", {}))
    log_event("action_approved", **log_fields)
    return _action_result_prefix(action) + result


def reject_action(action_id: str) -> str:
    action = get_action(action_id)
    if action is None:
        return f"Action {action_id} not found."
    update_action_status(action_id, "rejected")
    if action is None:
        return f"Action {action_id} not found."
    log_event("action_rejected", action_id=action_id)
    return _action_result_prefix(action) + f"Rejected action {action_id}."
