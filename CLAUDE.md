# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Setup

Requires two API keys:

```bash
export GROQ_API_KEY=gsk_…       # https://console.groq.com
export TAVILY_API_KEY=tvly-…    # https://app.tavily.com (free tier: 1000 searches/month)
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Running the app

**Streamlit UI (primary interface):**
```bash
streamlit run app.py
```
The app will prompt for the Groq API key in the sidebar if `GROQ_API_KEY` is not set.

**CLI mode:**
```bash
python -m travel_planner.main
```

## Architecture

The app is an India travel planning chatbot with two entry points sharing the same core logic:

- `app.py` — Streamlit web UI; manages session state (`trip_context`, `conversation_history`, `messages`, `awaiting_confirmation`, `phase`)
- `travel_planner/main.py` — CLI loop for terminal use

### Core modules

**`travel_planner/models.py` — `TripContext` dataclass**  
The single source of truth for a trip. Tracks hard requirements (dates, budget, starting city, traveler count, traveler type) and soft preferences (destination, experience type, travel mode, constraints). `is_complete()` gates when the confirmation flow begins; `missing_fields()` drives what the LLM asks next.

**`travel_planner/llm.py` — LLM calls via Groq**  
- `extract_inputs()` — structured extraction: given user message + current context JSON, returns a partial dict of `TripContext` fields. Strips markdown code fences before JSON parsing.
- `generate_response()` — conversational response that asks for the next missing field. System prompt is dynamically built from `missing_fields()` and current context JSON.
- `generate_confirmation()` — deterministic (no LLM); formats a human-readable trip summary from `TripContext`.
- `generate_plan()` — agentic loop (up to 8 rounds) that uses Groq tool calling with a `search_web` tool backed by Tavily. Yields `{"type": "searching", "query": ...}` events while searching and a final `{"type": "plan", "content": ...}` event when done. The model used is `llama-3.3-70b-versatile`.

**`travel_planner/search.py` — Tavily wrapper**  
Single `search(query, max_results=5)` function. Formats results as title/content/URL blocks joined by `---` separators for easy LLM consumption.

**`travel_planner/prompts.py` — all prompt strings**  
`EXTRACT_SYSTEM`, `RESPONSE_SYSTEM_TEMPLATE`, `CONFIRMATION_TEMPLATE`, and `OPENING_MESSAGE` are all defined here. Prompt changes are isolated to this file.

### Conversation flow

1. User describes trip → `extract_inputs()` populates `TripContext` → if incomplete, `generate_response()` asks for next missing field
2. Once `TripContext.is_complete()` → `generate_confirmation()` shows summary, sets `awaiting_confirmation = True`
3. User confirms → `phase` becomes `"planning"` (destination known) or `"suggestion"` (destination unknown); user denies → re-enters extraction loop
4. On next Streamlit render with `phase` set and `plan_generated = False` → `generate_plan()` runs the agentic search loop, shows live search progress via `st.status`, then renders the final markdown plan

The Streamlit UI mirrors this logic with session state; the CLI (`main.py`) only covers steps 1–3 and does not yet call `generate_plan`.
