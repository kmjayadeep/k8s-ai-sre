import unittest

from app.investigation_brief import parse_investigation_brief


class InvestigationBriefParserTests(unittest.TestCase):
    def test_parses_direct_json_payload(self) -> None:
        payload = (
            '{"summary":"Image pull backoff blocks rollout.",' 
            '"root_cause":"Deployment references a missing image tag.",' 
            '"confidence":"high",' 
            '"action_items":["Verify image tag in registry","Redeploy with valid tag"]}'
        )
        result = parse_investigation_brief(payload)
        self.assertEqual("Image pull backoff blocks rollout.", result["summary"])
        self.assertEqual("Deployment references a missing image tag.", result["root_cause"])
        self.assertEqual("high", result["confidence"])
        self.assertEqual(["Verify image tag in registry", "Redeploy with valid tag"], result["action_items"])

    def test_parses_json_when_prefixed_with_text(self) -> None:
        payload = "Investigation result:\n{\"summary\":\"Pod crashloop\",\"root_cause\":\"OOMKilled\",\"confidence\":\"medium\",\"action_items\":[\"Increase memory limit\"]}"
        result = parse_investigation_brief(payload)
        self.assertEqual("Pod crashloop", result["summary"])
        self.assertEqual(["Increase memory limit"], result["action_items"])

    def test_returns_empty_for_non_json_payload(self) -> None:
        self.assertEqual({}, parse_investigation_brief("Summary: text only"))
