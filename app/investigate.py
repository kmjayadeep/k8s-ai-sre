from agents import Agent, Runner

from app.actions import begin_proposal_capture, finish_proposal_capture
from app.log import log_event
from app.prompts import AGENT_INSTRUCTIONS, build_demo_prompt
from app.tools import (
    collect_investigation_evidence,
    get_k8s_resource,
    get_k8s_resource_events,
    get_pod_logs,
    get_pod_status,
    get_workload_pods,
    list_k8s_resources,
    propose_delete_pod,
    propose_rollout_restart,
    propose_rollout_undo,
    propose_scale,
    query_prometheus,
)
from model_factory import create_groq_model


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
            propose_delete_pod,
            propose_rollout_restart,
            propose_scale,
            propose_rollout_undo,
            query_prometheus,
        ],
    )


async def investigate_target(kind: str, namespace: str, name: str, emit_progress: bool = True) -> dict[str, str]:
    log_event("investigation_started", kind=kind, namespace=namespace, name=name)
    agent = create_agent()
    evidence = collect_investigation_evidence(kind, namespace, name)
    if emit_progress:
        print("Agent: Processing request...")
        print("Collected evidence:")
        print(evidence)

    capture_token = begin_proposal_capture()
    result = await Runner.run(agent, build_demo_prompt(kind, namespace, name) + "\n\nEvidence:\n" + evidence)
    proposed_actions = finish_proposal_capture(capture_token)
    response = {
        "kind": kind,
        "namespace": namespace,
        "name": name,
        "evidence": evidence,
        "answer": result.final_output,
        "proposed_actions": proposed_actions,
        "action_ids": [str(item["action_id"]) for item in proposed_actions],
    }
    log_event("investigation_completed", kind=kind, namespace=namespace, name=name)
    if emit_progress:
        print(f"Agent: {result.final_output}")
    return response
