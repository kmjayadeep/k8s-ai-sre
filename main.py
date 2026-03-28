import asyncio
import sys

from agents import Agent, Runner, set_tracing_disabled
from model_factory import create_groq_model
from prompts import AGENT_INSTRUCTIONS, build_demo_prompt
from tools import (
    get_k8s_resource,
    get_k8s_resource_events,
    get_pod_logs,
    get_pod_status,
    get_workload_pods,
    list_k8s_resources,
)

set_tracing_disabled(True)


def get_target_from_args() -> tuple[str, str, str]:
    if len(sys.argv) == 4:
        kind, namespace, name = sys.argv[1], sys.argv[2], sys.argv[3]
        return kind, namespace, name
    return "deployment", "ai-sre-demo", "bad-deploy"


async def main():
    model = create_groq_model()
    kind, namespace, name = get_target_from_args()

    agent = Agent(
        name="K8s SRE Investigator",
        instructions=AGENT_INSTRUCTIONS,
        model=model,
        tools=[get_k8s_resource, get_pod_status, list_k8s_resources, get_workload_pods, get_k8s_resource_events, get_pod_logs],
    )

    print("Agent: Processing request...")
    result = await Runner.run(agent, build_demo_prompt(kind, namespace, name))

    print(f"Agent: {result.final_output}")

if __name__ == "__main__":
    asyncio.run(main())
