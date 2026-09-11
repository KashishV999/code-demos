from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
)
from agent_executor import PantryAgentExecutor


if __name__ == '__main__':
    skill = AgentSkill(
        id='pantry',
        name='Pantry Agent',
        description=(
            'Tracks which ingredients are currently available at home. '
            'Can list current pantry items, add new items, and remove items.'
        ),
        tags=['pantry', 'ingredients'],
        examples=[
            'what do I have in my pantry?',
            'add rice and chicken to my pantry',
            'remove eggs from my pantry',
        ],
    )

    agent_card = AgentCard(
        name='Pantry Agent',
        description='Keeps track of the ingredients currently available at home.',
        url='http://localhost:10011/',
        version='1.0.0',
        default_input_modes=['text'],
        default_output_modes=['text'],
        capabilities=AgentCapabilities(streaming=False),
        skills=[skill],
    )

    request_handler = DefaultRequestHandler(
        agent_executor=PantryAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )

    server = A2AStarletteApplication(
        agent_card=agent_card, http_handler=request_handler
    )
    import uvicorn

    uvicorn.run(server.build(), host='0.0.0.0', port=10011)