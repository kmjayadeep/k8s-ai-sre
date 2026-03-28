import asyncio
from agents import Agent, Runner, set_tracing_disabled, function_tool
from model_factory import create_groq_model

set_tracing_disabled(True)

@function_tool
def get_weather(city: str) -> str:
    """returns weather info for the specified city."""
    return f"The weather in {city} is sunny"

async def main():
    # 2. Initialize the model (defaults to openai/gpt-oss-20b)
    model = create_groq_model()

    # 3. Create the Agent
    agent = Agent(
        name="Fast Assistant",
        instructions="You are a helpful assistant. just answe the question using avaialble tools",
        model=model,
        tools=[get_weather],
    )

    # 4. Run the Agent
    print("Agent: Processing request...")
    result = await Runner.run(agent, "how the weather in new york")
    
    # 5. Output the result
    print(f"Agent: {result.final_output}")

if __name__ == "__main__":
    asyncio.run(main())
