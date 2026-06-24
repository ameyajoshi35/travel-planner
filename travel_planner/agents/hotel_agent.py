from typing import List

from .. import guards
from ..llm import synthesize_json
from ..models import TripContext
from ..prompts import HOTELS_JSON_SCHEMA
from ..schemas import validate_hotels
from ..search import search as tavily_search
from .base import BaseAgent


class HotelAgent(BaseAgent):
    """Finds Budget / Mid-range / Luxury hotel options per city."""

    def run(self, ctx: TripContext, cities: List[str] = None) -> dict:  # type: ignore[override]
        traveler_type = ctx.traveler_type or "travelers"

        if not cities:
            cities = [ctx.destination] if ctx.destination else []

        hotel_snippets: dict = {}
        sources: dict = {}

        for city in cities[:3]:
            result = tavily_search(
                f"best hotels {city} India price per night {traveler_type} booking options reviews",
                max_results=5,
                include_images=False,
            )
            hotel_snippets[city] = "\n".join(
                f"[{r['title']}] {r['content'][:500]}" for r in result["results"]
            )
            sources[city] = [
                {"title": r["title"], "url": r["url"]} for r in result["results"] if r.get("url")
            ]

        if not hotel_snippets:
            return {"by_city": {}, "sources": {}}

        system = (
            "You are a hotel expert for India travel. Based on the search results, suggest exactly "
            "3 hotels per city — one Budget, one Mid-range, one Luxury — with real hotel names, "
            "prices, ratings, and a one-line reason to pick each.\n\n"
            f"Return a JSON object using exactly this structure:\n{HOTELS_JSON_SCHEMA}"
        )
        search_snippets = "\n\n".join(
            f"### Hotels in {city}:\n{snippets}" for city, snippets in hotel_snippets.items()
        )
        # Trip context goes OUTSIDE the untrusted block so the model can trust it
        safe_user = (
            guards.wrap_untrusted(search_snippets)
            + f"\n\nTrip context: {ctx.to_json()}\n\nReturn the JSON now."
        )
        data = synthesize_json(system, safe_user, validate_hotels, max_tokens=1800) or {}
        return {"by_city": data.get("hotels_by_location", {}), "sources": sources}
