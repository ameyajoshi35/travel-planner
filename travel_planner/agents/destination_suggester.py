"""
Destination Suggester — shows ALL curated places in the selected state as
pick-cards before the user commits to full planning.

Strategy:
  1. Pull the predefined places list from india_data.STATES[state]
  2. Two Tavily text searches for general state travel context
  3. ONE LLM call that generates a card for every place in the list at once
  4. Parallel Tavily image searches (one per place)

This gives 6–10 cards per state in ~25–30 seconds with 1 LLM call and
1 image search per destination.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

from .. import guards
from ..india_data import STATES
from ..llm import synthesize_json
from ..models import TripContext
from ..schemas import validate_suggester
from ..search import search as tavily_search

_SCHEMA_ITEM = """{
  "name": "Exact place name as given in the list",
  "tagline": "Short evocative tagline — 4–6 words",
  "description": "2 vivid sentences — the vibe, what makes it unique, and why this traveller in particular should go",
  "highlights": ["Top attraction 1", "Top attraction 2", "Top attraction 3"],
  "best_for": "e.g. Couples seeking serenity / Families with kids / Adventure seekers",
  "approx_cost_per_person": "e.g. ₹8,500–12,000 for the trip",
  "budget_fit": "Well within budget | Fits your budget | Slightly over budget",
  "weather_in_month": "One sentence on expected weather and why it is / isn't good for travel",
  "travel_time_from_origin": "e.g. 2h flight + 3h drive from Mumbai"
}"""


def suggest(ctx: TripContext) -> List[dict]:
    """
    Return destination cards for all curated places in ctx.state.
    Each dict has an `images` key added after parallel image search.
    """
    state    = ctx.state or "India"
    month    = ctx.travel_month or "the travel season"
    budget   = ctx.budget_total or 50000
    n        = ctx.num_travelers or 2
    starting = ctx.starting_city or "your city"
    t_type   = ctx.traveler_type or "travelers"
    exp      = ", ".join(ctx.experience_type) if ctx.experience_type else "sightseeing"
    duration = ctx.duration_days or 7
    per_pp   = budget // n

    # ── Full place list from curated data ────────────────────────────────────
    places: List[str] = STATES.get(state, [])
    if not places:
        # State not in our list — fall back to LLM discovery (rare)
        places = [state]

    # ── Two background searches for state travel context ─────────────────────
    q1 = f"tourist destinations {state} India {month} travel guide {exp} things to do"
    q2 = f"travel tips {state} India {t_type} budget travel {month} hidden gems"

    raw1 = tavily_search(q1, max_results=6, include_images=False)
    raw2 = tavily_search(q2, max_results=4, include_images=False)

    def _snip(results: list) -> str:
        return "\n".join(f"[{r['title']}] {r['content'][:300]}" for r in results)

    context = f"### {q1}\n{_snip(raw1['results'])}\n\n### {q2}\n{_snip(raw2['results'])}"

    # ── Single LLM call for all places ───────────────────────────────────────
    places_list = "\n".join(f"  {i+1}. {p}" for i, p in enumerate(places))
    system = (
        f"You are an India travel expert. Generate a travel card for each of the following "
        f"{len(places)} places in {state}, India.\n\n"
        f"Traveller profile:\n"
        f"  - Party: {n} {t_type} from {starting}\n"
        f"  - Total budget: ₹{budget:,} (≈ ₹{per_pp:,} per person)\n"
        f"  - Duration: {duration} days in {month}\n"
        f"  - Interests: {exp}\n\n"
        f"Places to cover (include ALL of them, in this order):\n{places_list}\n\n"
        f"For each place return an object shaped like:\n{_SCHEMA_ITEM}\n\n"
        f"Return a single JSON object:\n"
        f'{{"destinations": [ /* one object per place, in the same order */ ]}}'
    )

    user_content = (
        f"Context from search:\n\n{guards.wrap_untrusted(context)}\n\nReturn the JSON now."
    )
    data = synthesize_json(system, user_content, validate_suggester, max_tokens=4000) or {}
    destinations: List[dict] = data.get("destinations", [])

    # Guard: ensure every place from the list has a card (LLM sometimes skips)
    covered = {d.get("name", "").lower() for d in destinations}
    for place in places:
        if place.lower() not in covered:
            destinations.append({
                "name": place,
                "tagline": f"Explore {place}",
                "description": f"{place} is a beautiful destination in {state}, India.",
                "highlights": [],
                "best_for": t_type,
                "approx_cost_per_person": f"≈ ₹{per_pp:,}",
                "budget_fit": "Fits your budget",
                "weather_in_month": "",
                "travel_time_from_origin": "",
            })

    # ── Parallel image search — one query per place ───────────────────────────
    def _fetch_imgs(name: str) -> List[str]:
        r = tavily_search(
            f"{name} {state} India travel photography tourist attractions landscape",
            max_results=3, include_images=True,
        )
        imgs = r.get("images", [])
        seen: set = set()
        return [img for img in imgs if not (img in seen or seen.add(img))][:3]

    with ThreadPoolExecutor(max_workers=min(len(destinations), 8)) as pool:
        futures = {pool.submit(_fetch_imgs, d["name"]): i for i, d in enumerate(destinations)}
        for fut in as_completed(futures):
            idx = futures[fut]
            try:
                destinations[idx]["images"] = fut.result()
            except Exception:
                destinations[idx]["images"] = []

    return destinations
