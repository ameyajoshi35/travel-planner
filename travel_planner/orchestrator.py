"""
Orchestrator — LangGraph StateGraph implementation.

Graph topology:
  START → phase1_agents → phase2_hotels → phase3_images → END

  phase1_agents : PlannerAgent + FlightAgent + TrainAgent + VehicleAgent
                  all run in parallel (ThreadPoolExecutor fan-out).
  phase2_hotels : HotelAgent — must wait for phase1 to know which cities.
  phase3_images : Tavily image searches for destination photos.

LangGraph's graph.stream(state, stream_mode="updates") yields one dict per
completed node:  {node_name: state_update}
The run() generator translates those updates into the typed event stream
that app.py already consumes unchanged.
"""

import operator
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Annotated, Generator, List, Optional

from typing_extensions import TypedDict

from langgraph.graph import END, START, StateGraph

from .agents import FlightAgent, HotelAgent, PlannerAgent, TrainAgent, VehicleAgent
from .models import TripContext
from .search import search as tavily_search


# ── LangGraph state ───────────────────────────────────────────────────────────
#
# TypedDict fields are the shared "blackboard" the graph nodes read and write.
# step_messages uses Annotated[list, operator.add] so each node can append its
# progress lines without overwriting messages from other nodes.

class TravelGraphState(TypedDict):
    ctx:                 object               # TripContext instance
    phase:               str                  # "planning" | "suggestion"
    plan:                Optional[dict]
    flight:              Optional[dict]
    train:               Optional[dict]
    vehicle:             Optional[dict]
    hotels_by_location:  dict
    sources:             dict
    all_images:          List[str]
    by_dest:             dict
    step_messages:       Annotated[List[str], operator.add]  # append-only


# ── Node 1: parallel agent fan-out ────────────────────────────────────────────

def _phase1_agents(state: TravelGraphState) -> dict:
    """
    Run Planner, Flight, Train, Vehicle agents concurrently.

    All four agents only need TripContext, so they can start immediately and
    run in parallel. ThreadPoolExecutor gives us the fan-out; as_completed()
    collects results as they finish.
    """
    ctx: TripContext = state["ctx"]

    step_messages: List[str] = [
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
        futures = {pool.submit(agent.run, ctx): key for key, agent in jobs.items()}
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


# ── Node 2: hotel agent (sequential — needs city list from planner) ───────────

def _phase2_hotels(state: TravelGraphState) -> dict:
    """
    Run HotelAgent after phase1 finishes.

    The hotel agent needs the list of destination cities from the planner's
    output, which is why it runs sequentially after phase1_agents.
    Also assembles the consolidated sources dict here.
    """
    ctx: TripContext = state["ctx"]
    plan = state.get("plan") or {}

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


# ── Node 3: image search (sequential — needs destination names from planner) ──

def _phase3_images(state: TravelGraphState) -> dict:
    """
    Fetch travel photos for each destination via Tavily image search.

    Runs after hotels because it's the last thing needed before the results
    page can fully render.
    """
    plan = state.get("plan") or {}
    ctx: TripContext = state["ctx"]

    dest_names = [d["name"] for d in plan.get("destinations", [])]
    if not dest_names and ctx.destination:
        dest_names = [ctx.destination]

    all_images: List[str] = []
    by_dest: dict = {}
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


# ── Build the compiled graph (module-level singleton) ─────────────────────────

def _build_graph():
    builder = StateGraph(TravelGraphState)

    # Register nodes
    builder.add_node("phase1_agents", _phase1_agents)
    builder.add_node("phase2_hotels", _phase2_hotels)
    builder.add_node("phase3_images", _phase3_images)

    # Wire edges: linear pipeline
    builder.add_edge(START,           "phase1_agents")
    builder.add_edge("phase1_agents", "phase2_hotels")
    builder.add_edge("phase2_hotels", "phase3_images")
    builder.add_edge("phase3_images", END)

    return builder.compile()


_graph = _build_graph()


# ── Public interface (unchanged — app.py consumes this generator) ─────────────

def run(ctx: TripContext, phase: str) -> Generator[dict, None, None]:
    """
    Execute the LangGraph travel planning pipeline and stream typed events.

    graph.stream(state, stream_mode="updates") yields one dict per completed
    node:  {node_name: {field: new_value, ...}}

    We translate those state updates into the event format that app.py expects,
    so the UI layer requires no changes.
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
    }

    for event in _graph.stream(initial, stream_mode="updates"):
        for node_name, update in event.items():

            # Every node can emit progress messages
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
