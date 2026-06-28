from .. import guards
from ..llm import synthesize_json
from ..models import TripContext
from ..prompts import PLANNER_JSON_SCHEMA, SUGGESTION_JSON_SCHEMA
from ..schemas import validate_plan
from ..search import search as tavily_search
from .base import BaseAgent


class PlannerAgent(BaseAgent):
    """Builds the day-by-day itinerary, destination cards, budget, and tips."""

    def run(self, ctx: TripContext, previous_feedback: str = "") -> dict:
        dest = ctx.destination or None
        state = ctx.state or None
        month = ctx.travel_month or "the travel season"
        duration = ctx.duration_days or 7
        starting = ctx.starting_city or "your city"
        budget = ctx.budget_total or 50000
        traveler_type = ctx.traveler_type or "travelers"
        exp = ", ".join(ctx.experience_type) if ctx.experience_type else "sightseeing"
        phase = "planning" if dest else "suggestion"

        # Build precise location string — always India-scoped
        location = dest or (f"{state}, India" if state else "India")

        if phase == "planning":
            queries = [
                f"{location} top tourist attractions places to visit must see things to do",
                f"{location} {month} activities local experiences travel guide",
                f"{location} {duration} day itinerary tips travel advice India",
            ]
        else:
            state_scope = f"in {state}" if state else "across India"
            queries = [
                f"best tourist destinations {state_scope} India {month} {exp}",
                f"top places to visit {state_scope} {traveler_type} budget ₹{budget} {duration} days",
                f"hidden gems must-visit {state_scope} India tourism {month}",
                f"popular travel spots {state_scope} India {traveler_type} {month}",
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
        state_scope = f" within {state}" if state else ""
        system = (
            f"You are an India travel expert. IMPORTANT: Only suggest destinations inside India{state_scope}. "
            f"Never suggest international destinations. All places must be real, verified Indian locations.\n\n"
            f"{'Create a detailed day-by-day trip plan' if phase == 'planning' else 'Suggest the best 3 destinations in India' + (f' in {state}' if state else '')}.\n\n"
            f"Trip details:\n{ctx.to_json()}\n\n"
            f"Return a JSON object using exactly this structure:\n{schema}"
        )

        if previous_feedback:
            system += f"\n\nPREVIOUS ATTEMPT FEEDBACK — you MUST fix these issues:\n{previous_feedback}"

        user_content = (
            f"Search results:\n\n{guards.wrap_untrusted(combined)}\n\nProduce the JSON plan now."
        )
        plan = synthesize_json(system, user_content, validate_plan, max_tokens=4096) or {}
        plan["_sources"]   = sources
        plan["_contexts"]  = all_results   # raw snippets for Ragas faithfulness eval
        return plan
