from agents import Agent, Runner

from app.actions import begin_proposal_capture, finish_proposal_capture, propose_action
from app.investigation_brief import parse_investigation_brief
from app.log import log_event
from app.prompts import AGENT_INSTRUCTIONS, build_demo_prompt
from app.tools.k8s import (
    collect_investigation_evidence,
    get_k8s_resource,
    get_k8s_resource_events,
    get_pod_logs,
    get_pod_status,
    get_workload_pods,
    list_k8s_resources,
    query_prometheus,
)
from app.tools.proposals import propose_delete_pod, propose_rollout_restart, propose_rollout_undo, propose_scale
from model_factory import create_model


def _create_deterministic_fallback_proposal(kind: str, namespace: str, name: str) -> str | None:
    normalized_kind = kind.strip().lower()
    if normalized_kind == "deployment":
        propose_action("rollout-restart", namespace, name)
        return "rollout-restart"
    if normalized_kind == "pod":
        propose_action("delete-pod", namespace, name)
        return "delete-pod"
    return None


def create_agent() -> Agent:
    model = create_model()
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


async def investigate_target(kind: str, namespace: str, name: str, emit_progress: bool = True) -> dict[str, object]:
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
    fallback_action_type: str | None = None
    if not proposed_actions:
        fallback_token = begin_proposal_capture()
        fallback_action_type = _create_deterministic_fallback_proposal(kind, namespace, name)
        proposed_actions = finish_proposal_capture(fallback_token)
        if proposed_actions and fallback_action_type is not None:
            log_event(
                "investigation_fallback_proposal_created",
                kind=kind,
                namespace=namespace,
                name=name,
                action_type=fallback_action_type,
            )
    raw_output = str(result.final_output)
    response = {
        "kind": kind,
        "namespace": namespace,
        "name": name,
        "evidence": evidence,
        "answer": raw_output,
        "brief": parse_investigation_brief(raw_output),
        "proposed_actions": proposed_actions,
        "action_ids": [str(item["action_id"]) for item in proposed_actions],
    }
    log_event("investigation_completed", kind=kind, namespace=namespace, name=name)
    if emit_progress:
        print(f"Agent: {result.final_output}")
    return response
