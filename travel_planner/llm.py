import json
import re
from typing import Generator, List, Optional

from groq import Groq

from .models import TripContext
from .prompts import (
    CONFIRMATION_TEMPLATE,
    EXTRACT_SYSTEM,
    PLAN_JSON_SCHEMA,
    RESPONSE_SYSTEM_TEMPLATE,
    SUGGESTION_JSON_SCHEMA,
)

MODEL = "llama-3.3-70b-versatile"
_client: Optional[Groq] = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq()
    return _client


def _chat(system: str, messages: List[dict], max_tokens: int) -> str:
    response = _get_client().chat.completions.create(
        model=MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "system", "content": system}] + messages,
    )
    return response.choices[0].message.content.strip()


def extract_inputs(user_message: str, trip_context: TripContext) -> dict:
    user_content = f"Current context: {trip_context.to_json()}\nUser said: {user_message}"
    raw = _chat(EXTRACT_SYSTEM, [{"role": "user", "content": user_content}], max_tokens=512)
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def generate_response(
    trip_context: TripContext,
    user_message: str,
    conversation_history: List[dict],
) -> str:
    system = RESPONSE_SYSTEM_TEMPLATE.format(
        missing_fields=", ".join(trip_context.missing_fields()) or "none",
        trip_context_json=trip_context.to_json(),
    )
    messages = conversation_history + [{"role": "user", "content": user_message}]
    return _chat(system, messages, max_tokens=1024)


def generate_plan_v2(trip_context: TripContext, phase: str) -> Generator[dict, None, None]:
    """
    Programmatic search + LLM synthesis (no tool calling).
    Yields:
      {"type": "searching", "query": str}
      {"type": "images", "all": list[str], "by_dest": dict[str, list[str]]}
      {"type": "plan", "data": dict | None, "text": str | None}
    """
    from .search import search as tavily_search

    dest = trip_context.destination or "India"
    month = trip_context.travel_month or "the travel season"
    starting = trip_context.starting_city or "your city"
    budget = trip_context.budget_total or 50000
    traveler_type = trip_context.traveler_type or "travelers"
    duration = trip_context.duration_days or 7
    exp = ", ".join(trip_context.experience_type) if trip_context.experience_type else "sightseeing"

    if phase == "planning":
        search_tasks = [
            (f"{dest} India top tourist attractions places to visit must see", dest),
            (f"best hotels {dest} India {traveler_type} accommodation options", dest),
            (f"{dest} {month} things to do activities local experiences", dest),
            (f"travel {starting} to {dest} trains flights road transport options", "transport"),
            (f"{dest} India {duration} day travel itinerary guide tips", dest),
        ]
    else:
        search_tasks = [
            (f"best travel destinations India {month} {exp} from {starting}", "destinations"),
            (f"top places visit India {traveler_type} budget ₹{budget} {duration} days", "destinations"),
            (f"India tourism {exp} {month} hidden gems unique destinations", "destinations"),
            (f"popular Indian tourist destinations {month} {traveler_type}", "destinations"),
        ]

    all_results: List[str] = []

    # Phase 1: text-only searches for planning content
    for query, label in search_tasks:
        yield {"type": "searching", "query": query}
        result = tavily_search(query, max_results=5, include_images=False)
        snippets = "\n".join(
            f"[{r['title']}] {r['content'][:400]}" for r in result["results"]
        )
        all_results.append(f"### {query}\n{snippets}")

    yield {"type": "searching", "query": "Crafting your personalised travel plan…"}

    combined_results = "\n\n".join(all_results)

    if phase == "planning":
        system = (
            f"You are an India travel expert. Based on the search results, create a detailed trip plan.\n\n"
            f"Trip details:\n{trip_context.to_json()}\n\n"
            f"IMPORTANT: Return ONLY the raw JSON object — no markdown fences, no explanation, "
            f"no text before or after. Start your response with {{ and end with }}.\n\n"
            f"Use this exact structure:\n{PLAN_JSON_SCHEMA}"
        )
    else:
        system = (
            f"You are an India travel expert. Based on the search results, suggest the best 3 destinations.\n\n"
            f"Trip details:\n{trip_context.to_json()}\n\n"
            f"IMPORTANT: Return ONLY the raw JSON object — no markdown fences, no explanation, "
            f"no text before or after. Start your response with {{ and end with }}.\n\n"
            f"Use this exact structure:\n{SUGGESTION_JSON_SCHEMA}"
        )

    response = _get_client().chat.completions.create(
        model=MODEL,
        max_tokens=6000,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": f"Search results:\n\n{combined_results}\n\nProduce the JSON plan now."},
        ],
    )

    raw = response.choices[0].message.content.strip()
    # Strip any markdown fences
    raw = re.sub(r"```(?:json)?", "", raw).strip()
    # Extract the outermost JSON object even if there's surrounding text
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        raw = raw[start : end + 1]

    try:
        plan_data = json.loads(raw)
    except json.JSONDecodeError:
        plan_data = None

    yield {"type": "plan", "data": plan_data, "text": raw if plan_data is None else None}

    # Phase 2: targeted image searches now that we know the exact destinations
    dest_names: List[str] = []
    if plan_data:
        dest_names = [d["name"] for d in plan_data.get("destinations", [])]
    if not dest_names:
        dest_names = [dest] if dest != "India" else []

    all_images: List[str] = []
    by_dest: dict = {}

    for dest_name in dest_names[:3]:
        yield {"type": "searching", "query": f"Finding authentic photos of {dest_name}…"}
        for img_query in [
            f"{dest_name} India travel photography tourist attractions",
            f"{dest_name} India landmarks beautiful scenery",
        ]:
            img_result = tavily_search(img_query, max_results=3, include_images=True)
            imgs = img_result["images"][:5]
            by_dest.setdefault(dest_name, []).extend(imgs)
            all_images.extend(imgs)

    # Deduplicate
    seen: set = set()
    unique_images = [img for img in all_images if not (img in seen or seen.add(img))]

    yield {"type": "images", "all": unique_images[:18], "by_dest": by_dest}


