import asyncio
import json
import subprocess

from agents import Agent, Runner, set_tracing_disabled, function_tool
from model_factory import create_groq_model

set_tracing_disabled(True)


def _kubectl_get_json(resource_type: str, namespace: str, name: str) -> dict | None:
    command = [
        "kubectl",
        "get",
        resource_type,
        name,
        "-n",
        namespace,
        "-o",
        "json",
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return None
    return json.loads(result.stdout)


@function_tool
def get_k8s_resource(api_version: str, kind: str, namespace: str, name: str) -> str:
    """Returns a compact real Kubernetes resource summary using kubectl."""
    resource = _kubectl_get_json(kind.lower(), namespace, name)
    if resource is None:
        return f"Failed to fetch {kind} {name} in namespace {namespace}."

    metadata = resource.get("metadata", {})
    spec = resource.get("spec", {})
    status = resource.get("status", {})

    if kind == "Pod":
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
            f"{kind} {name} in namespace {namespace} with apiVersion {api_version}. "
            f"Phase: {status.get('phase', 'Unknown')}. "
            f"Restart count: {restart_count}. "
            f"Primary state reason: {primary_state}. "
            f"Node: {resource.get('spec', {}).get('nodeName', 'Unknown')}."
        )

    if kind == "Deployment":
        return (
            f"{kind} {name} in namespace {namespace} with apiVersion {api_version}. "
            f"Desired replicas: {spec.get('replicas', 'Unknown')}. "
            f"Ready replicas: {status.get('readyReplicas', 0)}. "
            f"Available replicas: {status.get('availableReplicas', 0)}. "
            f"Observed generation: {status.get('observedGeneration', 'Unknown')}. "
            f"Generation: {metadata.get('generation', 'Unknown')}."
        )

    return (
        f"{kind} {name} in namespace {namespace} with apiVersion {api_version}. "
        f"metadata.generation: {metadata.get('generation', 'Unknown')}. "
        f"spec keys: {sorted(spec.keys())}. "
        f"status keys: {sorted(status.keys())}."
    )


@function_tool
def get_pod_status(namespace: str, pod_name: str) -> str:
    """Returns real pod status data from kubectl for local testing."""
    return get_k8s_resource("v1", "Pod", namespace, pod_name)

async def main():
    model = create_groq_model()

    agent = Agent(
        name="K8s SRE Investigator",
        instructions=(
            "You are an AI Kubernetes SRE investigator. "
            "Use available tools to gather evidence before answering. "
            "Do not guess when tool output is missing. "
            "Keep the response concise and use exactly these sections: "
            "Summary: "
            "Most likely cause: "
            "Next actions: "
        ),
        model=model,
        tools=[get_k8s_resource, get_pod_status],
    )

    print("Agent: Processing request...")
    result = await Runner.run(
        agent,
        "Investigate why deployment bad-deploy in namespace ai-sre-demo is unhealthy.",
    )

    print(f"Agent: {result.final_output}")

if __name__ == "__main__":
    asyncio.run(main())
