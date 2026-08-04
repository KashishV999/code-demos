from __future__ import annotations

import asyncio
import os
import sys
from openai import AsyncOpenAI
from dotenv import load_dotenv, find_dotenv

from agents import (
    Agent,
    Model,
    ModelProvider,
    OpenAIChatCompletionsModel,
    RunConfig,
    Runner,
    set_tracing_export_api_key, 
    enable_verbose_stdout_logging,  
)

from get_weather_forecast import get_weather_forecast


# Locate the .env file by searching up the directory tree
load_dotenv(find_dotenv())
API_KEY= os.getenv("OPENROUTER_API_KEY")


BASE_URL = "https://openrouter.ai/api/v1"
MODEL_NAME = "anthropic/claude-haiku-4.5"

if not API_KEY:
    raise ValueError(
        "Please set OPENROUTER_API_KEY via env var or code."
    )

"""This uses a custom provider (OpenRouter) for some calls to Runner.run() Steps:
1. Create a custom OpenAI client.
2. Create a ModelProvider that uses the custom client.
3. Use the ModelProvider in calls to Runner.run(), only when we want to use the custom LLM provider.

we disable tracing under the assumption that you don't have an API key from platform.openai.com. 
"""
client = AsyncOpenAI(base_url=BASE_URL, api_key=API_KEY) #reusable connection object

# Tracing is a separate system from inference — it uploads run logs to
# platform.openai.com, so it needs a real OpenAI key here even though
# model calls themselves are routed through OpenRouter, not OpenAI.
set_tracing_export_api_key(os.getenv("OPENAI_TRACING_KEY"))  
enable_verbose_stdout_logging() 


class CustomModelProvider(ModelProvider):
    def get_model(self, model_name: str | None) -> Model:
        return OpenAIChatCompletionsModel(model=MODEL_NAME, openai_client=client)


CUSTOM_MODEL_PROVIDER = CustomModelProvider()


# to get the content inside the system prompt file
def get_file_contents(path: str, description: str) -> str:
    """Read a TEXT file and return its contents, or exit on error. Not for images."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"Error: {description} not found: {path}")
        sys.exit(1)
    except Exception as err:
        print(f"Error reading {description}: {path}")
        print(f"   {err}")
        sys.exit(1)
        
# system_prompt = get_file_contents('SYSTEM_PROMPT.md', 'System prompt file')




# MAIN ENTRY POINT

async def main():
    agent = Agent(name="Assistant", instructions="Answer the user query", tools=[get_weather_forecast])
    query="What is the weather in Toronto on August 4 2026"

    # This will use the custom model provider
    result = await Runner.run(
        agent,
        query,
        max_turns=10,
        run_config=RunConfig(model_provider=CUSTOM_MODEL_PROVIDER),
    )
    print(result.final_output)
    
    # with open("output.md", "w") as f:
    #     f.write(result.final_output)




if __name__ == "__main__":
    asyncio.run(main())