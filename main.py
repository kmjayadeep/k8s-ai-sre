import asyncio
from agents import Agent, Runner, set_tracing_disabled, function_tool
from model_factory import create_groq_model

set_tracing_disabled(True)

@function_tool
def get_pod_status(namespace: str, pod_name: str) -> str:
    """Returns fake Kubernetes pod status data for local testing."""
    fake_pods = {
        ("payments", "api-123"): {
            "phase": "Running",
            "restarts": 7,
            "reason": "CrashLoopBackOff",
            "event": "Back-off restarting failed container",
        },
        ("checkout", "worker-456"): {
            "phase": "Pending",
            "restarts": 0,
            "reason": "Unschedulable",
            "event": "0/3 nodes are available: insufficient memory",
        },
    }

    pod = fake_pods.get((namespace, pod_name))
    if not pod:
        return f"Pod {pod_name} in namespace {namespace} was not found."

    return (
        f"Pod {pod_name} in namespace {namespace} is {pod['phase']}. "
        f"Restart count: {pod['restarts']}. "
        f"Current reason: {pod['reason']}. "
        f"Recent event: {pod['event']}."
    )

async def main():
    model = create_groq_model()

    agent = Agent(
        name="K8s Assistant",
        instructions="You are a Kubernetes assistant. Use the available tools to answer questions about pod health.",
        model=model,
        tools=[get_pod_status],
    )

    print("Agent: Processing request...")
    result = await Runner.run(
        agent,
        "Investigate why pod api-123 in namespace payments is unhealthy.",
    )

    print(f"Agent: {result.final_output}")

if __name__ == "__main__":
    asyncio.run(main())
