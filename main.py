import asyncio
from agents import Agent, Runner, set_tracing_disabled
from model_factory import create_groq_model

set_tracing_disabled(True)

# 1. Define a simple tool
def get_weather(location: str) -> str:
    """Get the current weather for a specific location."""
    # Mock response
    return f"The weather in {location} is sunny and 72°F."

async def main():
    # 2. Initialize the model (defaults to openai/gpt-oss-20b)
    model = create_groq_model()

    # 3. Create the Agent
    agent = Agent(
        name="Fast Assistant",
        instructions="You are a helpful assistant. just answe the question without any extra information.",
        model=model,
    )

    # 4. Run the Agent
    print("Agent: Processing request...")
    result = await Runner.run(agent, "how is it going")
    
    # 5. Output the result
    print(f"Agent: {result.final_output}")

if __name__ == "__main__":
    asyncio.run(main())
