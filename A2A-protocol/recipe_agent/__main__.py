from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
)
from agent_executor import RecipeAgentExecutor


if __name__ == '__main__':
    skill = AgentSkill(
        id='recipe_finder',
        name='Recipe Agent',
        description='Suggests a recipe based on available ingredients and preferences.',
        tags=['recipe', 'cooking'],
        examples=[
            'Available ingredients: rice, chicken, broccoli. Preferences: quick dinner',
        ],
    )

    agent_card = AgentCard(
        name='Recipe Agent',
        description='Suggests recipes based on what ingredients are available.',
        url='http://localhost:10012/',
        version='1.0.0',
        default_input_modes=['text'],
        default_output_modes=['text'],
        capabilities=AgentCapabilities(streaming=False),
        skills=[skill],
    )

    request_handler = DefaultRequestHandler(
        agent_executor=RecipeAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )

    server = A2AStarletteApplication(
        agent_card=agent_card, http_handler=request_handler
    )
    import uvicorn

    uvicorn.run(server.build(), host='0.0.0.0', port=10012)
