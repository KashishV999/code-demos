# Pantry MCP Server

A complete, runnable implementation of the design in the WorkOS article
[*Designing an MCP server from a REST API*](https://workos.com/blog/designing-mcp-server-from-rest-api).

The article works through a fictional 24-endpoint "Pantry" cookbook REST API
and designs an MCP server for it: **8 tools, 3 resources, 2 prompts** —
curated down from the naive "one tool per endpoint" approach. This project
implements exactly that design, end to end:

- `pantry_api.py` — an in-memory mock of the full 24-endpoint Pantry REST
  API (no external services, no database — it's just Python so the whole
  thing runs with one dependency).
- `server.py` — the MCP server itself, built with the official Python SDK's
  `FastMCP`, wrapping `pantry_api.py` per the article's design.
- `test_server.py` — an end-to-end smoke test that drives the server over
  the real MCP stdio protocol (not just calling the Python functions
  directly), the same way Claude Desktop or any other client would.

## What's implemented

**8 tools** (verbs the model decides to call):

| Tool | Maps to | Pattern |
|---|---|---|
| `search_recipes` | `GET /recipes` | 1-to-1, general search |
| `save_recipe` | `POST /recipes` | 1-to-1, clean mapping |
| `whats_for_dinner` | `GET /recipes` (pantry-weighted) | 1-to-N split of search |
| `plan_week_meals` | 5 endpoints combined | **N-to-1**, the flagship workflow tool |
| `update_pantry` | `POST`/`PATCH`/`DELETE /pantry` | N-to-1, bulk batch update |
| `add_recipe_to_plan` | `POST /meal-plans/{id}/recipes` | 1-to-1, targeted |
| `get_shopping_list` | `GET /shopping-lists/{plan_id}` | 1-to-1 |
| `suggest_substitutes` | `GET /ingredients/{id}` | 1-to-1, recipe-aware |

**3 resources** (nouns, pulled in by URI, no tool-call slot spent):

- `recipe://{id}` — full recipe detail
- `pantry://current` — current pantry contents
- `meal-plan://{id}` — a specific meal plan

**2 prompts** (user-invoked workflows):

- `weekly_meal_planning` — primes the agent to check the pantry and
  preferences, then call `plan_week_meals`
- `recipe_from_text` — walks the agent through parsing pasted recipe text
  and calling `save_recipe`

**Deliberately not exposed** (per the article's "0 to 1: don't expose this
at all"), though the endpoints still exist in `pantry_api.py`:
`/admin/*`, `DELETE /recipes/{id}`, `DELETE /meal-plans/{id}/recipes/{rid}`,
`PUT /recipes/{id}`, `PUT /meal-plans/{id}`, `PUT /users/{id}/preferences`,
`GET /meal-plans` (list), `POST /shopping-lists/{id}/check`.

Every design rule from the article shows up in the code:

- **Flat, top-level parameters** (`plan_week_meals(start_date, days, dietary, prefer_pantry)`, not a nested config object)
- **Constrained types** — `meal_slot` is a `Literal["breakfast", "lunch", "dinner"]`
- **Small, structured, self-summarizing returns** — every tool returns a
  short JSON object plus a one-sentence `summary` the model can quote back
  directly, instead of dumping raw records
- **Model-facing, recoverable errors** — e.g. `add_recipe_to_plan` with a
  bad id returns
  `"recipe_id 999 not found. Use search_recipes to find a valid recipe_id..."`
  instead of a raw exception or a generic `404`
- **N-to-1 aggregation** — `plan_week_meals` internally makes 5+ backend
  calls (read pantry, read preferences, query recipes, create plan, add
  recipes) but the model only makes one tool call
- **1-to-N splitting** — `search_recipes` and `whats_for_dinner` both read
  the recipe catalog but serve different intents, so they're separate tools
  with separate descriptions instead of one tool with a `mode` flag

## Setup

Requires Python 3.10+.

```bash
pip install -r requirements.txt
```

> **Note on `mcp` versions:** this project targets the `FastMCP` API as
> described in the article. The `mcp` package went through a breaking
> change (2.x renamed `FastMCP` to `MCPServer`), so `requirements.txt`
> pins `mcp==1.30.0`. If you have `mcp>=2` installed system-wide, use a
> virtualenv:
> ```bash
> python3 -m venv .venv && source .venv/bin/activate
> pip install -r requirements.txt
> ```

## Running

**Locally over stdio** (what Claude Desktop and the MCP Inspector use):

```bash
python server.py
```

**Locally over streamable HTTP** (for a remote client):

```bash
python server.py --http
# serves on http://127.0.0.1:8000
```

## Testing

Run the end-to-end smoke test, which spawns the server as a subprocess and
talks to it over the real MCP protocol:

```bash
python test_server.py
```

You should see 11 `OK` lines covering tool/resource/prompt registration,
the `plan_week_meals` workflow, the `meal-plan://` resource reflecting a
newly created plan, and the recoverable-error path.

You can also poke at it interactively with the official inspector:

```bash
npx @modelcontextprotocol/inspector python server.py
```

## Connecting to Claude Desktop

Add this to your Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "pantry": {
      "command": "python3",
      "args": ["/absolute/path/to/pantry-mcp/server.py"]
    }
  }
}
```

Then try prompts like:

- *"What can I make for dinner tonight with what I have?"*
- *"Plan me a week of dinners starting Monday."*
- *"I'm out of buttermilk, what can I use instead?"*
- *"I bought milk, eggs, and bread, and used up the flour."*

## Extending this to a real API

To point this at an actual REST backend instead of the in-memory mock,
swap out `pantry_api.py`'s function bodies for `httpx` calls against your
real endpoints — the tool layer in `server.py` doesn't need to change,
since it only depends on the function signatures, not their
implementation. That's the seam the article's design deliberately creates:
curation happens at the MCP layer, independent of how the backend is
actually implemented.




nano "$HOME/Library/Application Support/Claude/claude_desktop_config.json"


"$HOME/Library/Logs/Claude/main.log"