import json
import unittest
from pathlib import Path
from urllib.parse import parse_qs
from unittest.mock import patch

import app.telegram as telegram
from app.notifier import send_telegram_notification


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "telegram_contract_regressions.json"


class _FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return b'{"ok": true}'


class TelegramOutputContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixtures = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def _render_notification_text(self, incident: dict[str, object]) -> str:
        with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "token", "TELEGRAM_CHAT_ID": "123"}, clear=False):
            with patch("app.notifier.urllib.request.urlopen", return_value=_FakeResponse()) as urlopen:
                status = send_telegram_notification(incident)
        self.assertEqual("Telegram notification sent.", status)
        request = urlopen.call_args.args[0]
        payload = parse_qs(request.data.decode("utf-8"))
        return payload["text"][0]

    def test_notification_contract_regressions(self) -> None:
        for case in self.fixtures:
            with self.subTest(case=case["name"]):
                text = self._render_notification_text(case["incident"])
                self.assertIn("Incident ", text)
                self.assertIn("Target:", text)
                self.assertIn("Quick summary:", text)
                self.assertIn("Root cause:", text)
                self.assertIn("Action items:", text)
                for expected in case["assert_contains"]:
                    self.assertIn(expected, text)
                for unexpected in case["assert_not_contains"]:
                    self.assertNotIn(unexpected, text)

    def test_incident_command_contract_regressions(self) -> None:
        for case in self.fixtures:
            with self.subTest(case=case["name"]):
                incident = dict(case["incident"])
                incident_id = str(incident["incident_id"])
                with patch("app.telegram.get_incident", return_value=incident):
                    text = telegram._handle_command(f"/incident {incident_id}")

                self.assertIn(f"Incident {incident_id}", text)
                self.assertIn("Target:", text)
                self.assertIn("Quick summary:", text)
                self.assertIn("Root cause:", text)
                self.assertIn("Action items:", text)
                for expected in case["assert_contains"]:
                    self.assertIn(expected, text)
                for unexpected in case["assert_not_contains"]:
                    self.assertNotIn(unexpected, text)


if __name__ == "__main__":
    unittest.main()
