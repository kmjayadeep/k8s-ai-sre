import asyncio
import json
import subprocess

from agents import Agent, Runner, set_tracing_disabled, function_tool
from model_factory import create_groq_model

set_tracing_disabled(True)


@function_tool
def get_pod_status(namespace: str, pod_name: str) -> str:
    """Returns real pod status data from kubectl for local testing."""
    command = [
        "kubectl",
        "get",
        "pod",
        pod_name,
        "-n",
        namespace,
        "-o",
        "json",
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        error = result.stderr.strip() or result.stdout.strip() or "unknown kubectl error"
        return f"Failed to fetch pod {pod_name} in namespace {namespace}: {error}"

    pod = json.loads(result.stdout)
    status = pod.get("status", {})
    spec = pod.get("spec", {})
    container_statuses = status.get("containerStatuses", [])

    restart_count = sum(container.get("restartCount", 0) for container in container_statuses)
    primary_state = "unknown"
    for container in container_statuses:
        state = container.get("state", {})
        if state.get("waiting"):
            primary_state = state["waiting"].get("reason", "waiting")
            break
        if state.get("terminated"):
            primary_state = state["terminated"].get("reason", "terminated")
            break
        if state.get("running"):
            primary_state = "Running"

    return (
        f"Pod {pod_name} in namespace {namespace}. "
        f"Phase: {status.get('phase', 'Unknown')}. "
        f"Restart count: {restart_count}. "
        f"Primary state reason: {primary_state}. "
        f"Node: {spec.get('nodeName', 'Unknown')}."
    )

async def main():
    model = create_groq_model()

    agent = Agent(
        name="K8s SRE Investigator",
        instructions=(
            "You are an AI Kubernetes SRE investigator. "
            "Use available tools to gather evidence before answering. "
            "You can investigate both built-in Kubernetes resources and custom resources. "
            "When you respond, include: "
            "1. a short summary, "
            "2. the most likely cause, and "
            "3. recommended next actions."
        ),
        model=model,
        tools=[get_pod_status],
    )

    print("Agent: Processing request...")
    result = await Runner.run(
        agent,
        "Investigate why pod crashy in namespace ai-sre-demo is unhealthy.",
    )

    print(f"Agent: {result.final_output}")

if __name__ == "__main__":
    asyncio.run(main())
