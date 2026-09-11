# Recipe & Meal-Planning Assistant (A2A multi-agent)

A host script orchestrates 3 independent A2A agent servers:

- **Pantry Agent** (port 10011) : tracks ingredients you have, stored in
  `pantry_agent/pantry_store.json`. 
- **Recipe Agent** (port 10012) : suggest a recipe from your available ingredients.
- **Grocery Agent** (port 10013) : what's missing between the suggested recipe and your pantry.

`host_client.py` is a terminal client that connects to all three, chains
the calls (pantry → recipe → grocery), and prints a full recipe and shopping list.

## Setup

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Set your OpenAI API key for the recipe agent:
   ```
   cd recipe_agent
   cp .env.example .env
   # edit .env and put your real key in OPENAI_API_KEY
   cd ..
   ```

## Running it

Open **4 terminals**:

```bash
# Terminal 1
cd pantry_agent && python __main__.py

# Terminal 2
cd recipe_agent && python __main__.py

# Terminal 3
cd grocery_agent && python __main__.py

# Terminal 4 (once all 3 servers are up)
python host_client.py
```

## Using it

- Type anything : 
Example : 
  - I want to eat something with chicken and rice.
  - I want to eat something sweet and cold.

