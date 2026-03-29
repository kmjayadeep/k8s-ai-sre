import asyncio
import sys

from agents import Agent, Runner, set_tracing_disabled
from action_store import create_action, get_action, update_action_status
from model_factory import create_groq_model
from prompts import AGENT_INSTRUCTIONS, build_demo_prompt
from tools import (
    collect_investigation_evidence,
    delete_pod,
    get_k8s_resource,
    get_k8s_resource_events,
    get_pod_logs,
    get_pod_status,
    get_workload_pods,
    list_k8s_resources,
    query_prometheus,
)

set_tracing_disabled(True)


def get_target_from_args() -> tuple[str, str, str]:
    if len(sys.argv) == 4:
        kind, namespace, name = sys.argv[1], sys.argv[2], sys.argv[3]
        return kind, namespace, name
    return "deployment", "ai-sre-demo", "bad-deploy"


def is_delete_pod_command() -> bool:
    return len(sys.argv) >= 4 and sys.argv[1] == "delete-pod"


def get_delete_pod_args() -> tuple[str, str, bool]:
    namespace = sys.argv[2]
    pod_name = sys.argv[3]
    confirm = len(sys.argv) >= 5 and sys.argv[4] == "--confirm"
    return namespace, pod_name, confirm


def is_propose_delete_pod_command() -> bool:
    return len(sys.argv) == 4 and sys.argv[1] == "propose-delete-pod"


def is_approve_command() -> bool:
    return len(sys.argv) == 3 and sys.argv[1] == "approve"


def is_reject_command() -> bool:
    return len(sys.argv) == 3 and sys.argv[1] == "reject"


def create_agent() -> Agent:
    model = create_groq_model()
    return Agent(
        name="K8s SRE Investigator",
        instructions=AGENT_INSTRUCTIONS,
        model=model,
        tools=[
            get_k8s_resource,
            get_pod_status,
            list_k8s_resources,
            get_workload_pods,
            get_k8s_resource_events,
            get_pod_logs,
            query_prometheus,
        ],
    )


async def run_investigation(agent: Agent, kind: str, namespace: str, name: str) -> None:
    print("Agent: Processing request...")
    evidence = collect_investigation_evidence(kind, namespace, name)
    print("Collected evidence:")
    print(evidence)
    result = await Runner.run(
        agent,
        build_demo_prompt(kind, namespace, name) + "\n\nEvidence:\n" + evidence,
    )

    print(f"Agent: {result.final_output}")

async def main():
    if is_propose_delete_pod_command():
        namespace, pod_name = sys.argv[2], sys.argv[3]
        action = create_action("delete-pod", namespace, pod_name)
        print(
            f"Created action {action['id']} to delete pod {pod_name} in namespace {namespace}.\n"
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
        if action["type"] == "delete-pod":
            result = delete_pod(action["namespace"], action["name"], confirm=True)
            update_action_status(action_id, "approved")
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
        print(f"Rejected action {action_id}.")
        return

    if is_delete_pod_command():
        namespace, pod_name, confirm = get_delete_pod_args()
        print(delete_pod(namespace, pod_name, confirm))
        return

    agent = create_agent()
    await run_investigation(agent, *get_target_from_args())

if __name__ == "__main__":
    asyncio.run(main())
