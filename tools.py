import json
import os
import subprocess
import urllib.error
import urllib.parse
import urllib.request

from agents import function_tool


def _run_kubectl(command: list[str]) -> tuple[bool, str]:
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    output = result.stdout.strip() or result.stderr.strip()
    return result.returncode == 0, output


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
    ok, output = _run_kubectl(command)
    if not ok:
        return None
    return json.loads(output)


def _list_resource_items(kind: str, namespace: str, label_selector: str = "") -> list[dict]:
    command = [
        "kubectl",
        "get",
        kind.lower(),
        "-n",
        namespace,
        "-o",
        "json",
    ]
    if label_selector:
        command.extend(["-l", label_selector])
    ok, output = _run_kubectl(command)
    if not ok:
        return []
    return json.loads(output).get("items", [])


def delete_pod(namespace: str, pod_name: str, confirm: bool) -> str:
    """Deletes a pod only when explicit confirmation is provided."""
    if not confirm:
        return (
            f"Refusing to delete pod {pod_name} in namespace {namespace} without --confirm. "
            f"Re-run with: uv run main.py delete-pod {namespace} {pod_name} --confirm"
        )

    command = ["kubectl", "delete", "pod", pod_name, "-n", namespace]
    ok, output = _run_kubectl(command)
    if not ok:
        return f"Failed to delete pod {pod_name} in namespace {namespace}: {output}"
    return output


def _summarize_k8s_resource(api_version: str, kind: str, namespace: str, name: str) -> str:
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
        selector = spec.get("selector", {}).get("matchLabels", {})
        selector_text = ",".join(f"{key}={value}" for key, value in selector.items()) or "none"
        return (
            f"{kind} {name} in namespace {namespace} with apiVersion {api_version}. "
            f"Desired replicas: {spec.get('replicas', 'Unknown')}. "
            f"Ready replicas: {status.get('readyReplicas', 0)}. "
            f"Available replicas: {status.get('availableReplicas', 0)}. "
            f"Observed generation: {status.get('observedGeneration', 'Unknown')}. "
            f"Generation: {metadata.get('generation', 'Unknown')}. "
            f"Selector: {selector_text}."
        )

    return (
        f"{kind} {name} in namespace {namespace} with apiVersion {api_version}. "
        f"metadata.generation: {metadata.get('generation', 'Unknown')}. "
        f"spec keys: {sorted(spec.keys())}. "
        f"status keys: {sorted(status.keys())}."
    )


def _get_workload_pod_names(namespace: str, workload_kind: str, workload_name: str) -> list[str]:
    if workload_kind.lower() != "deployment":
        return []
    deployment = _kubectl_get_json("deployment", namespace, workload_name)
    if deployment is None:
        return []
    selector = deployment.get("spec", {}).get("selector", {}).get("matchLabels", {})
    if not selector:
        return []
    label_selector = ",".join(f"{key}={value}" for key, value in selector.items())
    items = _list_resource_items("pods", namespace, label_selector)
    return [item.get("metadata", {}).get("name", "unknown") for item in items]


def _query_prometheus(query: str) -> str:
    base_url = os.getenv("PROMETHEUS_BASE_URL", "").strip()
    if not base_url:
        return "Prometheus is not configured. Set PROMETHEUS_BASE_URL to enable metrics queries."

    url = base_url.rstrip("/") + "/api/v1/query?" + urllib.parse.urlencode({"query": query})
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        return f"Failed to query Prometheus: {exc}"

    if payload.get("status") != "success":
        return f"Prometheus query failed: {json.dumps(payload)}"

    results = payload.get("data", {}).get("result", [])
    if not results:
        return f"Prometheus query returned no data for: {query}"

    compact = []
    for item in results[:5]:
        metric = item.get("metric", {})
        value = item.get("value", [])
        compact.append(f"metric={metric}, value={value}")
    return "Prometheus results: " + " | ".join(compact)


def _summarize_resource_events(kind: str, namespace: str, name: str) -> str:
    command = [
        "kubectl",
        "get",
        "events",
        "-n",
        namespace,
        "--field-selector",
        f"involvedObject.kind={kind},involvedObject.name={name}",
        "--sort-by=.lastTimestamp",
        "-o",
        "json",
    ]
    ok, output = _run_kubectl(command)
    if not ok:
        return f"Failed to fetch events for {kind} {name} in namespace {namespace}: {output}"

    payload = json.loads(output)
    items = payload.get("items", [])
    if not items:
        return f"No events found for {kind} {name} in namespace {namespace}."

    recent = items[-5:]
    messages = [
        f"{item.get('reason', 'UnknownReason')}: {item.get('message', '').strip()}"
        for item in recent
    ]
    return f"Recent events for {kind} {name} in namespace {namespace}: " + " | ".join(messages)


