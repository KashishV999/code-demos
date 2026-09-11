
import json
from pathlib import Path
import os
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

load_dotenv(Path(__file__).resolve().parent.parent / '.env')

PANTRY_FILE = Path(__file__).resolve().parent / 'pantry_store.json'


def _load() -> list[str]:
    if not PANTRY_FILE.exists():
        return []
    with PANTRY_FILE.open() as f:
        return json.load(f)


def _save(items: list[str]) -> None:
    with PANTRY_FILE.open('w') as f:
        json.dump(items, f, indent=2)


@tool
def get_pantry_items() -> str:
    """Return the list of ingredients currently in the pantry."""
    items = _load()
    return ', '.join(items) if items else 'Pantry is empty.'


@tool
def add_pantry_item(items: str) -> str:
    """Add one or more ingredients to the pantry. Pass a comma-separated list, e.g. 'rice, chicken'."""
    new_items = [i.strip() for i in items.split(',') if i.strip()]
    current = _load()
    existing_lower = [x.lower() for x in current]
    for item in new_items:
        if item.lower() not in existing_lower:
            current.append(item)
    _save(current)
    return f"Added: {', '.join(new_items)}. Pantry now has: {', '.join(current)}"


@tool
def remove_pantry_items(items: str) -> str:
    """Remove one or more ingredients from the pantry. Pass a comma-separated list, e.g. 'eggs, onion'."""
    remove_set = {i.strip().lower() for i in items.split(',') if i.strip()}
    current = _load()
    current = [i for i in current if i.lower() not in remove_set]
    _save(current)
    return f"Pantry now has: {', '.join(current) if current else '(empty)'}"


SYSTEM_INSTRUCTION = """
You are a pantry assistant. You track what ingredients the user has at home.
Use your tools to check, add, or remove pantry items based on what the user asks.
Keep responses short and confirm what you did.
"""


class PantryAgent:
    def __init__(self):
        config_path = Path(__file__).resolve().parent.parent / 'config.json'
        with config_path.open() as f:
            config = json.load(f)

        api_key = os.getenv(config['api_key'])
        if not api_key or not api_key.strip():
            print(f'{config["api_key"]} environment variable not set.')
            sys.exit(1)

        self.tools = [get_pantry_items, add_pantry_item, remove_pantry_items]
        self.tool_map = {t.name: t for t in self.tools}
        self.model = ChatOpenAI(
            model=config['model_name'],
            base_url=config['base_url'] or None,
            api_key=api_key,
            temperature=0,
        ).bind_tools(self.tools)

    async def invoke(self, query: str) -> str:
        messages = [SystemMessage(content=SYSTEM_INSTRUCTION), HumanMessage(content=query)]
        response = await self.model.ainvoke(messages)

        # Run any tool calls the model requested, then get a final reply
        while response.tool_calls:
            messages.append(response)
            for call in response.tool_calls:
                result = self.tool_map[call['name']].invoke(call['args'])
                messages.append(ToolMessage(content=str(result), tool_call_id=call['id']))
            response = await self.model.ainvoke(messages)

        return response.content