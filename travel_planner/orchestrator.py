"""
Orchestrator — LangGraph StateGraph with a reflection loop.

Graph topology:

  START → phase1_agents → reflect_plan ──(pass)──→ phase2_hotels → phase3_images → END
                               ↑
                               └──(revise, max 2 retries)──┘

  phase1_agents : PlannerAgent + FlightAgent + TrainAgent + VehicleAgent in parallel.
  reflect_plan  : LLM critique — checks the plan meets duration, budget, scope, and
                  traveler requirements. If it fails and retries remain, routes back
                  to phase1_agents with the feedback appended to the planner prompt.
  phase2_hotels : HotelAgent — runs after reflection passes (needs city list).
  phase3_images : Tavily image searches for destination photos.
"""

import operator
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Annotated, Generator, List, Optional

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from typing_extensions import TypedDict

from langgraph.graph import END, START, StateGraph

from .agents import FlightAgent, HotelAgent, PlannerAgent, TrainAgent, VehicleAgent
from .llm import get_llm
from .models import TripContext
from .search import search as tavily_search

MAX_RETRIES = 2


# ── LangGraph state ───────────────────────────────────────────────────────────

class TravelGraphState(TypedDict):
    ctx:                 object                              # TripContext instance
    phase:               str                                 # "planning" | "suggestion"
    plan:                Optional[dict]
    flight:              Optional[dict]
    train:               Optional[dict]
    vehicle:             Optional[dict]
    hotels_by_location:  dict
    sources:             dict
    all_images:          List[str]
    by_dest:             dict
    step_messages:       Annotated[List[str], operator.add]  # append-only
    retry_count:         int   # how many plan revisions have been attempted
    reflection_ok:       bool  # True once the reflection node approves the plan
    reflection_feedback: str   # critique text passed back to the planner on retry


# ── Node 1: parallel agent fan-out ────────────────────────────────────────────

def _phase1_agents(state: TravelGraphState) -> dict:
    """
    Run Planner, Flight, Train, Vehicle agents concurrently.

    On a retry the planner receives the reflection feedback so it can
    address the specific issues found in the previous attempt.
    """
    ctx: TripContext    = state["ctx"]
    feedback: str       = state.get("reflection_feedback", "")
    retry_count: int    = state.get("retry_count", 0)

    if retry_count > 0 and feedback:
        step_messages = [f"🔄  Revising plan (attempt {retry_count + 1}/{MAX_RETRIES + 1}): {feedback[:80]}…"]
    else:
        step_messages = [
            "🗺️  Building your itinerary…",
            "✈️  Searching flight options…",
            "🚂  Finding train schedules…",
            "🚗  Checking vehicle rentals…",
        ]

    jobs = {
        "plan":    PlannerAgent(),
        "flight":  FlightAgent(),
        "train":   TrainAgent(),
        "vehicle": VehicleAgent(),
    }

    results: dict = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        def _run(key: str, agent):
            if key == "plan":
                return agent.run(ctx, previous_feedback=feedback)
            return agent.run(ctx)

        futures = {pool.submit(_run, key, agent): key for key, agent in jobs.items()}
        for future in as_completed(futures):
            key = futures[future]
            results[key] = future.result()
            step_messages.append(f"✅  {key.title()} info ready")

    plan = results.get("plan", {})
    return {
        "plan":          plan,
        "flight":        results.get("flight",  {"options": [], "sources": []}),
        "train":         results.get("train",   {"options": [], "sources": []}),
        "vehicle":       results.get("vehicle", {"options": [], "sources": []}),
        "step_messages": step_messages,
    }


# ── Node 2: reflection / critique ─────────────────────────────────────────────

