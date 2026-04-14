import tempfile
import unittest
from asyncio import run
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import app.stores.actions as action_store

from app.investigate import create_agent, investigate_target


class InvestigateTargetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.action_path = Path(self.tempdir.name) / "actions.json"
        self.action_patch = patch.object(action_store, "ACTION_STORE_PATH", self.action_path)
        self.action_patch.start()
        self.addCleanup(self.action_patch.stop)

    def test_deployment_fallback_creates_rollout_restart_action(self) -> None:
        with patch("app.investigate.create_agent", return_value=object()):
            with patch("app.investigate.collect_investigation_evidence", return_value="events and logs"):
                with patch(
                    "app.investigate.Runner.run",
                    new=AsyncMock(return_value=SimpleNamespace(final_output="Summary: unhealthy deployment")),
                ):
                    result = run(investigate_target("deployment", "ai-sre-demo", "bad-deploy", emit_progress=False))

        self.assertEqual(1, len(result["action_ids"]))
        self.assertEqual("rollout-restart", result["proposed_actions"][0]["action_type"])
        self.assertEqual("bad-deploy", result["proposed_actions"][0]["name"])

    def test_pod_fallback_creates_delete_pod_action(self) -> None:
        with patch("app.investigate.create_agent", return_value=object()):
            with patch("app.investigate.collect_investigation_evidence", return_value="pod crashloop"):
                with patch(
                    "app.investigate.Runner.run",
                    new=AsyncMock(return_value=SimpleNamespace(final_output="Summary: pod is crash looping")),
                ):
                    result = run(investigate_target("pod", "ai-sre-demo", "crashy", emit_progress=False))

        self.assertEqual(1, len(result["action_ids"]))
        self.assertEqual("delete-pod", result["proposed_actions"][0]["action_type"])
        self.assertEqual("crashy", result["proposed_actions"][0]["name"])

    def test_unknown_kind_without_model_proposal_remains_empty(self) -> None:
        with patch("app.investigate.create_agent", return_value=object()):
            with patch("app.investigate.collect_investigation_evidence", return_value="statefulset evidence"):
                with patch(
                    "app.investigate.Runner.run",
                    new=AsyncMock(return_value=SimpleNamespace(final_output="Summary: gathered evidence")),
                ):
                    result = run(investigate_target("statefulset", "ai-sre-demo", "db", emit_progress=False))

        self.assertEqual([], result["action_ids"])
        self.assertEqual([], result["proposed_actions"])

    def test_create_agent_disables_reasoning_effort(self) -> None:
        with patch("app.investigate.create_model", return_value="mock-model"):
            agent = create_agent()

        self.assertIsNotNone(agent.model_settings.reasoning)
        self.assertEqual("none", agent.model_settings.reasoning.effort)
