import unittest

from agents.tool import FunctionTool
from app.tools.k8s import get_pod_status


class K8sToolsTests(unittest.TestCase):
    """Tests for Kubernetes tools."""

    def test_get_pod_status_is_function_tool(self) -> None:
        """Verify get_pod_status is a FunctionTool."""
        self.assertIsInstance(get_pod_status, FunctionTool)
        self.assertEqual(get_pod_status.name, "get_pod_status")
