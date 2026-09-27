"""
pantry_api.py

A small in-memory stand-in for the "Pantry" REST backend described in the
WorkOS article "Designing an MCP server from a REST API"
(https://workos.com/blog/designing-mcp-server-from-rest-api).

This module plays the role of the existing REST API: it is the thing you'd
normally reach over HTTP with `requests`/`httpx`. Here it's just Python
objects and functions so the whole project runs with zero external
dependencies and no server to stand up separately.

Every function below corresponds to one endpoint in the article's table:

    Recipes
      GET    /recipes                       -> list_recipes()
      GET    /recipes/{id}                  -> get_recipe()
      POST   /recipes                       -> create_recipe()
      PUT    /recipes/{id}                  -> update_recipe()          [not exposed as a tool]
      DELETE /recipes/{id}                  -> delete_recipe()          [not exposed as a tool]
      GET    /recipes/{id}/similar          -> similar_recipes()

    Ingredients (catalog)
      GET    /ingredients                   -> search_ingredients()
      GET    /ingredients/{id}              -> get_ingredient()

    Pantry (what the user has at home)
      GET    /pantry                        -> list_pantry()
      POST   /pantry                        -> add_pantry_item()
      PATCH  /pantry/{id}                   -> update_pantry_item()
      DELETE /pantry/{id}                   -> remove_pantry_item()

    Meal plans
      GET    /meal-plans                    -> list_meal_plans()        [not exposed as a tool]
      POST   /meal-plans                    -> create_meal_plan()
      GET    /meal-plans/{id}               -> get_meal_plan()
      PUT    /meal-plans/{id}               -> update_meal_plan()       [not exposed as a tool]
      POST   /meal-plans/{id}/recipes       -> add_recipe_to_plan()
      DELETE /meal-plans/{id}/recipes/{rid} -> remove_recipe_from_plan()[not exposed as a tool]

    Shopping lists
      GET    /shopping-lists/{plan_id}      -> generate_shopping_list()
      POST   /shopping-lists/{id}/check     -> check_shopping_item()    [not exposed as a tool]

    Admin and user
      GET    /admin/stats                   -> admin_stats()            [not exposed as a tool]
      POST   /admin/index/rebuild           -> rebuild_index()          [not exposed as a tool]
      GET    /users/{id}/preferences        -> get_preferences()
      PUT    /users/{id}/preferences        -> update_preferences()     [not exposed as a tool]

The endpoints marked "[not exposed as a tool]" all exist here (so the API
is a faithful, complete implementation of the article's 24-endpoint table)
but server.py deliberately does not wrap them in MCP tools, for exactly the
reasons the article gives in "0 to 1: don't expose this at all".
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field, asdict
from datetime import date, timedelta
from typing import Literal

MealSlot = Literal["breakfast", "lunch", "dinner"]


class PantryAPIError(Exception):
    """
    Raised by the mock backend for not-found / invalid-state conditions.

    Kept distinct from generic exceptions so server.py can catch it
    specifically and translate it into a model-facing error message,
    per the article's Step 6 ("Plan for failure as a normal case").
    """


# --------------------------------------------------------------------------
# In-memory "database"
# --------------------------------------------------------------------------

_recipe_ids = itertools.count(1)
_pantry_ids = itertools.count(1)
_plan_ids = itertools.count(1)


@dataclass
class Recipe:
    id: int
    title: str
    ingredients: list[dict]  # [{"name": str, "quantity": float, "unit": str}]
    steps: list[str]
    cuisine: str | None = None
    dietary: list[str] = field(default_factory=list)
    time_minutes: int = 30


@dataclass
class IngredientCatalogEntry:
    id: int
    name: str
    substitutes: list[str] = field(default_factory=list)


@dataclass
class PantryItem:
    id: int
    ingredient: str
    quantity: float
    unit: str


@dataclass
class PlanEntry:
    day: str
    meal_slot: MealSlot
    recipe_id: int


@dataclass
class MealPlan:
    id: int
    start_date: str
    days: int
    entries: list[PlanEntry] = field(default_factory=list)


_recipes: dict[int, Recipe] = {}
_ingredient_catalog: dict[int, IngredientCatalogEntry] = {}
_pantry: dict[int, PantryItem] = {}
_meal_plans: dict[int, MealPlan] = {}
_preferences: dict = {
    "dietary": ["vegetarian"],
    "dislikes": ["cilantro"],
}


def _seed() -> None:
    seed_recipes = [
        dict(
            title="Miso Salmon",
            ingredients=[
                {"name": "salmon fillet", "quantity": 2, "unit": "pcs"},
                {"name": "miso paste", "quantity": 2, "unit": "tbsp"},
                {"name": "rice", "quantity": 1, "unit": "cup"},
            ],
            steps=["Mix miso glaze.", "Broil salmon 8 min.", "Serve over rice."],
            cuisine="japanese",
            dietary=["pescatarian"],
            time_minutes=25,
        ),
        dict(
            title="Tofu Stir-Fry",
            ingredients=[
                {"name": "tofu", "quantity": 400, "unit": "g"},
                {"name": "broccoli", "quantity": 1, "unit": "pcs"},
                {"name": "soy sauce", "quantity": 2, "unit": "tbsp"},
                {"name": "garlic", "quantity": 2, "unit": "pcs"},
            ],
            steps=["Press and cube tofu.", "Stir-fry veg and tofu.", "Add sauce, toss."],
            cuisine="chinese",
            dietary=["vegetarian", "vegan"],
            time_minutes=20,
        ),
        dict(
            title="Chicken Curry",
            ingredients=[
                {"name": "chicken thigh", "quantity": 500, "unit": "g"},
                {"name": "coconut milk", "quantity": 1, "unit": "cup"},
                {"name": "curry powder", "quantity": 2, "unit": "tbsp"},
                {"name": "onion", "quantity": 1, "unit": "pcs"},
            ],
            steps=["Saute onion.", "Brown chicken.", "Add curry powder and coconut milk, simmer 20 min."],
            cuisine="indian",
            dietary=[],
            time_minutes=40,
        ),
        dict(
            title="Buttermilk Pancakes",
            ingredients=[
                {"name": "flour", "quantity": 2, "unit": "cup"},
                {"name": "buttermilk", "quantity": 1.5, "unit": "cup"},
                {"name": "egg", "quantity": 2, "unit": "pcs"},
                {"name": "baking soda", "quantity": 1, "unit": "tsp"},
            ],
            steps=["Whisk dry ingredients.", "Whisk wet ingredients.", "Combine, cook on griddle."],
            cuisine="american",
            dietary=["vegetarian"],
            time_minutes=20,
        ),
        dict(
            title="Chickpea Salad",
            ingredients=[
                {"name": "chickpeas", "quantity": 1, "unit": "cup"},
                {"name": "cucumber", "quantity": 1, "unit": "pcs"},
                {"name": "feta", "quantity": 100, "unit": "g"},
                {"name": "lemon", "quantity": 1, "unit": "pcs"},
            ],
            steps=["Rinse chickpeas.", "Chop cucumber.", "Toss everything with lemon juice."],
            cuisine="mediterranean",
            dietary=["vegetarian"],
            time_minutes=10,
        ),
        dict(
            title="Beef Tacos",
            ingredients=[
                {"name": "ground beef", "quantity": 500, "unit": "g"},
                {"name": "taco shells", "quantity": 8, "unit": "pcs"},
                {"name": "onion", "quantity": 1, "unit": "pcs"},
                {"name": "cheddar", "quantity": 100, "unit": "g"},
            ],
            steps=["Brown beef with onion.", "Season.", "Fill shells, top with cheddar."],
            cuisine="mexican",
            dietary=[],
            time_minutes=25,
        ),
    ]
    for r in seed_recipes:
        rid = next(_recipe_ids)
        _recipes[rid] = Recipe(id=rid, **r)

    seed_ingredients = [
        ("buttermilk", ["milk + 1 tbsp lemon juice", "plain yogurt thinned with milk"]),
        ("egg", ["1/4 cup unsweetened applesauce", "1 tbsp ground flaxseed + 3 tbsp water"]),
        ("soy sauce", ["tamari", "coconut aminos"]),
        ("cilantro", ["parsley", "basil"]),
        ("coconut milk", ["heavy cream", "cashew cream"]),
    ]
    for name, subs in seed_ingredients:
        iid = len(_ingredient_catalog) + 1
        _ingredient_catalog[iid] = IngredientCatalogEntry(id=iid, name=name, substitutes=subs)

    seed_pantry = [
        ("rice", 2, "cup"),
        ("garlic", 5, "pcs"),
        ("onion", 3, "pcs"),
        ("soy sauce", 1, "cup"),
        ("egg", 6, "pcs"),
        ("cheddar", 200, "g"),
    ]
    for name, qty, unit in seed_pantry:
        pid = next(_pantry_ids)
        _pantry[pid] = PantryItem(id=pid, ingredient=name, quantity=qty, unit=unit)


_seed()


# --------------------------------------------------------------------------
# Recipes
# --------------------------------------------------------------------------

def list_recipes(
    query: str | None = None,
    max_minutes: int | None = None,
    dietary: list[str] | None = None,
    cuisine: str | None = None,
) -> list[Recipe]:
    """GET /recipes"""
    results = list(_recipes.values())
    if query:
        q = query.lower()
        results = [
            r for r in results
            if q in r.title.lower() or any(q in i["name"].lower() for i in r.ingredients)
        ]
    if max_minutes is not None:
        results = [r for r in results if r.time_minutes <= max_minutes]
    if dietary:
        wanted = set(dietary)
        results = [r for r in results if wanted.issubset(set(r.dietary))]
    if cuisine:
        results = [r for r in results if r.cuisine == cuisine]
    return results


def get_recipe(recipe_id: int) -> Recipe:
    """GET /recipes/{id}"""
    if recipe_id not in _recipes:
        raise PantryAPIError(f"recipe_id {recipe_id} not found")
    return _recipes[recipe_id]


def create_recipe(
    title: str,
    ingredients: list[dict],
    steps: list[str],
    cuisine: str | None = None,
    dietary: list[str] | None = None,
    time_minutes: int = 30,
) -> Recipe:
    """POST /recipes"""
    rid = next(_recipe_ids)
    recipe = Recipe(
        id=rid,
        title=title,
        ingredients=ingredients,
        steps=steps,
        cuisine=cuisine,
        dietary=dietary or [],
        time_minutes=time_minutes,
    )
    _recipes[rid] = recipe
    return recipe


def update_recipe(recipe_id: int, **fields) -> Recipe:
    """PUT /recipes/{id} -- exists in the backend, deliberately not exposed as a tool."""
    recipe = get_recipe(recipe_id)
    for k, v in fields.items():
        if hasattr(recipe, k) and v is not None:
            setattr(recipe, k, v)
    return recipe


def delete_recipe(recipe_id: int) -> None:
    """DELETE /recipes/{id} -- exists in the backend, deliberately not exposed as a tool."""
    if recipe_id not in _recipes:
        raise PantryAPIError(f"recipe_id {recipe_id} not found")
    del _recipes[recipe_id]


def similar_recipes(recipe_id: int, limit: int = 3) -> list[Recipe]:
    """GET /recipes/{id}/similar"""
    base = get_recipe(recipe_id)
    others = [r for r in _recipes.values() if r.id != recipe_id]
    others.sort(
        key=lambda r: (
            r.cuisine != base.cuisine,
            len(set(i["name"] for i in r.ingredients) & set(i["name"] for i in base.ingredients)) * -1,
        )
    )
    return others[:limit]


# --------------------------------------------------------------------------
# Ingredient catalog
# --------------------------------------------------------------------------

def search_ingredients(query: str) -> list[IngredientCatalogEntry]:
    """GET /ingredients"""
    q = query.lower()
    return [e for e in _ingredient_catalog.values() if q in e.name.lower()]


def get_ingredient(name: str) -> IngredientCatalogEntry:
    """GET /ingredients/{id} (looked up by name for convenience in this mock)"""
    for e in _ingredient_catalog.values():
        if e.name.lower() == name.lower():
            return e
    raise PantryAPIError(f"ingredient '{name}' not found in catalog")


# --------------------------------------------------------------------------
# Pantry
# --------------------------------------------------------------------------

def list_pantry() -> list[PantryItem]:
    """GET /pantry"""
    return list(_pantry.values())


def add_pantry_item(ingredient: str, quantity: float, unit: str) -> PantryItem:
    """POST /pantry"""
    for item in _pantry.values():
        if item.ingredient.lower() == ingredient.lower() and item.unit == unit:
            item.quantity += quantity
            return item
    pid = next(_pantry_ids)
    item = PantryItem(id=pid, ingredient=ingredient, quantity=quantity, unit=unit)
    _pantry[pid] = item
    return item


def update_pantry_item(item_id: int, quantity: float) -> PantryItem:
    """PATCH /pantry/{id}"""
    if item_id not in _pantry:
        raise PantryAPIError(f"pantry item_id {item_id} not found")
    _pantry[item_id].quantity = quantity
    return _pantry[item_id]


def remove_pantry_item(item_id: int) -> None:
    """DELETE /pantry/{id}"""
    if item_id not in _pantry:
        raise PantryAPIError(f"pantry item_id {item_id} not found")
    del _pantry[item_id]


def find_pantry_item_by_name(ingredient: str) -> PantryItem | None:
    for item in _pantry.values():
        if item.ingredient.lower() == ingredient.lower():
            return item
    return None


# --------------------------------------------------------------------------
# Meal plans
# --------------------------------------------------------------------------

def list_meal_plans() -> list[MealPlan]:
    """GET /meal-plans -- exists in the backend, deliberately not exposed as a tool."""
    return list(_meal_plans.values())


def create_meal_plan(start_date: str, days: int) -> MealPlan:
    """POST /meal-plans"""
    pid = next(_plan_ids)
    plan = MealPlan(id=pid, start_date=start_date, days=days)
    _meal_plans[pid] = plan
    return plan


def get_meal_plan(plan_id: int) -> MealPlan:
    """GET /meal-plans/{id}"""
    if plan_id not in _meal_plans:
        raise PantryAPIError(f"plan_id {plan_id} not found")
    return _meal_plans[plan_id]


def update_meal_plan(plan_id: int, **fields) -> MealPlan:
    """PUT /meal-plans/{id} -- exists in the backend, deliberately not exposed as a tool."""
    plan = get_meal_plan(plan_id)
    for k, v in fields.items():
        if hasattr(plan, k) and v is not None:
            setattr(plan, k, v)
    return plan


def add_recipe_to_plan_api(plan_id: int, recipe_id: int, day: str, meal_slot: MealSlot) -> MealPlan:
    """POST /meal-plans/{id}/recipes"""
    plan = get_meal_plan(plan_id)
    get_recipe(recipe_id)  # raises if missing
    plan.entries.append(PlanEntry(day=day, meal_slot=meal_slot, recipe_id=recipe_id))
    return plan


def remove_recipe_from_plan(plan_id: int, recipe_id: int) -> MealPlan:
    """DELETE /meal-plans/{id}/recipes/{rid} -- exists in the backend, deliberately not exposed as a tool."""
    plan = get_meal_plan(plan_id)
    plan.entries = [e for e in plan.entries if e.recipe_id != recipe_id]
    return plan


# --------------------------------------------------------------------------
# Shopping lists
# --------------------------------------------------------------------------

def generate_shopping_list(plan_id: int, exclude_pantry: bool = True) -> list[dict]:
    """GET /shopping-lists/{plan_id}"""
    plan = get_meal_plan(plan_id)
    needed: dict[tuple[str, str], float] = {}
    for entry in plan.entries:
        recipe = get_recipe(entry.recipe_id)
        for ing in recipe.ingredients:
            key = (ing["name"].lower(), ing["unit"])
            needed[key] = needed.get(key, 0) + ing["quantity"]

    have = {(i.ingredient.lower(), i.unit): i.quantity for i in _pantry.values()}

    shopping_list = []
    for (name, unit), qty in needed.items():
        have_qty = have.get((name, unit), 0) if exclude_pantry else 0
        remaining = max(qty - have_qty, 0)
        if remaining > 0:
            shopping_list.append({"ingredient": name, "quantity": round(remaining, 2), "unit": unit})
    return shopping_list


def check_shopping_item(list_id: int, ingredient: str) -> None:
    """POST /shopping-lists/{id}/check -- exists in the backend, deliberately not exposed as a tool."""
    return None  # no-op in this mock; app-side action per the article


# --------------------------------------------------------------------------
# Admin / user
# --------------------------------------------------------------------------

def admin_stats() -> dict:
    """GET /admin/stats -- exists in the backend, deliberately not exposed as a tool."""
    return {"recipes": len(_recipes), "pantry_items": len(_pantry), "meal_plans": len(_meal_plans)}


def rebuild_index() -> dict:
    """POST /admin/index/rebuild -- exists in the backend, deliberately not exposed as a tool."""
    return {"status": "ok"}


def get_preferences(user_id: str = "default") -> dict:
    """GET /users/{id}/preferences"""
    return dict(_preferences)


def update_preferences(user_id: str = "default", **fields) -> dict:
    """PUT /users/{id}/preferences -- exists in the backend, deliberately not exposed as a tool."""
    _preferences.update({k: v for k, v in fields.items() if v is not None})
    return dict(_preferences)


def to_dict(obj) -> dict:
    """Small helper: dataclass -> plain dict, for building tool/resource payloads."""
    return asdict(obj)
