import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

load_dotenv(Path(__file__).resolve().parent.parent / '.env')

SYSTEM_INSTRUCTION = """
You are a grocery-list assistant. You will be given:
- a recipe's required ingredients
- what's currently in the user's pantry

Compare them carefully. Match ingredients even if worded differently
(e.g. "chicken" in the pantry satisfies "chicken breast" in the recipe,
"onions" satisfies "onion", small staples like salt/pepper/oil count as
available if a similar staple is listed).

Reply in EXACTLY this format, nothing else:

MISSING: <comma-separated list of ingredients the user still needs to buy>

If nothing is missing, reply:
MISSING: none - you have everything you need
"""


class GroceryAgent:
    """Figures out what's missing between a recipe and the pantry, using an LLM."""

    def __init__(self):
        config_path = Path(__file__).resolve().parent.parent / 'config.json'
        with config_path.open() as f:
            config = json.load(f)

        api_key = os.getenv(config['api_key'])
        if not api_key or not api_key.strip():
            print(f'{config["api_key"]} environment variable not set.')
            sys.exit(1)

        self.model = ChatOpenAI(
            model=config['model_name'],
            base_url=config['base_url'] or None,
            api_key=api_key,  # type: ignore[arg-type]
            temperature=0,
        )

    async def invoke(self, query: str) -> str:
        # Expected input format (same as before, from the host):
        # "recipe: item1, item2, item3 | pantry: itemA, itemB"
        messages = [
            SystemMessage(content=SYSTEM_INSTRUCTION),
            HumanMessage(content=query),
        ]
        response = await self.model.ainvoke(messages)
        return response.content