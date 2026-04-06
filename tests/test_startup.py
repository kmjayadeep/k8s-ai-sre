import unittest
from unittest.mock import patch

from app.startup import validate_startup_config, validate_startup_environment


class StartupConfigTests(unittest.TestCase):
    def test_accepts_required_model_config_with_portkey_key(self) -> None:
        validate_startup_config({"MODEL_NAME": "openai/gpt-oss-20b", "PORTKEY_API_KEY": "pk_test"})

    def test_accepts_required_model_config_with_model_key(self) -> None:
        validate_startup_config({"MODEL_NAME": "openai/gpt-oss-20b", "MODEL_API_KEY": "mk_test"})

    def test_rejects_missing_model_name(self) -> None:
        with self.assertRaises(ValueError) as raised:
            validate_startup_config({"PORTKEY_API_KEY": "pk_test"})

        self.assertIn("MODEL_NAME is required.", str(raised.exception))

    def test_rejects_missing_model_api_keys(self) -> None:
        with self.assertRaises(ValueError) as raised:
            validate_startup_config({"MODEL_NAME": "openai/gpt-oss-20b"})

        self.assertIn("One of MODEL_API_KEY or PORTKEY_API_KEY is required.", str(raised.exception))

    def test_rejects_partial_telegram_pair_when_token_only(self) -> None:
        with self.assertRaises(ValueError) as raised:
            validate_startup_config(
                {
                    "MODEL_NAME": "openai/gpt-oss-20b",
                    "PORTKEY_API_KEY": "pk_test",
                    "TELEGRAM_BOT_TOKEN": "bot_token",
                }
            )

        self.assertIn("TELEGRAM_CHAT_ID must be set when TELEGRAM_BOT_TOKEN is configured.", str(raised.exception))

    def test_rejects_partial_telegram_pair_when_chat_only(self) -> None:
        with self.assertRaises(ValueError) as raised:
            validate_startup_config(
                {
                    "MODEL_NAME": "openai/gpt-oss-20b",
                    "PORTKEY_API_KEY": "pk_test",
                    "TELEGRAM_CHAT_ID": "12345",
                }
            )

        self.assertIn("TELEGRAM_BOT_TOKEN must be set when TELEGRAM_CHAT_ID is configured.", str(raised.exception))

    def test_rejects_allowed_chat_ids_without_bot_token(self) -> None:
        with self.assertRaises(ValueError) as raised:
            validate_startup_config(
                {
                    "MODEL_NAME": "openai/gpt-oss-20b",
                    "PORTKEY_API_KEY": "pk_test",
                    "TELEGRAM_ALLOWED_CHAT_IDS": "12345",
                }
            )

        self.assertIn("TELEGRAM_BOT_TOKEN must be set when TELEGRAM_ALLOWED_CHAT_IDS is configured.", str(raised.exception))

    def test_reports_multiple_errors_in_one_failure(self) -> None:
        with self.assertRaises(ValueError) as raised:
            validate_startup_config({"MODEL_API_KEY": "mk_test", "TELEGRAM_CHAT_ID": "12345"})

        message = str(raised.exception)
        self.assertIn("MODEL_NAME is required.", message)
        self.assertIn("TELEGRAM_BOT_TOKEN must be set when TELEGRAM_CHAT_ID is configured.", message)


class StartupEnvironmentTests(unittest.TestCase):
    def test_validate_startup_environment_raises_when_write_namespaces_missing(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(
                RuntimeError,
                "WRITE_ALLOWED_NAMESPACES must be set to at least one namespace",
            ):
                validate_startup_environment()

    def test_validate_startup_environment_raises_when_write_namespaces_empty(self) -> None:
        with patch.dict("os.environ", {"WRITE_ALLOWED_NAMESPACES": " , "}, clear=True):
            with self.assertRaisesRegex(
                RuntimeError,
                "WRITE_ALLOWED_NAMESPACES must be set to at least one namespace",
            ):
                validate_startup_environment()

    def test_validate_startup_environment_accepts_non_empty_write_namespaces(self) -> None:
        with patch.dict("os.environ", {"WRITE_ALLOWED_NAMESPACES": "ai-sre-demo,prod"}, clear=True):
            validate_startup_environment()
