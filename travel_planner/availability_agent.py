"""
Availability agent — re-checks live prices and availability for all trip
components before the user commits to booking.

Returns a status dict shaped like:
{
  "overall": "all_clear | some_changes | major_issues",
  "flight":  {"flag": "ok|warning|error", "status": "...", "note": "..."},
  "train":   {"flag": "ok|warning|error", "status": "...", "note": "..."},
  "vehicle": {"flag": "ok|warning|error", "status": "...", "note": "..."},
  "hotels":  {"CityName": {"flag": "...", "status": "...", "note": "..."}, ...},
}
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from .llm import create_completion, parse_json
from .models import TripContext
from .search import search as tavily_search

_SCHEMA = """{
  "overall": "all_clear | some_changes | major_issues",
  "flight": {
    "flag": "ok | warning | error",
    "status": "one short phrase e.g. Available as planned",
    "note": "1–2 sentences on current prices / availability / caveats"
  },
  "train": {
    "flag": "ok | warning | error",
    "status": "one short phrase",
    "note": "1–2 sentences"
  },
  "vehicle": {
    "flag": "ok | warning | error",
    "status": "one short phrase",
    "note": "1–2 sentences"
  },
  "hotels": {
    "CityName": {
      "flag": "ok | warning | error",
      "status": "one short phrase",
      "note": "1–2 sentences"
    }
  }
}"""


def check(
    ctx: TripContext,
    transport: dict,
    hotels_by_location: dict,
) -> dict:
    dest     = ctx.destination or "India"
    starting = ctx.starting_city or "India"
    month    = ctx.travel_month or "travel season"
    n        = ctx.num_travelers or 2
    duration = ctx.duration_days or 5

    flight_opts  = transport.get("flight",  {}).get("options", [])
    train_opts   = transport.get("train",   {}).get("options", [])
    vehicle_opts = transport.get("vehicle", {}).get("options", [])
    hotel_cities = list(hotels_by_location.keys())[:3]

    best_flight  = flight_opts[0]  if flight_opts  else {}
    best_train   = train_opts[0]   if train_opts   else {}
    best_vehicle = vehicle_opts[0] if vehicle_opts else {}

    # ── Build targeted search queries ────────────────────────────────────────
    airline = best_flight.get("airlines", "flights")
    train_name = f'{best_train.get("name","")} {best_train.get("number","")}'.strip() or "train"
    vehicle_type = best_vehicle.get("vehicle_type", "car rental")

    searches: dict = {
        "flight": (
            f"{airline} {starting} to {dest} flight availability price {month}"
        ),
        "train": (
            f"{train_name} {starting} {dest} IRCTC availability {month}"
        ),
        "vehicle": (
            f"{vehicle_type} {dest} {month} self-drive hire availability"
        ),
    }
    for city in hotel_cities:
        searches[f"hotel__{city}"] = (
            f"hotel availability {city} India {month} {n} guests {duration} nights"
        )

    # ── Parallel Tavily searches ─────────────────────────────────────────────
    snippets: dict = {}
    with ThreadPoolExecutor(max_workers=len(searches)) as pool:
        fmap = {pool.submit(tavily_search, q, 3, False): key for key, q in searches.items()}
        for fut in as_completed(fmap):
            key = fmap[fut]
            try:
                res = fut.result()
                snippets[key] = "\n".join(
                    f"[{r['title']}] {r['content'][:300]}" for r in res["results"]
                )
            except Exception:
                snippets[key] = "(no data)"

    # ── Build reference summary of original options ──────────────────────────
    original_lines = []
    if best_flight:
        original_lines.append(
            f"Flight: {best_flight.get('airlines','')} {best_flight.get('route','')} "
            f"— {best_flight.get('cost_per_person','?')}/person"
        )
    if best_train:
        original_lines.append(
            f"Train: {best_train.get('name','')} {best_train.get('number','')} "
            f"— Sleeper {best_train.get('sleeper','?')}, 3AC {best_train.get('third_ac','?')}"
        )
    if best_vehicle:
        original_lines.append(
            f"Vehicle: {best_vehicle.get('vehicle_type','')} — {best_vehicle.get('total_estimate','?')}"
        )
    for city in hotel_cities:
        city_hotels = hotels_by_location.get(city, [])
        if city_hotels:
            h = city_hotels[0]
            original_lines.append(
                f"Hotel {city}: {h.get('name','')} ({h.get('type','')}) "
                f"— {h.get('price_per_night','?')}/night"
            )

    search_block = "\n\n".join(
        f"### Search: {k.replace('__', ' — ').replace('_', ' ')}\n{v}"
        for k, v in snippets.items()
    )

    system = (
        f"You are a travel availability checker. A user planned a trip from {starting} to "
        f"{dest} in {month} for {n} traveler(s) over {duration} days.\n\n"
        f"Originally suggested options:\n" + "\n".join(original_lines) + "\n\n"
        f"Based on the live search results below, assess whether each component is still "
        f"available and at what price. Flag any issues that could prevent booking.\n\n"
        f"Rules:\n"
        f"- 'ok' flag: option appears available at similar price\n"
        f"- 'warning' flag: prices may have changed significantly or limited seats/rooms\n"
        f"- 'error' flag: appears unavailable or route/hotel no longer operating\n"
        f"- 'overall' is 'all_clear' if no errors and warnings ≤1, else 'some_changes' or 'major_issues'\n\n"
        f"Return exactly this JSON:\n{_SCHEMA}"
    )

    response = create_completion(
        max_tokens=900,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": f"Live search results:\n\n{search_block}\n\nReturn the JSON now."},
        ],
    )
    result = parse_json(response.choices[0].message.content) or {
        "overall": "some_changes",
        "flight":  {"flag": "warning", "status": "Could not verify",  "note": "Please check manually."},
        "train":   {"flag": "warning", "status": "Could not verify",  "note": "Please check manually."},
        "vehicle": {"flag": "warning", "status": "Could not verify",  "note": "Please check manually."},
        "hotels":  {c: {"flag": "warning", "status": "Could not verify", "note": "Please check manually."} for c in hotel_cities},
    }
    return result
