import json
import re
import time
from typing import Callable, Generator, List, Optional

from groq import Groq, RateLimitError

from . import guards
from .models import TripContext
from .prompts import (
    CONFIRMATION_TEMPLATE,
    EXTRACT_SYSTEM,
    HOTELS_JSON_SCHEMA,
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
    return _create(
        max_tokens=max_tokens,
        messages=[{"role": "system", "content": system}] + messages,
    ).choices[0].message.content.strip()


def _create(max_tokens: int, messages: list, response_format: Optional[dict] = None) -> object:
    kwargs = dict(model=MODEL, max_tokens=max_tokens, messages=messages)
    if response_format:
        kwargs["response_format"] = response_format
    for attempt in range(3):
        try:
            return _get_client().chat.completions.create(**kwargs)
        except RateLimitError:
            if attempt < 2:
                time.sleep(8 * (attempt + 1))  # 8s, 16s
            else:
                raise


# Public helpers for agents to import
create_completion = _create


def synthesize_json(
    system: str,
    user_content: str,
    validate_fn: Callable,
    max_tokens: int,
) -> Optional[dict]:
    """Hardened LLM call: injection-defense header → JSON mode → schema validate → repair retry."""
    system = guards.INJECTION_DEFENSE + system
    messages: List[dict] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]

    def _call() -> str:
        return _create(
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
            messages=messages,
        ).choices[0].message.content

    raw = _call()
    clean = validate_fn(parse_json(raw))
    if clean is not None:
        return clean

    # Repair turn — tell model what went wrong and try once more
    messages.append({"role": "assistant", "content": raw})
    messages.append({
        "role": "user",
        "content": (
            "Your previous response was not valid JSON matching the required schema. "
            "Return ONLY a single valid JSON object matching the schema exactly — "
            "no prose, no markdown, no code fences."
        ),
    })
    return validate_fn(parse_json(_call()))


def parse_json(s: str) -> Optional[dict]:
    """Parse JSON from an LLM response with fallback cleanup."""
    s = re.sub(r"```(?:json)?", "", s).strip()
    start, end = s.find("{"), s.rfind("}")
    if start != -1 and end != -1 and end > start:
        s = s[start : end + 1]
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        fixed = re.sub(r",(\s*[}\]])", r"\1", s)
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            return None


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
            (f"{dest} {month} things to do activities local experiences", dest),
            (f"{dest} India {duration} day travel itinerary guide tips", dest),
            (f"flights {starting} to {dest} price fare economy class {month} airlines booking", "transport_flight"),
            (f"train {starting} to {dest} IRCTC express schedule fare class {month}", "transport_train"),
            (f"car rental self drive cab hire {starting} to {dest} charges per day {month}", "transport_car"),
        ]
    else:
        search_tasks = [
            (f"best travel destinations India {month} {exp} from {starting}", "destinations"),
            (f"top places visit India {traveler_type} budget ₹{budget} {duration} days", "destinations"),
            (f"India tourism {exp} {month} hidden gems unique destinations", "destinations"),
            (f"popular Indian tourist destinations {month} {traveler_type}", "destinations"),
        ]

    all_results: List[str] = []
    all_sources: dict = {"flight": [], "train": [], "car": [], "destinations": [], "hotels": {}}

    # Phase 1: text-only searches for planning content
    for query, label in search_tasks:
        yield {"type": "searching", "query": query}
        result = tavily_search(query, max_results=5, include_images=False)
        snippets = "\n".join(
            f"[{r['title']}] {r['content'][:400]}" for r in result["results"]
        )
        all_results.append(f"### {query}\n{snippets}")

        urls = [{"title": r["title"], "url": r["url"]} for r in result["results"] if r.get("url")]
        if label == "transport_flight":
            all_sources["flight"].extend(urls)
        elif label == "transport_train":
            all_sources["train"].extend(urls)
        elif label == "transport_car":
            all_sources["car"].extend(urls)
        else:
            all_sources["destinations"].extend(urls)

    yield {"type": "searching", "query": "Crafting your personalised travel plan…"}

    combined_results = "\n\n".join(all_results)

    if phase == "planning":
        system = (
            f"You are an India travel expert. Based on the search results, create a detailed trip plan.\n\n"
            f"Trip details:\n{trip_context.to_json()}\n\n"
            f"Return a JSON object using exactly this structure:\n{PLAN_JSON_SCHEMA}"
        )
    else:
        system = (
            f"You are an India travel expert. Based on the search results, suggest the best 3 destinations.\n\n"
            f"Trip details:\n{trip_context.to_json()}\n\n"
            f"Return a JSON object using exactly this structure:\n{SUGGESTION_JSON_SCHEMA}"
        )

    response = _create(
        max_tokens=3500,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": f"Search results:\n\n{combined_results}\n\nProduce the JSON plan now."},
        ],
    )

    raw = response.choices[0].message.content.strip()

    def _try_parse(s: str):
        # Strip markdown fences and extract outermost {}
        s = re.sub(r"```(?:json)?", "", s).strip()
        start = s.find("{")
        end = s.rfind("}")
        if start != -1 and end != -1 and end > start:
            s = s[start : end + 1]
        try:
            return json.loads(s), s
        except json.JSONDecodeError:
            # Remove trailing commas before } or ]
            fixed = re.sub(r",(\s*[}\]])", r"\1", s)
            try:
                return json.loads(fixed), fixed
            except json.JSONDecodeError:
                return None, s

    plan_data, raw = _try_parse(raw)

    yield {"type": "plan", "data": plan_data, "text": None}

    # Phase 2: per-city hotel searches
    hotels_by_location: dict = {}
    if plan_data and phase == "planning":
        dest_cities = [d["name"] for d in plan_data.get("destinations", [])]
        if not dest_cities:
            dest_cities = [dest]

        hotel_search_results: dict = {}
        for city in dest_cities[:3]:
            yield {"type": "searching", "query": f"Finding hotel options in {city}…"}
            hotel_result = tavily_search(
                f"best hotels {city} India price per night {traveler_type} booking options reviews",
                max_results=5, include_images=False,
            )
            hotel_search_results[city] = "\n".join(
                f"[{r['title']}] {r['content'][:500]}" for r in hotel_result["results"]
            )
            all_sources["hotels"][city] = [
                {"title": r["title"], "url": r["url"]} for r in hotel_result["results"] if r.get("url")
            ]

        yield {"type": "searching", "query": "Compiling hotel recommendations…"}
        hotel_system = (
            "You are a hotel expert for India travel. Based on the search results below, suggest exactly "
            "3 hotels per city — one Budget, one Mid-range, one Luxury — with real hotel names, prices, "
            "ratings, and a one-line reason to pick each.\n\n"
            "Return a JSON object with this exact structure:\n"
            f"{HOTELS_JSON_SCHEMA}"
        )
        hotel_user = "\n\n".join(
            f"### Hotels in {city}:\n{snippets}"
            for city, snippets in hotel_search_results.items()
        ) + f"\n\nTrip context: {trip_context.to_json()}"

        hotel_response = _create(
            max_tokens=1800,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": hotel_system},
                {"role": "user", "content": hotel_user + "\n\nReturn the JSON now."},
            ],
        )
        hotel_data, _ = _try_parse(hotel_response.choices[0].message.content)
        hotels_by_location = (hotel_data or {}).get("hotels_by_location", {})

    yield {"type": "hotels", "by_location": hotels_by_location}
    yield {"type": "sources", "data": all_sources}

    # Phase 3: targeted image searches now that we know the exact destinations
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
