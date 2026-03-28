import os
from openai import AsyncOpenAI
from agents import OpenAIChatCompletionsModel
from portkey_ai import PORTKEY_GATEWAY_URL, createHeaders

def create_groq_model(model_name: str = "openai/gpt-oss-20b"):
    """
    Creates an OpenAI Agents SDK model backed by Groq.
    
    Args:
        model_name: The model ID to use. Defaults to 'openai/gpt-oss-20b'.
                    Other options include 'llama-3.3-70b-versatile'.
    """
    api_key = os.getenv("PORTKEY_API_KEY")
    if not api_key:
        raise ValueError("PORTKEY_API_KEY environment variable is required")

    # 1. Create a standard OpenAI client pointing to Groq
    client = AsyncOpenAI(
        api_key=api_key,
        base_url=PORTKEY_GATEWAY_URL,
        default_headers=createHeaders(
            provider="@groq"
        )
    )

    # 2. Wrap it in the Agents SDK model class
    return OpenAIChatCompletionsModel(
        model=model_name,
        openai_client=client,
    )
