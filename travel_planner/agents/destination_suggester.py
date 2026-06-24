"""
Destination Suggester — lightweight first step before full planning.

For a given state + trip preferences, returns 3 destination cards with:
  - name, tagline, vivid description
  - top highlights
  - approx cost for the user's specific budget/party size
  - weather in travel month
  - estimated travel time from origin
  - photos (fetched in parallel from Tavily image search)
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

from ..llm import create_completion, parse_json
from ..models import TripContext
from ..search import search as tavily_search

_SCHEMA = """{
  "destinations": [
    {
      "name": "Place name (must be a real place inside the selected state, India)",
      "tagline": "Short evocative tagline — 4–6 words",
      "description": "2–3 vivid sentences on why this specific traveller should visit — mention the vibe, what makes it unique, and a personal touch",
      "highlights": ["Top attraction 1", "Top attraction 2", "Top attraction 3", "Top attraction 4"],
      "best_for": "e.g. Couples seeking serenity / Families with kids / Adventure seekers",
      "approx_cost_per_person": "e.g. ₹8,500–12,000 for the trip",
      "budget_fit": "Well within budget | Fits your budget | Slightly over budget",
      "weather_in_month": "One sentence — e.g. Pleasant 18–26°C, ideal for outdoor activities",
      "travel_time_from_origin": "e.g. 2h flight or 8h overnight train from Mumbai"
    }
  ]
}"""


def suggest(ctx: TripContext) -> List[dict]:
    """
    Return a list of 3 destination dicts, each enriched with an `images` key.
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

    # ── Two focused searches for top places in the state ─────────────────────
    q1 = f"best tourist places {state} India {month} {exp} must visit destinations"
    q2 = f"top travel destinations {state} India {t_type} {month} budget hidden gems"

    raw1 = tavily_search(q1, max_results=7, include_images=False)
    raw2 = tavily_search(q2, max_results=5, include_images=False)

    def _snip(results):
        return "\n".join(f"[{r['title']}] {r['content'][:400]}" for r in results)

    combined = f"### Query 1\n{_snip(raw1['results'])}\n\n### Query 2\n{_snip(raw2['results'])}"

    # ── LLM call ─────────────────────────────────────────────────────────────
    system = (
        f"You are an India travel expert. Suggest exactly 3 distinct, diverse destinations "
        f"WITHIN {state}, India for a {duration}-day trip in {month}.\n\n"
        f"Traveller profile:\n"
        f"  - Party: {n} {t_type} from {starting}\n"
        f"  - Total budget: ₹{budget:,} (≈ ₹{per_pp:,} per person)\n"
        f"  - Interests: {exp}\n\n"
        f"Rules:\n"
        f"  - ALL 3 destinations must be real, distinct places inside {state}, India only\n"
        f"  - No duplicate or near-duplicate suggestions\n"
        f"  - Give a mix: one popular, one offbeat, one hidden gem if possible\n"
        f"  - approx_cost_per_person must be tailored to the {duration}-day trip and their budget\n\n"
        f"Return exactly this JSON:\n{_SCHEMA}"
    )

    response = create_completion(
        max_tokens=2200,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": f"Search results:\n\n{combined}\n\nReturn 3 destination suggestion cards now."},
        ],
    )
    data = parse_json(response.choices[0].message.content) or {}
    destinations: List[dict] = data.get("destinations", [])[:3]

    if not destinations:
        return []

    # ── Fetch images per destination in parallel ──────────────────────────────
    def _fetch_imgs(name: str) -> List[str]:
        r1 = tavily_search(
            f"{name} {state} India travel photography tourist spots",
            max_results=3, include_images=True,
        )
        r2 = tavily_search(
            f"{name} India scenic beautiful landmark",
            max_results=2, include_images=True,
        )
        imgs = r1.get("images", [])[:4] + r2.get("images", [])[:2]
        seen: set = set()
        return [img for img in imgs if not (img in seen or seen.add(img))][:5]

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(_fetch_imgs, d["name"]): i for i, d in enumerate(destinations)}
        for fut in as_completed(futures):
            idx = futures[fut]
            try:
                destinations[idx]["images"] = fut.result()
            except Exception:
                destinations[idx]["images"] = []

    return destinations
