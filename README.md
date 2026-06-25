# India Travel Planner

An AI-powered travel planning app for India. Describe your trip, and the app searches the web in real time to build a personalised itinerary with transport options, hotel recommendations, and source links you can verify.

![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=flat&logo=streamlit&logoColor=white)
![Groq](https://img.shields.io/badge/Groq-LLaMA%203.3%2070B-orange?style=flat)
![Tavily](https://img.shields.io/badge/Tavily-Search-blue?style=flat)
![LangChain](https://img.shields.io/badge/LangChain-LCEL-brightgreen?style=flat)
![LangGraph](https://img.shields.io/badge/LangGraph-StateGraph-purple?style=flat)

## Features

- **Day-by-day itinerary** with morning / afternoon / evening plans
- **3 transport mode cards** — Flight, Train, and Rented Vehicle — with real costs and booking tips sourced from live web searches
- **Per-city hotel options** — Budget, Mid-range, and Luxury — for every overnight stop
- **Clickable source links** below each section so you can verify every detail
- **Destination suggestions** when you haven't decided where to go yet — with a back button to switch destination after seeing the full plan
- **Photo gallery** pulled from the web for each destination
- **Budget breakdown** with visual progress bars
- **LLM reflection loop** — a critic node reviews every generated plan and requests a revision if duration, budget, scope, or fit requirements aren't met (up to 2 retries)
- **Security hardening** — all LLM and web content is XSS-escaped before rendering; Tavily results are fenced in an untrusted block to prevent prompt injection; all URLs are validated before use

## Setup

### Requirements

- Python 3.9+
- A [Groq](https://console.groq.com) API key (free tier works)
- A [Tavily](https://app.tavily.com) API key (free tier: 1,000 searches/month)

### Install

```bash
git clone https://github.com/ameyajoshi35/travel-planner.git
cd travel-planner
pip install -r requirements.txt
```

### Configure API keys

```bash
export GROQ_API_KEY=gsk_...
export TAVILY_API_KEY=tvly-...
```

Or create a `.env` file:

```
GROQ_API_KEY=gsk_...
TAVILY_API_KEY=tvly-...
```

## Running

```bash
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser.

## Architecture

```
travel_planner/
  models.py               — TripContext dataclass (single source of truth for trip inputs)
  llm.py                  — LangChain LCEL chains: extraction, conversation, plan synthesis
  search.py               — TavilySearchAPIWrapper (langchain-community)
  guards.py               — XSS escaping, URL validation, prompt-injection defences
  schemas.py              — Pydantic v2 models for all LLM outputs; validate_* helpers
  orchestrator.py         — LangGraph StateGraph pipeline (see below)
  agents/
    planner_agent.py      — Day-by-day itinerary + budget JSON
    flight_agent.py       — Real-time flight price search
    train_agent.py        — Train schedule and fare search
    vehicle_agent.py      — Car/bike rental options
    hotel_agent.py        — Per-city Budget / Mid-range / Luxury hotels
    destination_suggester.py — Destination cards when user hasn't decided
  availability_agent.py   — Live re-check of flights, trains, hotels before booking
  prompts.py              — All prompt strings and templates
  main.py                 — CLI entry point (input collection only)
app.py                    — Streamlit UI (form → suggestions → searching → results → booking)
evals/
  eval_fns.py             — 6 deterministic evaluators (no API calls)
  fixtures.py             — Sample trips and pre-baked plan fixtures
  test_evals.py           — pytest suite: offline tests + @pipeline integration tests
pytest.ini                — Registers the pipeline marker
```

### Pipeline (LangGraph StateGraph)

```
START → phase1_agents → reflect_plan ──(pass)──→ phase2_hotels → phase3_images → END
                              ↑
                              └──(revise, max 2 retries)──┘
```

| Node | What it does |
|---|---|
| `phase1_agents` | Runs Planner, Flight, Train, Vehicle agents concurrently via `ThreadPoolExecutor` |
| `reflect_plan` | LLM critic — checks duration, scope, budget, completeness, and traveller fit; routes back to `phase1_agents` with feedback if any criterion fails |
| `phase2_hotels` | `HotelAgent` — runs after reflection passes (needs the confirmed city list) |
| `phase3_images` | Tavily image searches for destination photos |

On a retry, the critique feedback is passed back to `PlannerAgent` as a standing instruction so the model knows exactly what to fix.

### LangChain components used

| Component | Package | Usage |
|---|---|---|
| `ChatGroq` | `langchain-groq` | LLM backend for all generation nodes |
| `ChatPromptTemplate` | `langchain-core` | Structured prompt construction |
| `JsonOutputParser` | `langchain-core` | Parses LLM JSON responses |
| `TavilySearchAPIWrapper` | `langchain-community` | Web search with image support |
| `StateGraph` | `langgraph` | Orchestration graph with conditional edges |

### Conversation flow

1. User describes trip → `extract_inputs()` populates `TripContext` → if incomplete, `generate_response()` asks for the next missing field
2. Once `TripContext.is_complete()` → confirmation summary shown
3. User confirms → `phase` becomes `"planning"` (destination known) or `"suggestion"` (destination unknown)
4. If suggestion phase: destination cards presented, user picks one
5. `orchestrator.run()` streams the LangGraph pipeline events to the UI — plan, transport, hotels, images
6. Results page shows full plan; if the trip came via suggestions, a **← Choose another destination** button lets the user go back and pick a different one

### Models & APIs

| Component | Service |
|---|---|
| LLM | `llama-3.3-70b-versatile` via [Groq](https://groq.com) |
| Web search | [Tavily](https://tavily.com) |
| UI | [Streamlit](https://streamlit.io) |

## Evals

The `evals/` directory contains a deterministic test suite that runs without any API calls.

```bash
# Offline tests only (instant):
pytest evals/test_evals.py

# Include live pipeline tests (~60–120 s each, requires API keys):
pytest evals/test_evals.py -m pipeline --run-pipeline
```

### Offline evaluators

| Eval | What it checks | Pass threshold |
|---|---|---|
| `schema_validity` | All 5 required keys present + Pydantic type validation | All keys present |
| `completeness` | trip_title, destinations, itinerary, budget, tips all non-empty | ≥ 4 of 5 sections |
| `duration_faithfulness` | Itinerary day count matches requested days | ± 1 day |
| `budget_faithfulness` | Estimated total ≤ stated budget | ≤ 120 % of budget |
| `scope_adherence` | Plan text mentions the requested Indian state | Exact mention |
| `experience_relevance` | Plan content contains keywords for requested experience types | ≥ 50 % match |

## Deploying to Streamlit Cloud

1. Push the repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io) and connect your repo
3. Add secrets in **Manage app → Secrets**:

```toml
GROQ_API_KEY = "gsk_..."
TAVILY_API_KEY = "tvly-..."
```

## Rate limits

The free Groq tier allows ~30 requests/minute. The reflection loop makes one additional LLM call per plan generation (and up to 2 more on retries), so budget ~3–4 Groq calls per full pipeline run.

The free Tavily tier allows 1,000 searches/month. Each pipeline run uses approximately 10–14 searches (destinations, transport, hotels, images).
