import unittest
from unittest.mock import MagicMock
from unittest.mock import patch

import app.telegram as telegram


class TelegramCommandParsingTests(unittest.TestCase):
    def test_approve_command_strips_bot_mention(self) -> None:
        with patch("app.telegram.approve_action", return_value="ok") as approve_action:
            reply = telegram._handle_command("/approve@k8s_ai_sre_bot f314980d")

        self.assertEqual("ok", reply)
        approve_action.assert_called_once_with("f314980d")

    def test_reject_command_strips_bot_mention(self) -> None:
        with patch("app.telegram.reject_action", return_value="rejected") as reject_action:
            reply = telegram._handle_command("/reject@k8s_ai_sre_bot f314980d")

        self.assertEqual("rejected", reply)
        reject_action.assert_called_once_with("f314980d")

    def test_start_telegram_polling_thread_skips_when_token_missing(self) -> None:
        with patch("app.telegram._telegram_token", return_value=None):
            thread = telegram.start_telegram_polling_thread()

        self.assertIsNone(thread)

    def test_start_telegram_polling_thread_starts_when_enabled(self) -> None:
        fake_thread = MagicMock()
        with patch("app.telegram._telegram_token", return_value="token"):
            with patch("app.telegram.threading.Thread", return_value=fake_thread) as thread_cls:
                thread = telegram.start_telegram_polling_thread()

        self.assertIs(thread, fake_thread)
        thread_cls.assert_called_once()
        fake_thread.start.assert_called_once()

    def test_approve_command_requires_action_id(self) -> None:
        reply = telegram._handle_command("/approve")

        self.assertEqual("Usage: /approve <action-id>", reply)

    def test_incident_command_rejects_extra_arguments(self) -> None:
        reply = telegram._handle_command("/incident abc def")

        self.assertEqual("Usage: /incident <incident-id>", reply)

    def test_unknown_command_returns_operator_help(self) -> None:
        reply = telegram._handle_command("/foobar")

        self.assertIn("Unknown command: /foobar", reply)
        self.assertIn("/incident <incident-id>", reply)
