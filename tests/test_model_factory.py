import os
import unittest
from unittest.mock import sentinel, patch

import model_factory


class ModelFactoryTests(unittest.TestCase):
    def test_create_model_raises_without_api_key(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "MODEL_API_KEY"):
                model_factory.create_model()

    def test_create_model_builds_client_and_model_without_provider_kwarg(self) -> None:
        with patch.dict(
            os.environ,
            {
                "MODEL_API_KEY": "test-key",
                "MODEL_NAME": "groq/llama",
                "MODEL_PROVIDER": "groq",
                "MODEL_BASE_URL": "https://api.groq.com/openai/v1",
            },
            clear=True,
        ):
            with patch("model_factory.AsyncOpenAI", return_value=sentinel.client) as async_openai:
                with patch(
                    "model_factory.OpenAIChatCompletionsModel",
                    side_effect=lambda *, model, openai_client: {
                        "model": model,
                        "client": openai_client,
                    },
                ) as model_ctor:
                    result = model_factory.create_model()

        self.assertEqual({"model": "groq/llama", "client": sentinel.client}, result)
        async_openai.assert_called_once_with(
            api_key="test-key",
            base_url="https://api.groq.com/openai/v1",
        )
        model_ctor.assert_called_once_with(model="groq/llama", openai_client=sentinel.client)

    def test_create_model_prefers_explicit_model_name(self) -> None:
        with patch.dict(
            os.environ,
            {
                "MODEL_API_KEY": "test-key",
                "MODEL_NAME": "env-model",
                "MODEL_BASE_URL": "https://api.groq.com/openai/v1",
            },
            clear=True,
        ):
            with patch("model_factory.AsyncOpenAI", return_value=sentinel.client):
                with patch("model_factory.OpenAIChatCompletionsModel", return_value=sentinel.model) as model_ctor:
                    result = model_factory.create_model("explicit-model")

        self.assertIs(result, sentinel.model)
        model_ctor.assert_called_once_with(model="explicit-model", openai_client=sentinel.client)
