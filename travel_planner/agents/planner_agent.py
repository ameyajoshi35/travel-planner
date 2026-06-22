from ..llm import create_completion, parse_json
from ..models import TripContext
from ..prompts import PLANNER_JSON_SCHEMA, SUGGESTION_JSON_SCHEMA
from ..search import search as tavily_search
from .base import BaseAgent


class PlannerAgent(BaseAgent):
    """Builds the day-by-day itinerary, destination cards, budget, and tips."""

    def run(self, ctx: TripContext) -> dict:
        dest = ctx.destination or "India"
        month = ctx.travel_month or "the travel season"
        duration = ctx.duration_days or 7
        starting = ctx.starting_city or "your city"
        budget = ctx.budget_total or 50000
        traveler_type = ctx.traveler_type or "travelers"
        exp = ", ".join(ctx.experience_type) if ctx.experience_type else "sightseeing"
        phase = "planning" if ctx.destination else "suggestion"

        if phase == "planning":
            queries = [
                f"{dest} India top tourist attractions places to visit must see",
                f"{dest} {month} things to do activities local experiences",
                f"{dest} India {duration} day travel itinerary guide tips",
            ]
        else:
            queries = [
                f"best travel destinations India {month} {exp} from {starting}",
                f"top places visit India {traveler_type} budget ₹{budget} {duration} days",
                f"India tourism {exp} {month} hidden gems unique destinations",
                f"popular Indian tourist destinations {month} {traveler_type}",
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

        combined = "\n\n".join(all_results)
        schema = PLANNER_JSON_SCHEMA if phase == "planning" else SUGGESTION_JSON_SCHEMA
        system = (
            f"You are an India travel expert. Based on the search results, "
            f"{'create a detailed trip plan' if phase == 'planning' else 'suggest the best 3 destinations'}.\n\n"
            f"Trip details:\n{ctx.to_json()}\n\n"
            f"Return a JSON object using exactly this structure:\n{schema}"
        )

        response = create_completion(
            max_tokens=3500,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": f"Search results:\n\n{combined}\n\nProduce the JSON plan now."},
            ],
        )
        plan = parse_json(response.choices[0].message.content) or {}
        plan["_sources"] = sources
        return plan
