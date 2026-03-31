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

    def test_approve_command_without_argument_returns_usage(self) -> None:
        reply = telegram._handle_command("/approve")
        self.assertEqual("Usage: /approve <action-id>", reply)

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

    def test_poll_updates_ignores_unauthorized_chat(self) -> None:
        body = {
            "ok": True,
            "result": [{"update_id": 7, "message": {"chat": {"id": 123}, "text": "/approve deadbeef"}}],
        }
        with patch("app.telegram._telegram_token", return_value="token"):
            with patch("app.telegram._telegram_api", return_value=body):
                with patch("app.telegram._allowed_chat_ids", return_value={"999"}):
                    with patch("app.telegram._save_offset"):
                        with patch("app.telegram._send_message") as send_message:
                            with patch("app.telegram.log_event") as log_event:
                                result = telegram.poll_telegram_updates_once()

        self.assertEqual("Processed 0 Telegram command(s).", result)
        send_message.assert_not_called()
        log_event.assert_any_call("telegram_command_ignored_unauthorized", chat_id="123", text="/approve deadbeef")

    def test_poll_updates_sends_actionable_failure_reply(self) -> None:
        body = {
            "ok": True,
            "result": [{"update_id": 11, "message": {"chat": {"id": 123}, "text": "/approve deadbeef"}}],
        }
        with patch("app.telegram._telegram_token", return_value="token"):
            with patch("app.telegram._telegram_api", return_value=body):
                with patch("app.telegram._allowed_chat_ids", return_value=set()):
                    with patch("app.telegram._save_offset"):
                        with patch("app.telegram._handle_command", side_effect=RuntimeError("boom")):
                            with patch("app.telegram._send_message") as send_message:
                                telegram.poll_telegram_updates_once()

        send_message.assert_called_once_with("123", "Command failed for /approve deadbeef: boom")
