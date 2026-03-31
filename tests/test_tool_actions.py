import unittest
from unittest.mock import patch

import app.tools.actions as tool_actions


class ToolActionGuardsTests(unittest.TestCase):
    def test_rollout_undo_refuses_when_target_deployment_is_missing(self) -> None:
        with patch("app.tools.actions._allowed_to_write", return_value=True):
            with patch("app.tools.actions._run_kubectl", return_value=(False, "not found")) as run_kubectl:
                result = tool_actions.rollout_undo_deployment("ai-sre-demo", "bad-deploy", confirm=True)

        self.assertIn("Refusing to undo deployment bad-deploy", result)
        self.assertIn("does not exist", result)
        run_kubectl.assert_called_once_with(["kubectl", "get", "deployment", "bad-deploy", "-n", "ai-sre-demo"])

    def test_rollout_undo_checks_target_before_undo(self) -> None:
        with patch("app.tools.actions._allowed_to_write", return_value=True):
            with patch(
                "app.tools.actions._run_kubectl",
                side_effect=[(True, "deployment.apps/bad-deploy"), (True, 'deployment.apps/"bad-deploy" rolled back')],
            ) as run_kubectl:
                result = tool_actions.rollout_undo_deployment("ai-sre-demo", "bad-deploy", confirm=True)

        self.assertIn("rolled back", result)
        self.assertEqual(
            [
                (["kubectl", "get", "deployment", "bad-deploy", "-n", "ai-sre-demo"],),
                (["kubectl", "rollout", "undo", "deployment/bad-deploy", "-n", "ai-sre-demo"],),
            ],
            [call.args for call in run_kubectl.call_args_list],
        )
