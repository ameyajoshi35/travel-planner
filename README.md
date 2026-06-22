# India Travel Planner

An AI-powered travel planning app for India. Describe your trip, and the app searches the web in real time to build a personalised itinerary with transport options, hotel recommendations, and source links you can verify.

![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=flat&logo=streamlit&logoColor=white)
![Groq](https://img.shields.io/badge/Groq-LLaMA%203.3%2070B-orange?style=flat)
![Tavily](https://img.shields.io/badge/Tavily-Search-blue?style=flat)

## Features

- **Day-by-day itinerary** with morning / afternoon / evening plans
- **3 transport mode cards** — Flight, Train, and Rented Vehicle — with real costs and booking tips sourced from live web searches
- **Per-city hotel options** — Budget, Mid-range, and Luxury — for every overnight stop
- **Clickable source links** below each section so you can verify every detail
- **Destination suggestions** when you haven't decided where to go yet
- **Photo gallery** pulled from the web for each destination
- **Budget breakdown** with visual progress bars

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
  models.py      — TripContext dataclass (single source of truth for trip inputs)
  llm.py         — Groq/LLaMA calls: plan generation, hotel recommendations
  search.py      — Tavily web search wrapper
  prompts.py     — All prompt strings and JSON schemas
  main.py        — CLI entry point (covers input collection only)
app.py           — Streamlit UI (form → searching → results)
```

### How it works

1. **Form** — user fills in destination, dates, budget, traveler type, and experience preferences
2. **Search** — 6 targeted Tavily searches run in sequence (attractions, activities, itinerary, flight prices, train fares, car rental costs)
3. **Plan generation** — LLaMA 3.3 70B via Groq synthesises search results into a structured JSON plan (itinerary, transport, budget, tips)
4. **Hotel search** — per-city hotel searches run for each destination in the plan, followed by a second LLM call to produce Budget / Mid-range / Luxury options
5. **Image search** — destination photos fetched from Tavily
6. **Results** — everything rendered in a rich UI with source links throughout

### Models & APIs

| Component | Service |
|---|---|
| LLM | `llama-3.3-70b-versatile` via [Groq](https://groq.com) |
| Web search | [Tavily](https://tavily.com) |
| UI | [Streamlit](https://streamlit.io) |

## Deploying to Streamlit Cloud

1. Push the repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io) and connect your repo
3. Add secrets in **Manage app → Secrets**:

```toml
GROQ_API_KEY = "gsk_..."
TAVILY_API_KEY = "tvly-..."
```

## Rate limits

The free Groq tier allows ~30 requests/minute. The app retries automatically on rate limit errors with exponential back-off (8s, 16s). If you hit limits frequently, wait 60 seconds between searches or upgrade to a paid Groq plan.
