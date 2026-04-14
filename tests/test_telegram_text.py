import unittest

from app.telegram_text import sanitize_telegram_answer


class TelegramTextTests(unittest.TestCase):
    def test_sanitize_removes_think_block(self) -> None:
        answer = "before\n<think>hidden reasoning</think>\nafter"
        self.assertEqual("before\n\nafter", sanitize_telegram_answer(answer))

    def test_sanitize_truncates_after_unclosed_think_tag(self) -> None:
        answer = "Final summary\n<thinking>hidden reasoning"
        self.assertEqual("Final summary", sanitize_telegram_answer(answer))
