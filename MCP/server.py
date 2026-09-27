"""
server.py

The Pantry MCP server, built following the design in the WorkOS article
"Designing an MCP server from a REST API":
https://workos.com/blog/designing-mcp-server-from-rest-api

Pantry's REST API has 24 endpoints (see pantry_api.py). This server does
NOT wrap all 24 as tools. Per the article's six-step process, it ships:

    8 tools       (verbs -- the model decides when to call these)
    3 resources   (nouns -- context the model pulls in by URI)
    2 prompts     (recipes -- user-invoked workflows)

Tools
-----
1. search_recipes        N/A -> GET /recipes                 (1-to-1, generic search)
2. save_recipe           -> POST /recipes                    (1-to-1, clean mapping)
3. whats_for_dinner       -> GET /recipes (pantry-weighted)    (1-to-N split of search_recipes)
4. plan_week_meals        -> 5 endpoints combined              (N-to-1, the flagship workflow tool)
5. update_pantry          -> POST/PATCH/DELETE /pantry         (N-to-1, bulk pantry update)
6. add_recipe_to_plan     -> POST /meal-plans/{id}/recipes     (1-to-1, targeted)
7. get_shopping_list      -> GET /shopping-lists/{plan_id}     (1-to-1, with pantry exclusion)
8. suggest_substitutes    -> GET /ingredients/{id}             (1-to-1, recipe-aware)

Resources
---------
- recipe://{id}       -> GET /recipes/{id}      (1-to-0: read-only detail, not a tool)
- pantry://current    -> GET /pantry            (1-to-0: read-only detail, not a tool)
- meal-plan://{id}    -> GET /meal-plans/{id}   (1-to-0: read-only detail, not a tool)

Prompts
-------
- weekly_meal_planning  -- primes the agent to check preferences/pantry, then call plan_week_meals
- recipe_from_text      -- walks the agent through parsing pasted text into save_recipe

Deliberately NOT exposed as tools (per "0 to 1: don't expose this at all"):
    GET  /admin/stats
    POST /admin/index/rebuild
    DELETE /recipes/{id}
    DELETE /meal-plans/{id}/recipes/{rid}
    PUT  /recipes/{id}
    PUT  /meal-plans/{id}
    PUT  /users/{id}/preferences
    GET  /meal-plans (list)
    POST /shopping-lists/{id}/check
These all still exist in pantry_api.py -- the backend is complete -- they are
simply not surfaced to the agent, exactly as the article recommends.

Run it:
    pip install "mcp==1.30.0"
    python server.py                # stdio transport, for Claude Desktop / MCP Inspector
    python server.py --http          # streamable-HTTP transport on :8000, for remote clients
"""

from __future__ import annotations

import sys
from typing import Literal

from mcp.server.fastmcp import FastMCP

import pantry_api as api
from pantry_api import PantryAPIError, MealSlot

mcp = FastMCP(
    "pantry",
    instructions=(
        "Pantry is a cooking assistant. Use whats_for_dinner or search_recipes for quick "
        "lookups, plan_week_meals for a full week, and update_pantry whenever the user "
        "mentions buying or using up groceries. Read recipe://, pantry://, and meal-plan:// "
        "resources instead of re-fetching things you already have an id for."
    ),
)


# --------------------------------------------------------------------------
# Small internal helpers (not tools -- used to build tool return values)
# --------------------------------------------------------------------------

def _recipe_summary(recipe: api.Recipe) -> dict:
    """A compact, model-friendly view of a recipe -- not the full detail."""
    return {
        "id": recipe.id,
        "title": recipe.title,
        "cuisine": recipe.cuisine,
        "dietary": recipe.dietary,
        "time_minutes": recipe.time_minutes,
    }


def _pantry_ingredient_names() -> set[str]:
    return {item.ingredient.lower() for item in api.list_pantry()}


def _score_by_pantry_overlap(recipe: api.Recipe, have: set[str]) -> int:
    needed = {ing["name"].lower() for ing in recipe.ingredients}
    return len(needed & have)


# --------------------------------------------------------------------------
# Tool 1 -- search_recipes (1-to-1: GET /recipes, general search)
# --------------------------------------------------------------------------

