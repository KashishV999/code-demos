# Weather Demo

This project is a small AI agent demo that answers weather-related questions by using a tool to fetch forecast data from Open-Meteo. It uses the OpenAI Agents SDK with OpenRouter as the model provider so you can access different models through a single OpenAI-compatible endpoint.

## What this app does

- Accepts a user query such as: "What is the weather in Toronto on August 4 2026?"
- Uses an agent tool to find the location and retrieve weather forecast data
- Sends the prompt to a model through OpenRouter

## Requirements

- Python 3.10+
- An OpenRouter API key
- Optional: an OpenAI tracing key if you want to enable tracing export to OpenAI's platform

## Setup

1. Create and activate a virtual environment:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file from the example:

   ```bash
   cp .env.example .env
   ```

4. Add your API keys to the `.env` file:

   ```env
   OPENROUTER_API_KEY=your-openrouter-key
   OPENAI_TRACING_KEY=your-openai-tracing-key
   ```

## Run the app

```bash
python index.py
```

## Important note about OpenRouter and tracing

I am using an OpenRouter API key to access different models through the OpenAI-compatible API. That is used for model inference.

However, the OpenAI Agents SDK tracing feature is a separate service. It uploads run traces to the OpenAI platform, so for that part you need an OpenAI key as well. In short:

- `OPENROUTER_API_KEY` is used for sending model requests to OpenRouter
- `OPENAI_TRACING_KEY` is used only for tracing/exporting agent run logs to OpenAI's platform

If you do not have an OpenAI tracing key, the app may still work for normal model calls, but tracing export will not be available.

## Model configuration

The default model is set in `index.py`:

```python
MODEL_NAME = "anthropic/claude-haiku-4.5"
```

You can change this to another OpenRouter-supported model if you want.
