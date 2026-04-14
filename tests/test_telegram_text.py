import unittest

from app.telegram_text import format_target_lines


class TelegramTextTests(unittest.TestCase):
    def test_format_target_lines_without_cluster(self) -> None:
        incident = {"kind": "deployment", "namespace": "ai-sre-demo", "name": "bad-deploy"}
        self.assertEqual(["Target: deployment ai-sre-demo/bad-deploy"], format_target_lines(incident))

    def test_format_target_lines_with_cluster_name_in_incident(self) -> None:
        incident = {
            "kind": "deployment",
            "namespace": "ai-sre-demo",
            "name": "bad-deploy",
            "cluster_name": "kind-local",
        }
        self.assertEqual(
            ["Target: deployment ai-sre-demo/bad-deploy", "Cluster: kind-local"],
            format_target_lines(incident),
        )
