from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
)
from agent_executor import GroceryAgentExecutor


if __name__ == '__main__':
    skill = AgentSkill(
        id='grocery_list',
        name='Grocery Agent',
        description="Figures out what's missing between a recipe and the pantry.",
        tags=['grocery', 'shopping'],
        examples=['recipe: rice, chicken, ginger | pantry: rice, chicken'],
    )

    agent_card = AgentCard(
        name='Grocery Agent',
        description="Computes a shopping list for whatever a recipe needs that isn't in the pantry.",
        url='http://localhost:10013/',
        version='1.0.0',
        default_input_modes=['text'],
        default_output_modes=['text'],
        capabilities=AgentCapabilities(streaming=False),
        skills=[skill],
    )

    request_handler = DefaultRequestHandler(
        agent_executor=GroceryAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )

    server = A2AStarletteApplication(
        agent_card=agent_card, http_handler=request_handler
    )
    import uvicorn

    uvicorn.run(server.build(), host='0.0.0.0', port=10013)
