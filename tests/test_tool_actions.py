import unittest
from unittest.mock import patch

import app.tools.actions as tool_actions


class ToolActionSafetyTests(unittest.TestCase):
    def test_scale_refuses_negative_replicas(self) -> None:
        result = tool_actions.scale_deployment("ai-sre-demo", "bad-deploy", -1, confirm=True)
        self.assertIn("replicas must be >= 0", result)

    def test_scale_refuses_when_deployment_not_found(self) -> None:
        with patch("app.tools.actions._run_kubectl", return_value=(False, 'Error from server (NotFound): deployments.apps "bad-deploy" not found')):
            result = tool_actions.scale_deployment("ai-sre-demo", "bad-deploy", 3, confirm=True)

        self.assertIn("deployment was not found or not readable", result)
        self.assertIn("NotFound", result)

    def test_rollout_undo_refuses_when_deployment_not_found(self) -> None:
        with patch("app.tools.actions._run_kubectl", return_value=(False, 'Error from server (NotFound): deployments.apps "bad-deploy" not found')):
            result = tool_actions.rollout_undo_deployment("ai-sre-demo", "bad-deploy", confirm=True)

        self.assertIn("deployment was not found or not readable", result)
        self.assertIn("NotFound", result)

    def test_scale_runs_after_deployment_existence_check(self) -> None:
        run_results = [
            (True, 'deployment.apps "bad-deploy"'),
            (True, 'deployment.apps/bad-deploy scaled'),
        ]
        with patch("app.tools.actions._run_kubectl", side_effect=run_results) as run_kubectl:
            result = tool_actions.scale_deployment("ai-sre-demo", "bad-deploy", 2, confirm=True)

        self.assertEqual('deployment.apps/bad-deploy scaled', result)
        self.assertEqual(2, run_kubectl.call_count)