def _summarize_pod_logs(namespace: str, pod_name: str, container: str = "") -> str:
    command = [
        "kubectl",
        "logs",
        pod_name,
        "-n",
        namespace,
        "--tail",
        "30",
    ]
    if container:
        command.extend(["-c", container])

    ok, output = _run_kubectl(command)
    if not ok:
        return f"Failed to fetch logs for pod {pod_name} in namespace {namespace}: {output}"
    if not output:
        return f"No logs returned for pod {pod_name} in namespace {namespace}."
    return f"Recent logs for pod {pod_name} in namespace {namespace}: {output}"


def _summarize_workload_pods(namespace: str, workload_kind: str, workload_name: str) -> str:
    if workload_kind.lower() != "deployment":
        return f"Workload pod lookup is currently supported only for Deployment, not {workload_kind}."
    pod_names = _get_workload_pod_names(namespace, workload_kind, workload_name)
    if not pod_names:
        return f"No pods found for Deployment {workload_name} in namespace {namespace}."

    items = []
    for pod_name in pod_names:
        pod = _kubectl_get_json("pod", namespace, pod_name)
        if pod:
            items.append(pod)

    pod_summaries = []
    for item in items:
        pod_name = item.get("metadata", {}).get("name", "unknown")
        pod_phase = item.get("status", {}).get("phase", "Unknown")
        pod_summaries.append(f"{pod_name} ({pod_phase})")

    return f"Pods for Deployment {workload_name} in namespace {namespace}: " + ", ".join(pod_summaries)


def collect_investigation_evidence(kind: str, namespace: str, name: str) -> str:
    """Collects a small evidence bundle in Python before handing off to the model."""
    normalized_kind = kind.capitalize()
    sections = [
        f"Target: {normalized_kind} {name} in namespace {namespace}",
        f"Resource: {_summarize_k8s_resource('v1' if normalized_kind == 'Pod' else 'apps/v1', normalized_kind, namespace, name)}",
        f"Events: {_summarize_resource_events(normalized_kind, namespace, name)}",
    ]

    if normalized_kind == "Deployment":
        sections.append(f"Related pods: {_summarize_workload_pods(namespace, 'Deployment', name)}")
        pod_names = _get_workload_pod_names(namespace, "Deployment", name)
        if pod_names:
            first_pod = pod_names[0]
            sections.append(f"First pod details: {_summarize_k8s_resource('v1', 'Pod', namespace, first_pod)}")
            sections.append(f"First pod events: {_summarize_resource_events('Pod', namespace, first_pod)}")
            sections.append(f"First pod logs: {_summarize_pod_logs(namespace, first_pod)}")
        sections.append(
            "Metrics: " + _query_prometheus(f'kube_deployment_status_replicas_unavailable{{namespace="{namespace}",deployment="{name}"}}')
        )

    if normalized_kind == "Pod":
        sections.append(f"Pod logs: {_summarize_pod_logs(namespace, name)}")

    return "\n".join(sections)


@function_tool
def get_k8s_resource(api_version: str, kind: str, namespace: str, name: str) -> str:
    """Returns a compact real Kubernetes resource summary using kubectl."""
    return _summarize_k8s_resource(api_version, kind, namespace, name)


@function_tool
def get_pod_status(namespace: str, pod_name: str) -> str:
    """Returns real pod status data from kubectl for local testing."""
    return _summarize_k8s_resource("v1", "Pod", namespace, pod_name)


@function_tool
def list_k8s_resources(api_version: str, kind: str, namespace: str, label_selector: str = "") -> str:
    """Lists Kubernetes resources using kubectl."""
    items = _list_resource_items(kind, namespace, label_selector)
    if not items:
        return f"No {kind} resources found in namespace {namespace}."

    names = [item.get("metadata", {}).get("name", "unknown") for item in items]
    return f"{kind} resources in namespace {namespace}: {', '.join(names)}."


@function_tool
def get_workload_pods(namespace: str, workload_kind: str, workload_name: str) -> str:
    """Lists pods selected by a workload, currently supporting Deployments."""
    return _summarize_workload_pods(namespace, workload_kind, workload_name)


@function_tool
def get_k8s_resource_events(kind: str, namespace: str, name: str) -> str:
    """Fetches recent events for a Kubernetes object."""
    return _summarize_resource_events(kind, namespace, name)


@function_tool
def get_pod_logs(namespace: str, pod_name: str, container: str = "") -> str:
    """Fetches recent logs for a pod."""
    return _summarize_pod_logs(namespace, pod_name, container)


@function_tool
def query_prometheus(query: str) -> str:
    """Runs a Prometheus instant query if PROMETHEUS_BASE_URL is configured."""
    return _query_prometheus(query)
