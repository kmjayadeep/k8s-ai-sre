import os

from agents import OpenAIChatCompletionsModel
from openai import AsyncOpenAI


DEFAULT_MODEL_NAME = "openai/gpt-oss-20b"
DEFAULT_MODEL_PROVIDER = "groq"
DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"


def create_model(model_name: str | None = None) -> OpenAIChatCompletionsModel:
    api_key = os.getenv("MODEL_API_KEY")
    if not api_key:
        raise ValueError("MODEL_API_KEY environment variable is required")

    resolved_model = model_name or os.getenv("MODEL_NAME", DEFAULT_MODEL_NAME)
    provider = os.getenv("MODEL_PROVIDER", DEFAULT_MODEL_PROVIDER)
    base_url = os.getenv("MODEL_BASE_URL", DEFAULT_BASE_URL)

    client = AsyncOpenAI(
        api_key=api_key,
        base_url=base_url,
    )

    return OpenAIChatCompletionsModel(
        model=resolved_model,
        openai_client=client,
        provider=provider,
    )


def create_groq_model(model_name: str = DEFAULT_MODEL_NAME) -> OpenAIChatCompletionsModel:
    return create_model(model_name)