def generate_confirmation(trip_context: TripContext) -> str:
    ctx = trip_context

    if ctx.traveler_type == "solo":
        travelers_summary = "Solo traveler"
    elif ctx.num_travelers is not None:
        travelers_summary = f"{ctx.num_travelers} {ctx.traveler_type or 'travelers'}"
    else:
        travelers_summary = ctx.traveler_type or "unknown"

    if ctx.has_kids and ctx.kids_ages:
        travelers_summary += f" (kids: {', '.join(str(a) for a in ctx.kids_ages)} yrs)"
    elif ctx.has_kids:
        travelers_summary += " (with kids)"

    dates_summary = ctx.travel_dates or f"{ctx.duration_days} days in {ctx.travel_month}"
    vibe = ", ".join(ctx.experience_type) if ctx.experience_type else "open"

    kids_line = ""
    if ctx.has_kids and ctx.kids_ages:
        kids_line = f"\n - Kids: {', '.join(str(a) for a in ctx.kids_ages)} yrs old"

    constraints_line = ""
    if ctx.constraints:
        constraints_line = f"\n - Constraints: {', '.join(ctx.constraints)}"
    if ctx.has_elderly:
        constraints_line += "\n - Elderly travelers included"

    destination_line = ""
    if ctx.destination:
        destination_line = f"\n - Destination: {ctx.destination}"

    return CONFIRMATION_TEMPLATE.format(
        travelers_summary=travelers_summary,
        dates_summary=dates_summary,
        starting_city=ctx.starting_city,
        budget=f"{ctx.budget_total:,}",
        vibe=vibe,
        kids_line=kids_line,
        constraints_line=constraints_line,
        destination_line=destination_line,
    )
