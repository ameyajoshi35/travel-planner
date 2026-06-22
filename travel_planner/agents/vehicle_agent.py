from ..llm import create_completion, parse_json
from ..models import TripContext
from ..prompts import VEHICLE_OPTIONS_SCHEMA
from ..search import search as tavily_search
from .base import BaseAgent


class VehicleAgent(BaseAgent):
    """Finds car rental and self-drive options with total cost estimates."""

    def run(self, ctx: TripContext) -> dict:
        dest = ctx.destination or "India"
        starting = ctx.starting_city or "your city"
        month = ctx.travel_month or "the travel season"
        duration = ctx.duration_days or 7

        queries = [
            f"car rental self drive {starting} to {dest} charges per day {month}",
            f"cab hire outstation {starting} {dest} cost per km with driver {duration} days",
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
            f"You are a vehicle rental expert for India. Based on the search results, list the best vehicle options "
            f"for a {duration}-day trip from {starting} to {dest}.\n\n"
            f"Return a JSON object using exactly this structure:\n{VEHICLE_OPTIONS_SCHEMA}"
        )
        response = create_completion(
            max_tokens=800,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": "\n\n".join(all_results) + "\n\nReturn the JSON now."},
            ],
        )
        data = parse_json(response.choices[0].message.content) or {}
        return {"options": data.get("options", []), "sources": sources}
