import asyncio

from agents import Agent, Runner, set_tracing_disabled
from model_factory import create_groq_model
from prompts import AGENT_INSTRUCTIONS, DEMO_PROMPT
from tools import (
    get_k8s_resource,
    get_k8s_resource_events,
    get_pod_logs,
    get_pod_status,
    list_k8s_resources,
)

set_tracing_disabled(True)

async def main():
    model = create_groq_model()

    agent = Agent(
        name="K8s SRE Investigator",
        instructions=AGENT_INSTRUCTIONS,
        model=model,
        tools=[get_k8s_resource, get_pod_status, list_k8s_resources, get_k8s_resource_events, get_pod_logs],
    )

    print("Agent: Processing request...")
    result = await Runner.run(agent, DEMO_PROMPT)

    print(f"Agent: {result.final_output}")

if __name__ == "__main__":
    asyncio.run(main())
