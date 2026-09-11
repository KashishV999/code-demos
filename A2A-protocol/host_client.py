import asyncio
import json
import os
from pathlib import Path

import httpx
from a2a.client import (
    A2ACardResolver,
    Client,
    ClientConfig,
    ClientFactory,
    create_text_message_object,
)
from a2a.types import AgentCard, TransportProtocol
from a2a.utils.message import get_message_text
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

load_dotenv(Path(__file__).resolve().parent / '.env')

AGENT_URLS = {
    'pantry': 'http://localhost:10011',
    'recipe': 'http://localhost:10012',
    'grocery': 'http://localhost:10013',
}


def load_model() -> ChatOpenAI:
    config_path = Path(__file__).resolve().parent / 'config.json'
    with config_path.open() as f:
        config = json.load(f)

    api_key = os.getenv(config['api_key'])
    if not api_key or not api_key.strip():
        raise RuntimeError(f'{config["api_key"]} environment variable not set.')

    return ChatOpenAI(
        model=config['model_name'],
        base_url=config['base_url'] or None,
        api_key=api_key,  # type: ignore[arg-type]
        temperature=0,
    )


class HostAgent:
    """Host Agent that routes user requests to pantry, recipe, and grocery agents."""

    def __init__(self):
        self.clients: dict[str, Client] = {}
        self.cards: dict[str, AgentCard] = {}
        self.httpx_client: httpx.AsyncClient | None = None

    async def connect(self):
        self.httpx_client = httpx.AsyncClient(timeout=60)
        for name, url in AGENT_URLS.items():
            try:
                resolver = A2ACardResolver(httpx_client=self.httpx_client, base_url=url)
                card = await resolver.get_agent_card()
                config = ClientConfig(
                    httpx_client=self.httpx_client,
                    supported_transports=[TransportProtocol.jsonrpc, TransportProtocol.http_json],
                    streaming=card.capabilities.streaming,
                )
                self.clients[name] = ClientFactory(config).create(card)
                self.cards[name] = card
                print(f"Connected to '{name}' agent: {card.name}")
            except Exception as e:
                print(f"Could not connect to '{name}' agent at {url}: {e}")

    async def close(self):
        if self.httpx_client:
            await self.httpx_client.aclose()

    async def _ask_remote_agent(self, agent_name: str, task: str) -> str:
        """Send a task to one connected remote agent and return its text reply."""
        client = self.clients.get(agent_name)
        if not client:
            return f"Agent '{agent_name}' is not connected."

        request = create_text_message_object(content=task)
        full_text = ''
        async for response in client.send_message(request):
            if isinstance(response, tuple):
                task_obj, _ = response
                if task_obj.artifacts:
                    full_text += get_message_text(task_obj.artifacts[-1])
            else:
                full_text += get_message_text(response)
        return full_text

    def _build_tools(self):
        host = self

        @tool
        async def send_message(agent_name: str, task: str) -> str:
            """Send a task or question to one of the remote agents.
            agent_name must be exactly one of: 'pantry', 'recipe', 'grocery'.
            task is the natural-language request to send to that agent.
            """
            return await host._ask_remote_agent(agent_name, task)

        return [send_message]

    def root_instruction(self) -> str:
        agent_list = '\n'.join(
            f"- {name}: {card.description}" for name, card in self.cards.items()
        )
        return f"""
You are the Host Agent for a meal-planning assistant. You coordinate with
specialist agents to help the user with meals, ingredients, and shopping.

<Available Agents>
{agent_list}
</Available Agents>

**Routing rules:**
- If the user only asks about their pantry (what they have, adding or
  removing items), call ONLY the pantry agent.
- If the user asks for a meal, recipe, or "what should I cook" - treat
  this as a full meal request and always do ALL THREE steps, in order:
    1. Call the pantry agent to get current ingredients.
    2. Call the recipe agent with those ingredients plus any preferences
       the user gave (e.g. vegetarian, quick, spicy).
    3. Call the grocery agent with the task formatted EXACTLY as:
       "recipe: <ingredients from the recipe> | pantry: <ingredients from the pantry>"
  Do this even if the user didn't explicitly ask for a shopping list -
  always include it as part of the meal suggestion.
- Only skip the recipe/grocery steps if the user's question is purely
  about the pantry itself (not about eating or cooking).
- Always use the exact agent names: 'pantry', 'recipe', 'grocery'.
- Present the final answer clearly with three parts: the recipe, its
  ingredients, and the shopping list of what's missing.
- Keep your final answer concise and easy to read.
"""

    async def handle_query(self, model: ChatOpenAI, query: str) -> str:
        tools = self._build_tools()
        model_with_tools = model.bind_tools(tools)
        tool_map = {t.name: t for t in tools}

        messages = [
            SystemMessage(content=self.root_instruction()),
            HumanMessage(content=query),
        ]
        response = await model_with_tools.ainvoke(messages)

        while response.tool_calls:
            messages.append(response)
            for call in response.tool_calls:
                result = await tool_map[call['name']].ainvoke(call['args'])
                messages.append(ToolMessage(content=str(result), tool_call_id=call['id']))
            response = await model_with_tools.ainvoke(messages)

        return response.content


async def main():
    print('=== Meal Planner Host ===')
    print("Type 'exit' to quit.\n")

    host = HostAgent()
    await host.connect()

    if not host.clients:
        print('No agents connected. Exiting.')
        return

    model = load_model()

    try:
        while True:
            user_input = input('\n> ').strip()
            if user_input.lower() == 'exit':
                print('bye!~')
                break

            reply = await host.handle_query(model, user_input)
            print(reply)
    finally:
        await host.close()


if __name__ == '__main__':
    asyncio.run(main())