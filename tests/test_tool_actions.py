import unittest
from unittest.mock import patch

import app.tools.actions as tool_actions


class ToolActionSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.env_patch = patch.dict("os.environ", {"WRITE_ALLOWED_NAMESPACES": "ai-sre-demo"}, clear=False)
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)

    def test_delete_pod_refuses_when_write_namespaces_unset(self) -> None:
        with patch.dict("os.environ", {"WRITE_ALLOWED_NAMESPACES": ""}, clear=False):
            with patch("app.tools.actions._run_kubectl") as run_kubectl:
                result = tool_actions.delete_pod("ai-sre-demo", "crashy", confirm=True)

        self.assertIn("namespace is not in WRITE_ALLOWED_NAMESPACES", result)
        run_kubectl.assert_not_called()

    def test_scale_refuses_negative_replicas(self) -> None:
        result = tool_actions.scale_deployment("ai-sre-demo", "bad-deploy", -1, confirm=True)
        self.assertIn("replicas must be >= 0", result)

    def test_scale_refuses_when_deployment_not_found(self) -> None:
        run_results = [
            (True, "yes"),
            (False, 'Error from server (NotFound): deployments.apps "bad-deploy" not found'),
        ]
        with patch("app.tools.actions._run_kubectl", side_effect=run_results):
            result = tool_actions.scale_deployment("ai-sre-demo", "bad-deploy", 3, confirm=True)

        self.assertIn("deployment was not found or not readable", result)
        self.assertIn("NotFound", result)

    def test_rollout_undo_refuses_when_deployment_not_found(self) -> None:
        run_results = [
            (True, "yes"),
            (False, 'Error from server (NotFound): deployments.apps "bad-deploy" not found'),
        ]
        with patch("app.tools.actions._run_kubectl", side_effect=run_results):
            result = tool_actions.rollout_undo_deployment("ai-sre-demo", "bad-deploy", confirm=True)

        self.assertIn("deployment was not found or not readable", result)
        self.assertIn("NotFound", result)

    def test_scale_runs_after_deployment_existence_check(self) -> None:
        run_results = [
            (True, "yes"),
            (True, 'deployment.apps "bad-deploy"'),
            (True, 'deployment.apps/bad-deploy scaled'),
        ]
        with patch("app.tools.actions._run_kubectl", side_effect=run_results) as run_kubectl:
            result = tool_actions.scale_deployment("ai-sre-demo", "bad-deploy", 2, confirm=True)

        self.assertEqual('deployment.apps/bad-deploy scaled', result)
        self.assertEqual(3, run_kubectl.call_count)

    def test_scale_refuses_when_rbac_denies(self) -> None:
        with patch("app.tools.actions._run_kubectl", return_value=(True, "no")):
            result = tool_actions.scale_deployment("ai-sre-demo", "bad-deploy", 2, confirm=True)

        self.assertIn("authorization denied by cluster RBAC", result)

    def test_scale_refuses_when_rbac_response_is_ambiguous(self) -> None:
        with patch("app.tools.actions._run_kubectl", return_value=(True, "maybe")):
            result = tool_actions.scale_deployment("ai-sre-demo", "bad-deploy", 2, confirm=True)

        self.assertIn("authorization check ambiguous", result)
