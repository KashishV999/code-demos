"""
test_server.py

An end-to-end smoke test that talks to server.py over the real MCP stdio
protocol (not just importing the functions), so it exercises the same path
Claude Desktop or any other MCP client would use.

Run:
    python test_server.py
"""

import asyncio
import json
import os

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

HERE = os.path.dirname(os.path.abspath(__file__))


def _text(result) -> str:
    return result.content[0].text


async def main() -> None:
    params = StdioServerParameters(command="python3", args=["server.py"], cwd=HERE)

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            assert len(tools.tools) == 8, f"expected 8 tools, got {len(tools.tools)}"
            print(f"OK  8 tools registered: {[t.name for t in tools.tools]}")

            resources = await session.list_resources()
            templates = await session.list_resource_templates()
            assert len(resources.resources) + len(templates.resourceTemplates) == 3
            print("OK  3 resources registered (1 static + 2 templates)")

            prompts = await session.list_prompts()
            assert len(prompts.prompts) == 2
            print(f"OK  2 prompts registered: {[p.name for p in prompts.prompts]}")

            # whats_for_dinner
            r = await session.call_tool("whats_for_dinner", arguments={})
            data = json.loads(_text(r))
            assert "suggestions" in data and len(data["suggestions"]) > 0
            print("OK  whats_for_dinner returns ranked suggestions")

            # plan_week_meals -> the flagship N-to-1 workflow tool
            r = await session.call_tool(
                "plan_week_meals", arguments={"start_date": "2026-09-22", "days": 5}
            )
            plan = json.loads(_text(r))
            assert plan["plan_id"] and len(plan["days"]) == 5
            print(f"OK  plan_week_meals created plan {plan['plan_id']} with 5 days")

            # resource read for the plan we just created
            r = await session.read_resource(f"meal-plan://{plan['plan_id']}")
            plan_detail = json.loads(r.contents[0].text)
            assert len(plan_detail["entries"]) == 5
            print("OK  meal-plan://{id} resource reflects the created plan")

            # get_shopping_list
            r = await session.call_tool(
                "get_shopping_list", arguments={"plan_id": plan["plan_id"]}
            )
            shopping = json.loads(_text(r))
            assert "items" in shopping
            print(f"OK  get_shopping_list returned {len(shopping['items'])} item(s)")

            # update_pantry -- bulk add/use/remove in one call
            r = await session.call_tool(
                "update_pantry",
                arguments={
                    "changes": [
                        {"action": "add", "ingredient": "butter", "quantity": 1, "unit": "lb"},
                        {"action": "use", "ingredient": "garlic", "quantity": 1, "unit": "pcs"},
                    ]
                },
            )
            update = json.loads(_text(r))
            assert len(update["results"]) == 2
            print("OK  update_pantry applied a batch of changes")

            # suggest_substitutes
            r = await session.call_tool(
                "suggest_substitutes", arguments={"ingredient": "buttermilk"}
            )
            subs = json.loads(_text(r))
            assert len(subs["substitutes"]) > 0
            print("OK  suggest_substitutes returned substitutes")

            # error path: add_recipe_to_plan with a bad recipe id should be
            # a recoverable, model-facing error, not a crash
            r = await session.call_tool(
                "add_recipe_to_plan",
                arguments={
                    "recipe_id": 99999,
                    "plan_id": plan["plan_id"],
                    "day": "2026-09-22",
                    "meal_slot": "lunch",
                },
            )
            err = json.loads(_text(r))
            assert "error" in err and "search_recipes" in err["error"]
            print("OK  add_recipe_to_plan gives a recoverable, actionable error")

            # save_recipe -> read it back as a resource
            r = await session.call_tool(
                "save_recipe",
                arguments={
                    "title": "Test Soup",
                    "ingredients": [{"name": "water", "quantity": 1, "unit": "l"}],
                    "steps": ["Boil water."],
                },
            )
            saved = json.loads(_text(r))
            r = await session.read_resource(f"recipe://{saved['recipe_id']}")
            recipe_detail = json.loads(r.contents[0].text)
            assert recipe_detail["title"] == "Test Soup"
            print("OK  save_recipe + recipe://{id} resource round-trip")

    print("\nAll checks passed.")


if __name__ == "__main__":
    asyncio.run(main())