@mcp.tool()
def search_recipes(
    query: str = "",
    max_minutes: int | None = None,
    dietary: list[str] | None = None,
    cuisine: str | None = None,
) -> dict:
    """
    Search the recipe catalog by keyword and optional filters.

    Use this for general "find me a recipe" requests where the user gives
    criteria but isn't asking what to cook with what they already have --
    for that, use whats_for_dinner instead.

    Example: search_recipes(query="curry", max_minutes=40, dietary=["pescatarian"])

    Args:
        query: Free-text search across title and ingredients. Empty string matches all.
        max_minutes: Only return recipes that take this long or less.
        dietary: Required dietary tags, e.g. ["vegetarian"]. Recipe must satisfy all of them.
        cuisine: Restrict to one cuisine, e.g. "japanese".

    Returns:
        A list of compact recipe summaries (id, title, cuisine, dietary, time_minutes)
        and a one-sentence summary. Fetch recipe://{id} for full ingredients/steps.
    """
    results = api.list_recipes(query=query or None, max_minutes=max_minutes, dietary=dietary, cuisine=cuisine)
    summaries = [_recipe_summary(r) for r in results]
    if not summaries:
        return {
            "recipes": [],
            "summary": "No recipes matched those filters. Try loosening max_minutes or dietary.",
        }
    return {
        "recipes": summaries,
        "summary": f"Found {len(summaries)} recipe(s) matching your search.",
    }


# --------------------------------------------------------------------------
# Tool 2 -- save_recipe (1-to-1: POST /recipes)
# --------------------------------------------------------------------------

@mcp.tool()
def save_recipe(
    title: str,
    ingredients: list[dict],
    steps: list[str],
    cuisine: str | None = None,
    dietary: list[str] | None = None,
    time_minutes: int = 30,
) -> dict:
    """
    Save a new recipe to the catalog.

    Use this when the user dictates or pastes a recipe they want kept, or
    when the recipe_from_text prompt has finished parsing one.

    Example: save_recipe(
        title="Lemon Garlic Pasta",
        ingredients=[{"name": "pasta", "quantity": 200, "unit": "g"},
                     {"name": "lemon", "quantity": 1, "unit": "pcs"}],
        steps=["Boil pasta.", "Toss with lemon, garlic, olive oil."],
        cuisine="italian", dietary=["vegetarian"], time_minutes=15,
    )

    Args:
        title: Recipe name.
        ingredients: List of {"name": str, "quantity": number, "unit": str}.
        steps: Ordered list of instruction strings.
        cuisine: Optional cuisine tag.
        dietary: Optional dietary tags, e.g. ["vegan"].
        time_minutes: Total time to cook, in minutes.

    Returns:
        The new recipe's id and a confirmation summary.
    """
    recipe = api.create_recipe(
        title=title, ingredients=ingredients, steps=steps,
        cuisine=cuisine, dietary=dietary, time_minutes=time_minutes,
    )
    return {
        "recipe_id": recipe.id,
        "summary": f"Saved \"{recipe.title}\" (recipe://{recipe.id}), {recipe.time_minutes} min.",
    }


# --------------------------------------------------------------------------
# Tool 3 -- whats_for_dinner (1-to-N split: pantry-aware variant of GET /recipes)
# --------------------------------------------------------------------------

@mcp.tool()
def whats_for_dinner(
    meal: MealSlot | None = None,
    max_minutes: int | None = None,
) -> dict:
    """
    Suggest recipes weighted toward ingredients already in the pantry.

    Use this for "what can I make tonight / with what I have" requests.
    This is intentionally a separate tool from search_recipes -- both read
    the recipe catalog, but this one also reads the pantry and re-ranks by
    overlap, which is a distinct user intent from a plain keyword search.

    Args:
        meal: Optional meal slot to bias suggestions toward ("breakfast", "lunch", "dinner").
        max_minutes: Only suggest recipes that take this long or less.

    Returns:
        Up to 3 ranked recipe summaries plus how many of each recipe's
        ingredients you already have, and a one-sentence summary.
    """
    have = _pantry_ingredient_names()
    candidates = api.list_recipes(max_minutes=max_minutes)
    ranked = sorted(candidates, key=lambda r: _score_by_pantry_overlap(r, have), reverse=True)[:3]

    if not ranked:
        return {"suggestions": [], "summary": "Nothing in the catalog fits that time limit."}

    suggestions = []
    for r in ranked:
        overlap = _score_by_pantry_overlap(r, have)
        s = _recipe_summary(r)
        s["ingredients_you_have"] = overlap
        s["ingredients_total"] = len(r.ingredients)
        suggestions.append(s)

    top = suggestions[0]
    return {
        "suggestions": suggestions,
        "summary": (
            f"Best match: \"{top['title']}\" -- you already have "
            f"{top['ingredients_you_have']}/{top['ingredients_total']} ingredients."
        ),
    }