def _reflect_plan(state: TravelGraphState) -> dict:
    """
    LLM-powered critique of the generated plan.

    Checks five criteria against the traveller's original requirements:
      1. Duration   — itinerary length matches requested days (±1 ok)
      2. Scope      — destinations stay within the specified Indian state
      3. Budget     — estimated total ≤ stated budget (20% over tolerated)
      4. Completeness — plan has destinations, itinerary, and budget sections
      5. Fit        — appropriate for traveller type and experience interests

    On pass  → sets reflection_ok=True, routes to phase2_hotels.
    On fail  → sets reflection_ok=False + feedback, routes back to phase1_agents.
    After MAX_RETRIES failures we pass anyway to avoid an infinite loop.
    """
    ctx: TripContext = state["ctx"]
    plan            = state.get("plan") or {}
    retry_count     = state.get("retry_count", 0)

    # If plan is structurally empty, fail immediately (no point asking the LLM)
    if not plan.get("itinerary") and not plan.get("destinations"):
        if retry_count >= MAX_RETRIES:
            return {
                "reflection_ok":       True,   # give up gracefully
                "reflection_feedback": "",
                "step_messages":       ["⚠️  Could not generate a valid plan — proceeding with best effort…"],
            }
        return {
            "reflection_ok":       False,
            "reflection_feedback": "The plan was empty. Generate a complete itinerary with destinations and a day-by-day schedule.",
            "retry_count":         retry_count + 1,
            "step_messages":       ["🔍  Plan was empty — regenerating…"],
        }

    # Summarise the plan for the LLM reviewer (avoid sending the full JSON)
    dest_names     = [d.get("name", "") for d in plan.get("destinations", [])]
    itinerary_days = len(plan.get("itinerary", []))
    budget_total   = sum(
        v for v in plan.get("budget", {}).values() if isinstance(v, (int, float))
    )

    plan_summary = (
        f"Destinations: {', '.join(dest_names) or 'none listed'}\n"
        f"Itinerary days: {itinerary_days}\n"
        f"Estimated budget total: ₹{int(budget_total):,}\n"
        f"Has tips section: {'yes' if plan.get('tips') else 'no'}\n"
        f"Overview snippet: {plan.get('overview', '')[:150]}"
    )

    requirements = (
        f"State / region : {ctx.state or 'India'}\n"
        f"Requested days : {ctx.duration_days}\n"
        f"Total budget   : ₹{ctx.budget_total:,}\n"
        f"Travelers      : {ctx.num_travelers} × {ctx.traveler_type}\n"
        f"Interests      : {', '.join(ctx.experience_type) if ctx.experience_type else 'general'}\n"
        f"Departing from : {ctx.starting_city}\n"
        f"Traveling with kids: {ctx.has_kids}"
    )

    system = (
        "You are a strict quality reviewer for India travel itineraries.\n"
        "Compare the generated plan summary against the traveller's requirements.\n\n"
        "Check:\n"
        "1. DURATION    — itinerary days ≈ requested days (±1 acceptable)\n"
        "2. SCOPE       — all destinations are within the specified Indian state/region\n"
        "3. BUDGET      — estimated total ≤ stated budget (up to 20% over is acceptable)\n"
        "4. COMPLETENESS — plan has at least one destination, itinerary days, and budget\n"
        "5. FIT         — plan suits the traveller type and stated interests\n\n"
        "Be lenient on minor issues. Only fail if there is a clear, significant problem.\n\n"
        'Return JSON exactly: {"pass": true, "feedback": "Plan meets all requirements"}\n'
        'or:                  {"pass": false, "feedback": "Specific issues that must be fixed"}'
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", "{system}"),
        ("human", "REQUIREMENTS:\n{requirements}\n\nPLAN SUMMARY:\n{plan_summary}\n\nDoes this plan pass review?"),
    ])
    chain = prompt | get_llm(max_tokens=300) | JsonOutputParser()

    try:
        result  = chain.invoke({"system": system, "requirements": requirements, "plan_summary": plan_summary})
        passed  = bool(result.get("pass", True))
        feedback = str(result.get("feedback", ""))
    except Exception:
        # If the reflection LLM call itself fails, don't block the pipeline
        passed, feedback = True, ""

    if passed:
        return {
            "reflection_ok":       True,
            "reflection_feedback": feedback,
            "step_messages":       ["✅  Plan review passed — building hotel options…"],
        }

    # Failed — but have we used all retries?
    if retry_count >= MAX_RETRIES:
        return {
            "reflection_ok":       True,   # accept and move on
            "reflection_feedback": feedback,
            "step_messages":       [f"⚠️  Plan has issues but max retries reached — proceeding: {feedback[:80]}"],
        }

    return {
        "reflection_ok":       False,
        "reflection_feedback": feedback,
        "retry_count":         retry_count + 1,
        "step_messages":       [f"🔄  Plan needs revision: {feedback[:100]}"],
    }


# ── Conditional router (after reflect_plan) ───────────────────────────────────

def _route_after_reflection(state: TravelGraphState) -> str:
    """Return the name of the next node based on the reflection result."""
    if state.get("reflection_ok", True):
        return "phase2_hotels"
    return "phase1_agents"


# ── Node 3: hotel agent (sequential — needs city list from planner) ───────────

