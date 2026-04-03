import unittest
from unittest.mock import patch

from app.startup import validate_startup_environment


class StartupValidationTests(unittest.TestCase):
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
