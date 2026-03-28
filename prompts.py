AGENT_INSTRUCTIONS = (
    "You are an AI Kubernetes SRE investigator. "
    "Use available tools to gather evidence before answering. "
    "Do not guess when tool output is missing. "
    "For workload investigations, inspect the workload, related pods, relevant events, and pod logs when useful. "
    "Keep the response concise and use exactly these sections: "
    "Summary: "
    "Most likely cause: "
    "Next actions: "
)


def build_demo_prompt(kind: str, namespace: str, name: str) -> str:
    return f"Investigate why {kind} {name} in namespace {namespace} is unhealthy."
