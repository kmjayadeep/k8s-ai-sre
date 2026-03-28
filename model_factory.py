import os
from openai import AsyncOpenAI
from agents import OpenAIChatCompletionsModel

# Groq's OpenAI-compatible base URL
GROQ_BASE_URL = "https://api.groq.com/openai/v1"


def create_groq_model(model_name: str = "openai/gpt-oss-20b"):
    """
    Creates an OpenAI Agents SDK model backed by Groq.
    
    Args:
        model_name: The model ID to use. Defaults to 'openai/gpt-oss-20b'.
                    Other options include 'llama-3.3-70b-versatile'.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY environment variable is required")

    # 1. Create a standard OpenAI client pointing to Groq
    client = AsyncOpenAI(
        api_key=api_key,
        base_url=GROQ_BASE_URL,
    )

    # 2. Wrap it in the Agents SDK model class
    return OpenAIChatCompletionsModel(
        model=model_name,
        openai_client=client,
    )