# --------------------------------------------------------------------------
# Tool 4 -- plan_week_meals (N-to-1: the flagship workflow tool)
# --------------------------------------------------------------------------

@mcp.tool()
def plan_week_meals(
    start_date: str,
    days: int = 7,
    dietary: list[str] | None = None,
    prefer_pantry: bool = True,
) -> dict:
    """
    Plan a week (or any number of days) of dinners in one call.

    Internally this reads the pantry, reads saved dietary preferences,
    queries the recipe catalog, creates a meal plan, and adds one dinner
    recipe per day -- five REST calls collapsed into a single tool so the
    model doesn't have to orchestrate them turn by turn.

    Example: plan_week_meals(start_date="2026-09-22", days=7)

    Args:
        start_date: ISO date (YYYY-MM-DD) for day 1 of the plan.
        days: How many days to plan. Keep this reasonable (1-14).
        dietary: Dietary tags to require, e.g. ["vegetarian"]. If omitted,
            falls back to the user's saved preferences.
        prefer_pantry: If true, favor recipes that use ingredients already
            on hand (same ranking as whats_for_dinner).

    Returns:
        The new plan's id, meal_plan://{id} resource URI, the chosen
        recipe per day, and a friendly one-paragraph summary the model
        can relay directly to the user.
    """
    if days < 1 or days > 14:
        return {
            "error": f"days={days} is out of range. Use a value between 1 and 14.",
        }

    prefs = api.get_preferences()
    effective_dietary = dietary if dietary is not None else prefs.get("dietary")

    have = _pantry_ingredient_names() if prefer_pantry else set()
    candidates = api.list_recipes(dietary=effective_dietary)
    if not candidates:
        return {
            "error": (
                f"No recipes match dietary={effective_dietary}. "
                "Try search_recipes with looser filters, or save_recipe to add one."
            ),
        }
    if prefer_pantry:
        candidates = sorted(candidates, key=lambda r: _score_by_pantry_overlap(r, have), reverse=True)

    plan = api.create_meal_plan(start_date=start_date, days=days)

    from datetime import date as _date, timedelta as _timedelta
    y, m, d = (int(x) for x in start_date.split("-"))
    base = _date(y, m, d)

    chosen: list[dict] = []
    for i in range(days):
        recipe = candidates[i % len(candidates)]
        day_str = (base + _timedelta(days=i)).isoformat()
        api.add_recipe_to_plan_api(plan.id, recipe.id, day_str, "dinner")
        chosen.append({"day": day_str, "recipe_id": recipe.id, "title": recipe.title})

    day_list = ", ".join(f"{c['day']}: {c['title']}" for c in chosen)
    return {
        "plan_id": plan.id,
        "resource_uri": f"meal-plan://{plan.id}",
        "days": chosen,
        "summary": f"Created a {days}-day plan (meal-plan://{plan.id}). {day_list}.",
    }


# --------------------------------------------------------------------------
# Tool 5 -- update_pantry (N-to-1: bulk add/remove/use in one call)
# --------------------------------------------------------------------------

