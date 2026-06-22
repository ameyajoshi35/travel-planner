"""
Orchestrator — coordinates all agents using Parallel Fan-out / Fan-in.

Dependency graph:
  TripContext ──► PlannerAgent  ──► HotelAgent(cities)
             ├──► FlightAgent            │
             ├──► TrainAgent             │
             └──► VehicleAgent           │
                       │                 │
                       └─────── fan-in ──┘
                                 │
                            ImageSearch
                                 │
                          Assembled result

Phase 1 (parallel):  Planner + Flight + Train + Vehicle — all need only TripContext.
Phase 2 (sequential): Hotel — needs city list from Planner output.
Phase 3 (sequential): Image search — needs destination names from Planner output.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Generator

from .agents import FlightAgent, HotelAgent, PlannerAgent, TrainAgent, VehicleAgent
from .models import TripContext
from .search import search as tavily_search


def run(ctx: TripContext, phase: str) -> Generator[dict, None, None]:
    # ── Phase 1: announce parallel work ───────────────────────────────────────
    yield {"type": "searching", "query": "🗺️  Building your itinerary…"}
    yield {"type": "searching", "query": "✈️  Searching flight options…"}
    yield {"type": "searching", "query": "🚂  Finding train schedules…"}
    yield {"type": "searching", "query": "🚗  Checking vehicle rentals…"}

    # ── Phase 1: fan-out — run all 4 agents in parallel ───────────────────────
    agents = {
        "plan":    (PlannerAgent(), (ctx,),        {}),
        "flight":  (FlightAgent(),  (ctx,),        {}),
        "train":   (TrainAgent(),   (ctx,),        {}),
        "vehicle": (VehicleAgent(), (ctx,),        {}),
    }

    results: dict = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {
            pool.submit(agent.run, *args, **kwargs): key
            for key, (agent, args, kwargs) in agents.items()
        }
        for future in as_completed(futures):
            key = futures[future]
            results[key] = future.result()
            yield {"type": "searching", "query": f"✅  {key.title()} info ready"}

    plan = results.get("plan", {})

    # ── Phase 2: hotel agent — needs city list from planner ───────────────────
    dest_names = [d["name"] for d in plan.get("destinations", [])]
    if not dest_names and ctx.destination:
        dest_names = [ctx.destination]

    for city in dest_names[:3]:
        yield {"type": "searching", "query": f"🏨  Finding hotels in {city}…"}

    hotel_result = HotelAgent().run(ctx, dest_names)
    yield {"type": "searching", "query": "🏨  Hotel recommendations ready…"}

    # ── Yield structured results ───────────────────────────────────────────────
    yield {"type": "plan", "data": plan if plan else None}

    yield {
        "type": "transport",
        "flight":  results.get("flight",  {"options": [], "sources": []}),
        "train":   results.get("train",   {"options": [], "sources": []}),
        "vehicle": results.get("vehicle", {"options": [], "sources": []}),
    }

    yield {"type": "hotels", "by_location": hotel_result.get("by_city", {})}

    yield {
        "type": "sources",
        "data": {
            "destinations": plan.get("_sources", []),
            "flight":  results.get("flight",  {}).get("sources", []),
            "train":   results.get("train",   {}).get("sources", []),
            "car":     results.get("vehicle", {}).get("sources", []),
            "hotels":  hotel_result.get("sources", {}),
        },
    }

    # ── Phase 3: image searches ────────────────────────────────────────────────
    all_images: list = []
    by_dest: dict = {}

    for dest_name in dest_names[:3]:
        yield {"type": "searching", "query": f"📸  Finding photos of {dest_name}…"}
        for img_query in [
            f"{dest_name} India travel photography tourist attractions",
            f"{dest_name} India landmarks beautiful scenery",
        ]:
            img_result = tavily_search(img_query, max_results=3, include_images=True)
            imgs = img_result["images"][:5]
            by_dest.setdefault(dest_name, []).extend(imgs)
            all_images.extend(imgs)

    seen: set = set()
    unique_images = [img for img in all_images if not (img in seen or seen.add(img))]
    yield {"type": "images", "all": unique_images[:18], "by_dest": by_dest}
