import asyncio
import sys

from agents import Agent, Runner, set_tracing_disabled
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
    if is_delete_pod_command():
        namespace, pod_name, confirm = get_delete_pod_args()
        print(delete_pod(namespace, pod_name, confirm))
        return

    agent = create_agent()
    await run_investigation(agent, *get_target_from_args())

if __name__ == "__main__":
    asyncio.run(main())