@mcp.tool()
def update_pantry(changes: list[dict]) -> dict:
    """
    Apply several pantry changes in one call -- additions, removals, or usage.

    Replaces three separate REST calls (POST /pantry, PATCH /pantry/{id},
    DELETE /pantry/{id}) with one tool, so "I bought milk, eggs, and bread,
    and used up the flour" is a single call instead of four.

    Example: update_pantry(changes=[
        {"action": "add", "ingredient": "milk", "quantity": 1, "unit": "l"},
        {"action": "add", "ingredient": "egg", "quantity": 12, "unit": "pcs"},
        {"action": "use", "ingredient": "flour", "quantity": 2, "unit": "cup"},
    ])

    Args:
        changes: List of {"action": "add"|"use"|"remove", "ingredient": str,
            "quantity": number, "unit": str}. "add" increases quantity
            (creating the item if new), "use" decreases it (never below 0),
            "remove" deletes the item entirely regardless of quantity given.

    Returns:
        One line per change describing what happened, plus a summary.
        Unrecognized actions or ingredients are reported, not raised, so
        the rest of the batch still applies.
    """
    results = []
    for change in changes:
        action = change.get("action")
        ingredient = change.get("ingredient", "")
        quantity = change.get("quantity", 0)
        unit = change.get("unit", "")

        if action == "add":
            item = api.add_pantry_item(ingredient, quantity, unit)
            results.append(f"added {quantity} {unit} {ingredient} (now {item.quantity} {unit})")
        elif action == "use":
            existing = api.find_pantry_item_by_name(ingredient)
            if existing is None:
                results.append(f"skipped: '{ingredient}' isn't in the pantry, nothing to use")
                continue
            new_qty = max(existing.quantity - quantity, 0)
            api.update_pantry_item(existing.id, new_qty)
            results.append(f"used {quantity} {unit} {ingredient} (now {new_qty} {existing.unit})")
        elif action == "remove":
            existing = api.find_pantry_item_by_name(ingredient)
            if existing is None:
                results.append(f"skipped: '{ingredient}' isn't in the pantry")
                continue
            api.remove_pantry_item(existing.id)
            results.append(f"removed {ingredient} from pantry")
        else:
            results.append(
                f"skipped: unknown action '{action}' for '{ingredient}'. "
                "Use 'add', 'use', or 'remove'."
            )

    return {"results": results, "summary": f"Applied {len(changes)} pantry change(s)."}


# --------------------------------------------------------------------------
# Tool 6 -- add_recipe_to_plan (1-to-1, targeted)
# --------------------------------------------------------------------------

@mcp.tool()
def add_recipe_to_plan(recipe_id: int, plan_id: int, day: str, meal_slot: MealSlot) -> dict:
    """
    Add a single recipe to a specific day/slot of an existing meal plan.

    Use this for targeted edits ("add the chicken curry to Wednesday's
    plan") rather than plan_week_meals, which builds a whole plan from
    scratch.

    Args:
        recipe_id: The recipe to add. Look it up with search_recipes or
            whats_for_dinner if you don't already have an id.
        plan_id: The meal plan to add it to.
        day: ISO date (YYYY-MM-DD) within the plan's range.
        meal_slot: One of "breakfast", "lunch", "dinner".

    Returns:
        A confirmation summary, or a recoverable error telling the model
        what to check if the recipe or plan id doesn't exist.
    """
    try:
        plan = api.add_recipe_to_plan_api(plan_id, recipe_id, day, meal_slot)
    except PantryAPIError as e:
        return {
            "error": (
                f"{e}. Use search_recipes to find a valid recipe_id, or "
                f"plan_week_meals to create a new plan if plan_id {plan_id} doesn't exist."
            )
        }
    recipe = api.get_recipe(recipe_id)
    return {
        "summary": f"Added \"{recipe.title}\" to {day} ({meal_slot}) on plan {plan_id}.",
        "resource_uri": f"meal-plan://{plan.id}",
    }


# --------------------------------------------------------------------------
# Tool 7 -- get_shopping_list (1-to-1, with pantry exclusion)
# --------------------------------------------------------------------------

@mcp.tool()
def get_shopping_list(plan_id: int, exclude_pantry: bool = True) -> dict:
    """
    Generate a shopping list for a meal plan.

    Args:
        plan_id: The meal plan to generate a list for.
        exclude_pantry: If true (default), subtract quantities already in
            the pantry so the list only shows what's actually missing.

    Returns:
        A list of {ingredient, quantity, unit} still needed, and a
        one-sentence summary. Errors if the plan doesn't exist.
    """
    try:
        items = api.generate_shopping_list(plan_id, exclude_pantry=exclude_pantry)
    except PantryAPIError as e:
        return {"error": f"{e}. Use plan_week_meals to create a plan first."}

    if not items:
        return {"items": [], "summary": "Nothing needed -- the pantry already covers this plan."}
    return {
        "items": items,
        "summary": f"{len(items)} item(s) needed for plan {plan_id}.",
    }


