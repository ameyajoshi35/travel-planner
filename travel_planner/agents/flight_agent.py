from .. import guards
from ..llm import synthesize_json
from ..models import TripContext
from ..prompts import FLIGHT_OPTIONS_SCHEMA
from ..schemas import validate_transport
from ..search import search as tavily_search
from .base import BaseAgent


class FlightAgent(BaseAgent):
    """Finds flight options with real prices and booking details."""

    def run(self, ctx: TripContext) -> dict:
        dest = ctx.destination or "India"
        starting = ctx.starting_city or "your city"
        month = ctx.travel_month or "the travel season"
        num = ctx.num_travelers or 1

        queries = [
            f"flights {starting} to {dest} price fare economy class {month} airlines booking",
            f"cheapest flights {starting} {dest} {month} schedule timing",
        ]

        all_results = []
        sources = []
        for query in queries:
            result = tavily_search(query, max_results=5, include_images=False)
            snippets = "\n".join(
                f"[{r['title']}] {r['content'][:400]}" for r in result["results"]
            )
            all_results.append(f"### {query}\n{snippets}")
            sources += [{"title": r["title"], "url": r["url"]} for r in result["results"] if r.get("url")]

        system = (
            f"You are a flight booking expert. Based on the search results, list the best flight options "
            f"from {starting} to {dest} in {month} for {num} traveler(s).\n\n"
            f"Return a JSON object using exactly this structure:\n{FLIGHT_OPTIONS_SCHEMA}"
        )
        user_content = guards.wrap_untrusted("\n\n".join(all_results)) + "\n\nReturn the JSON now."
        data = synthesize_json(system, user_content, validate_transport, max_tokens=1000) or {}
        return {"options": data.get("options", []), "sources": sources}
