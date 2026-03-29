import json
from pathlib import Path
from uuid import uuid4


ACTION_STORE_PATH = Path("/tmp/k8s-ai-sre-actions.json")


def _load_actions() -> dict[str, dict]:
    if not ACTION_STORE_PATH.exists():
        return {}
    return json.loads(ACTION_STORE_PATH.read_text(encoding="utf-8"))


def _save_actions(actions: dict[str, dict]) -> None:
    ACTION_STORE_PATH.write_text(json.dumps(actions, indent=2, sort_keys=True), encoding="utf-8")


def create_action(action_type: str, namespace: str, name: str) -> dict:
    actions = _load_actions()
    action_id = uuid4().hex[:8]
    action = {
        "id": action_id,
        "type": action_type,
        "namespace": namespace,
        "name": name,
        "status": "pending",
    }
    actions[action_id] = action
    _save_actions(actions)
    return action


def get_action(action_id: str) -> dict | None:
    return _load_actions().get(action_id)


def update_action_status(action_id: str, status: str) -> dict | None:
    actions = _load_actions()
    action = actions.get(action_id)
    if action is None:
        return None
    action["status"] = status
    actions[action_id] = action
    _save_actions(actions)
    return action