# --------------------------------------------------------------------------
# Tool 8 -- suggest_substitutes (1-to-1, recipe-aware)
# --------------------------------------------------------------------------

@mcp.tool()
def suggest_substitutes(ingredient: str, recipe_context: str | None = None) -> dict:
    """
    Suggest substitutes for an ingredient the user is out of.

    Example: suggest_substitutes(ingredient="buttermilk", recipe_context="pancakes")

    Args:
        ingredient: The ingredient to substitute, e.g. "buttermilk".
        recipe_context: Optional -- what dish it's for, purely for a more
            natural summary sentence. Doesn't change the substitutes returned.

    Returns:
        A list of substitute suggestions and a one-sentence summary, or a
        recoverable message if the ingredient isn't in the catalog yet.
    """
    try:
        entry = api.get_ingredient(ingredient)
    except PantryAPIError:
        return {
            "substitutes": [],
            "summary": (
                f"'{ingredient}' isn't in the substitution catalog yet. "
                "Common fallback: check the ingredient's category (dairy, "
                "leavening, acid) for a same-category swap."
            ),
        }

    context = f" for {recipe_context}" if recipe_context else ""
    return {
        "substitutes": entry.substitutes,
        "summary": f"For {ingredient}{context}, try: {', '.join(entry.substitutes)}.",
    }


# --------------------------------------------------------------------------
# Resources -- read-only, addressed by URI, no tool-call slot spent
# --------------------------------------------------------------------------

@mcp.resource("recipe://{recipe_id}")
def recipe_resource(recipe_id: str) -> dict:
    """Full detail (ingredients + steps) for one recipe."""
    try:
        recipe = api.get_recipe(int(recipe_id))
    except (PantryAPIError, ValueError) as e:
        return {"error": str(e)}
    return api.to_dict(recipe)


@mcp.resource("pantry://current")
def pantry_resource() -> dict:
    """The full current pantry contents."""
    return {"items": [api.to_dict(i) for i in api.list_pantry()]}


@mcp.resource("meal-plan://{plan_id}")
def meal_plan_resource(plan_id: str) -> dict:
    """A specific meal plan, with its per-day recipe assignments."""
    try:
        plan = api.get_meal_plan(int(plan_id))
    except (PantryAPIError, ValueError) as e:
        return {"error": str(e)}
    data = api.to_dict(plan)
    for entry in data["entries"]:
        try:
            entry["title"] = api.get_recipe(entry["recipe_id"]).title
        except PantryAPIError:
            entry["title"] = None
    return data


# --------------------------------------------------------------------------
# Prompts -- user-invoked workflows (macros), not called autonomously
# --------------------------------------------------------------------------

@mcp.prompt()
def weekly_meal_planning() -> str:
    """A guided flow for planning the coming week's dinners."""
    return (
        "Help the user plan their week of dinners. Follow this flow:\n"
        "1. Read the pantry://current resource to see what's on hand.\n"
        "2. Ask the user for their start date, how many days to plan, and "
        "whether any dietary restriction applies this week (or read their "
        "saved preferences if they say 'the usual').\n"
        "3. Call plan_week_meals with those parameters.\n"
        "4. Relay the returned summary, and ask if they'd like a shopping "
        "list via get_shopping_list for the new plan."
    )


@mcp.prompt()
def recipe_from_text(pasted_text: str) -> str:
    """
    Parse pasted recipe text (from a website, OCR, or an email) and save it.

    Args:
        pasted_text: The raw recipe text to parse.
    """
    return (
        "The user pasted the following recipe text. Extract a title, a "
        "structured ingredients list (name, quantity, unit), an ordered "
        "steps list, and if apparent a cuisine, dietary tags, and total "
        "time in minutes. Show the user your parsed version for a quick "
        "confirmation, then call save_recipe with the confirmed fields.\n\n"
        f"--- pasted text ---\n{pasted_text}"
    )


# --------------------------------------------------------------------------
# Entrypoint
# --------------------------------------------------------------------------

if __name__ == "__main__":
    if "--http" in sys.argv:
        mcp.run(transport="streamable-http")
    else:
        mcp.run(transport="stdio")
