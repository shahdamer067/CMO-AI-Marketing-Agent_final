# CMO.AI: Marketing Strategy Agent

Part of **CMO.AI**, an autonomous multi-agent marketing platform (graduation project, 7-member team, **3rd place at the SRTA-City Graduation Project Competition, Nov 2025**).

CMO.AI uses a pipeline of agents (branding, marketing strategy, content, image, video). **This repository contains the Marketing Strategy Agent.** It takes a brand profile and produces a complete, number-backed marketing strategy.

> **My contribution:** I designed and built the Marketing Strategy Agent: the LangGraph workflow, the five calculation tools, the MongoDB layer and the FastAPI service.

## What it does

1. Loads the brand profile from MongoDB, or collects it through a short conversational intake if none exists.
2. Runs five deterministic tools that calculate the numbers (platforms, budget split, projections, campaign phases, KPIs).
3. Gives those results to an LLM (Llama 3.3 70B on Groq), which writes the full strategy using only the calculated figures.
4. Saves the strategy to MongoDB so the content, image and video agents can read it.

## Architecture

The agent is a **LangGraph state graph** with conditional routing:

```
start -> (profile passed in?) -> yes -> tools
                              -> no  -> check_profile (MongoDB)
                                           -> found -> tools
                                           -> not found -> intake (LLM asks questions) -> tools

tools: platform -> budget -> financial -> campaign -> kpi -> write_strategy (LLM) -> END
```

Design decision: the tools are called **directly by the graph** instead of through LLM tool-calling. Their inputs are already known, and an earlier version that let the LLM call them failed Groq's strict schema validation. The LLM is used where it adds value: the conversational intake and the strategy writing.

### The five tools (`tools.py`)

| Tool | Purpose |
|------|---------|
| `platform_recommender` | Ranks platforms for the industry, audience and goal |
| `budget_allocator` | Splits the budget across categories and platforms |
| `financial_projector` | Estimates clicks, conversions, revenue and ROAS |
| `campaign_structurer` | Builds a phased campaign timeline |
| `kpi_generator` | Produces goal-specific KPIs |

They are rule-based calculators that use approximate benchmark constants (CPC, CTR, conversion rate per platform), so the output is a planning estimate and not a guarantee.

## Project structure

```
agent.py          LangGraph workflow and MarketingStrategyAgent class
tools.py          The five calculation tools
database.py       MongoDB read/write layer
models.py         Pydantic data models (BrandProfile, MarketingStrategy, ...)
api.py            FastAPI service
test_agent.py     Tests (tools only, mode 1, mode 2)
```

## Quick start

```bash
pip install -r requirements.txt
cp .env.example .env        # add your GROQ_API_KEY and MONGODB_URI

python test_agent.py --tools-only   # no API key or database needed
python test_agent.py --mode1        # full run with a mock brand profile (needs GROQ_API_KEY)
python api.py                       # API on http://localhost:8001
```

Free Groq key: https://console.groq.com

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/strategy/generate` | Run the agent. Body: `{"user_id": "abc123"}` |
| GET | `/strategy/{user_id}` | Fetch the saved strategy |
| GET | `/health` | Health check |

## Tech stack

Python, LangGraph, LangChain, Groq (Llama 3.3 70B), FastAPI, MongoDB (PyMongo), Pydantic

## Known limitations

- The conversational intake runs through `MarketingStrategyAgent.run(conversation=[...])`. The `/strategy/generate` endpoint does not accept a conversation yet, so over the API it works with a saved or supplied brand profile.
- Average order value (50 USD) and campaign length (8 weeks) are fixed defaults.
- Benchmark constants are static and should be refreshed periodically.