def _phase2_hotels(state: TravelGraphState) -> dict:
    ctx: TripContext = state["ctx"]
    plan            = state.get("plan") or {}

    dest_names = [d["name"] for d in plan.get("destinations", [])]
    if not dest_names and ctx.destination:
        dest_names = [ctx.destination]

    step_messages = [f"🏨  Finding hotels in {city}…" for city in dest_names[:3]]

    hotel_result = HotelAgent().run(ctx, dest_names)
    step_messages.append("🏨  Hotel recommendations ready…")

    sources = {
        "destinations": plan.get("_sources", []),
        "flight":       state.get("flight",  {}).get("sources", []),
        "train":        state.get("train",   {}).get("sources", []),
        "car":          state.get("vehicle", {}).get("sources", []),
        "hotels":       hotel_result.get("sources", {}),
    }

    return {
        "hotels_by_location": hotel_result.get("by_city", {}),
        "sources":            sources,
        "step_messages":      step_messages,
    }


# ── Node 4: image search ──────────────────────────────────────────────────────

def _phase3_images(state: TravelGraphState) -> dict:
    plan = state.get("plan") or {}
    ctx: TripContext = state["ctx"]

    dest_names = [d["name"] for d in plan.get("destinations", [])]
    if not dest_names and ctx.destination:
        dest_names = [ctx.destination]

    all_images: List[str] = []
    by_dest: dict         = {}
    step_messages: List[str] = []

    for name in dest_names[:3]:
        step_messages.append(f"📸  Finding photos of {name}…")
        for query in [
            f"{name} India travel photography tourist attractions",
            f"{name} India landmarks beautiful scenery",
        ]:
            imgs = tavily_search(query, max_results=3, include_images=True)["images"][:5]
            by_dest.setdefault(name, []).extend(imgs)
            all_images.extend(imgs)

    seen: set = set()
    unique_images = [img for img in all_images if not (img in seen or seen.add(img))]

    return {
        "all_images":    unique_images[:18],
        "by_dest":       by_dest,
        "step_messages": step_messages,
    }


# ── Build the compiled graph ──────────────────────────────────────────────────

def _build_graph():
    builder = StateGraph(TravelGraphState)

    builder.add_node("phase1_agents", _phase1_agents)
    builder.add_node("reflect_plan",  _reflect_plan)
    builder.add_node("phase2_hotels", _phase2_hotels)
    builder.add_node("phase3_images", _phase3_images)

    builder.add_edge(START,           "phase1_agents")
    builder.add_edge("phase1_agents", "reflect_plan")

    # Conditional edge: pass → hotels, fail → back to agents (capped at MAX_RETRIES)
    builder.add_conditional_edges(
        "reflect_plan",
        _route_after_reflection,
        {
            "phase2_hotels": "phase2_hotels",
            "phase1_agents": "phase1_agents",
        },
    )

    builder.add_edge("phase2_hotels", "phase3_images")
    builder.add_edge("phase3_images", END)

    return builder.compile()


_graph = _build_graph()


# ── Public interface ──────────────────────────────────────────────────────────

def run(ctx: TripContext, phase: str) -> Generator[dict, None, None]:
    """
    Execute the LangGraph pipeline and stream typed events to app.py.

    The reflect_plan node may cause phase1_agents to run more than once
    (up to MAX_RETRIES + 1 times total). Each retry passes the critique
    feedback to the planner so it can correct specific issues.
    """
    initial: TravelGraphState = {
        "ctx":                ctx,
        "phase":              phase,
        "plan":               None,
        "flight":             None,
        "train":              None,
        "vehicle":            None,
        "hotels_by_location": {},
        "sources":            {},
        "all_images":         [],
        "by_dest":            {},
        "step_messages":      [],
        "retry_count":        0,
        "reflection_ok":      False,
        "reflection_feedback": "",
    }

    for event in _graph.stream(initial, stream_mode="updates"):
        for node_name, update in event.items():

            for msg in update.get("step_messages", []):
                yield {"type": "searching", "query": msg}

            if node_name == "phase1_agents":
                yield {"type": "plan", "data": update.get("plan")}
                yield {
                    "type":    "transport",
                    "flight":  update.get("flight",  {"options": [], "sources": []}),
                    "train":   update.get("train",   {"options": [], "sources": []}),
                    "vehicle": update.get("vehicle", {"options": [], "sources": []}),
                }

            elif node_name == "phase2_hotels":
                yield {"type": "hotels",  "by_location": update.get("hotels_by_location", {})}
                yield {"type": "sources", "data":        update.get("sources", {})}

            elif node_name == "phase3_images":
                yield {
                    "type":    "images",
                    "all":     update.get("all_images", []),
                    "by_dest": update.get("by_dest",    {}),
                }
            # reflect_plan events are step_messages only — already yielded above
