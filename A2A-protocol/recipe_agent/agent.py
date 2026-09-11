import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

load_dotenv(Path(__file__).resolve().parent.parent / '.env')


class RecipeAgent:
    def __init__(self):
        try:
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
                temperature=0.7,
            )
        except FileNotFoundError:
            print('Error: config.json not found at project root.')
            sys.exit(1)
        except KeyError as e:
            print(f'config.json is missing required fields: {e}')
            sys.exit(1)

    async def invoke(self, query: str) -> str:
        messages = [
            SystemMessage(content="""
You are a recipe suggestion assistant. The user message will describe
available pantry ingredients and the user's actual request or preference
(e.g. "something sweet", "vegetarian", "quick dinner", "spicy").

PRIORITY ORDER (most important first):
1. The user's stated preference/craving is the most important factor.
   If they ask for dessert, suggest a dessert - even if it needs ingredients
   not currently in the pantry.
2. Prefer recipes that reuse pantry ingredients where reasonably possible,
   but never sacrifice matching the user's actual request just to avoid
   buying anything new.
3. It's completely fine and expected for the recipe to need ingredients
   the pantry doesn't have - a separate step will handle the shopping list.

Reply in EXACTLY this format, with nothing before or after it:

RECIPE: <name of the dish>
INGREDIENTS: <comma-separated list of every ingredient this recipe needs, including small staples like salt, oil, pepper>
STEPS:
1. ...
2. ...
3. ...
"""
),
            HumanMessage(content=query),
        ]
        response = await self.model.ainvoke(messages)
        return response.content
