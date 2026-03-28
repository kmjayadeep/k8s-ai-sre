from openai import OpenAI
from portkey_ai import PORTKEY_GATEWAY_URL, createHeaders
import os

model = "llama-3.1-8b-instant"

client = OpenAI(
    api_key=os.environ.get('GROQ_API_KEY'),
    base_url=PORTKEY_GATEWAY_URL,
    default_headers=createHeaders(
        provider="groq",
        api_key=os.environ.get('PORTKEY_API_KEY')
    )
)

chat_complete = client.chat.completions.create(
    model=model,
    messages=[{"role": "user", "content": "What's the purpose of Generative AI?"}]
)

print(chat_complete.choices[0].message.content)
