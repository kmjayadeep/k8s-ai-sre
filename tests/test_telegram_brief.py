import unittest

from app.telegram_brief import action_item_lines, quick_summary_lines


class TelegramBriefTests(unittest.TestCase):
    def test_quick_summary_removes_unclosed_think_block(self) -> None:
        incident = {
            "answer": (
                "<think>hidden reasoning\n"
                "Summary: API latency is high due to saturated CPU.\n"
                "Most likely cause: HPA minReplicas too low."
            )
        }
        lines = quick_summary_lines(incident)
        self.assertEqual("Quick summary: No investigation summary available.", lines[0])
        self.assertEqual("Root cause: Not explicitly identified.", lines[1])

    def test_quick_summary_extracts_summary_and_cause(self) -> None:
        incident = {
            "answer": (
                "Summary: API latency is high due to saturated CPU.\n"
                "Most likely cause: HPA minReplicas too low.\n"
                "Confidence: medium"
            )
        }
        lines = quick_summary_lines(incident)
        self.assertEqual("Quick summary: API latency is high due to saturated CPU.", lines[0])
        self.assertEqual("Root cause: HPA minReplicas too low.", lines[1])

    def test_action_items_fallback_when_empty(self) -> None:
        lines = action_item_lines({"proposed_actions": []})
        self.assertEqual("Action items:", lines[0])
        self.assertIn("No proposed automated remediation", lines[1])

    def test_prefers_structured_brief_fields_when_available(self) -> None:
        incident = {
            "brief": {
                "summary": "Deployment unavailable due to bad image tag.",
                "root_cause": "Container registry tag typo.",
                "action_items": ["Fix image tag in manifest", "Redeploy workload"],
            },
            "answer": "Summary: stale fallback",
            "proposed_actions": [],
        }

        summary_lines = quick_summary_lines(incident)
        action_lines = action_item_lines(incident)

        self.assertEqual("Quick summary: Deployment unavailable due to bad image tag.", summary_lines[0])
        self.assertEqual("Root cause: Container registry tag typo.", summary_lines[1])
        self.assertIn("1. Fix image tag in manifest", action_lines)
        self.assertIn("2. Redeploy workload", action_lines)
