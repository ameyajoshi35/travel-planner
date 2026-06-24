"""
Output validation (SPEC §3/§4).

Every LLM payload is coerced into a model here before it reaches the
orchestrator or the render layer. Validation does three jobs:

  1. Guarantees a stable shape, so downstream code stops defensive `.get()`-ing.
  2. Strips unknown / hostile keys the model may have been tricked into adding
     (extra="ignore").
  3. Coerces loose types (e.g. "15000" -> 15000) and fills safe defaults.

Each `validate_*` helper returns a **plain dict** (or None on unrecoverable
failure) so the existing agent/render interfaces are unchanged — the only
difference is that what flows through is now schema-clean.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


class _Base(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


# ── Planner / Suggester ──────────────────────────────────────────────────────

class Destination(_Base):
    name: str
    tagline: str = ""
    description: str = ""
    history: str = ""
    unique_facts: List[str] = Field(default_factory=list)
    fun_activities: List[str] = Field(default_factory=list)
    highlights: List[str] = Field(default_factory=list)
    estimated_cost: Optional[str] = None

    @field_validator("name")
    @classmethod
    def _name_nonempty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("destination name required")
        return v


class ItineraryDay(_Base):
    day: int = 0
    title: str = ""
    location: str = ""
    fun_highlight: str = ""
    morning: str = ""
    afternoon: str = ""
    evening: str = ""
    stay: str = ""
    activities: List[str] = Field(default_factory=list)


class BudgetBreakdown(_Base):
    transport: float = 0
    accommodation: float = 0
    food: float = 0
    activities: float = 0


class Plan(_Base):
    trip_title: str = "Your India Adventure"
    overview: str = ""
    destinations: List[Destination] = Field(default_factory=list)
    itinerary: List[ItineraryDay] = Field(default_factory=list)
    budget: BudgetBreakdown = Field(default_factory=BudgetBreakdown)
    tips: List[str] = Field(default_factory=list)


# ── Transport ─────────────────────────────────────────────────────────────────
# Option shapes differ per mode (flight/train/vehicle) and the render layer
# iterates over whatever string fields are present, so options are validated as
# string->string maps: hostile non-string values are dropped, shape is free.

class TransportResult(_Base):
    options: List[Dict[str, str]] = Field(default_factory=list)

    @field_validator("options", mode="before")
    @classmethod
    def _coerce_options(cls, v):
        if not isinstance(v, list):
            return []
        cleaned = []
        for opt in v:
            if isinstance(opt, dict):
                cleaned.append({str(k): str(val) for k, val in opt.items() if val is not None})
        return cleaned


# ── Hotels ────────────────────────────────────────────────────────────────────

class HotelOption(_Base):
    name: str = ""
    type: str = ""
    price_per_night: str = ""
    rating: str = ""
    why_pick: str = ""

    @field_validator("rating", "price_per_night", mode="before")
    @classmethod
    def _stringify(cls, v):
        return "" if v is None else str(v)


class HotelsResult(_Base):
    hotels_by_location: Dict[str, List[HotelOption]] = Field(default_factory=dict)


# ── Suggester cards ────────────────────────────────────────────────────────────

class SuggestionCard(_Base):
    name: str
    tagline: str = ""
    description: str = ""
    highlights: List[str] = Field(default_factory=list)
    best_for: str = ""
    approx_cost_per_person: str = ""
    budget_fit: str = ""
    weather_in_month: str = ""
    travel_time_from_origin: str = ""


class SuggesterResult(_Base):
    destinations: List[SuggestionCard] = Field(default_factory=list)


# ── Availability ────────────────────────────────────────────────────────────────

class AvailabilityComponent(_Base):
    flag: str = "warning"
    status: str = ""
    note: str = ""

    @field_validator("flag")
    @classmethod
    def _valid_flag(cls, v: str) -> str:
        return v if v in {"ok", "warning", "error"} else "warning"


class AvailabilityReport(_Base):
    overall: str = "some_changes"
    flight: AvailabilityComponent = Field(default_factory=AvailabilityComponent)
    train: AvailabilityComponent = Field(default_factory=AvailabilityComponent)
    vehicle: AvailabilityComponent = Field(default_factory=AvailabilityComponent)
    hotels: Dict[str, AvailabilityComponent] = Field(default_factory=dict)


# ── Public validators (return clean dict or None) ────────────────────────────

def _run(model_cls, data: Optional[dict]):
    if not isinstance(data, dict):
        return None
    try:
        return model_cls.model_validate(data).model_dump()
    except ValidationError:
        return None


def validate_plan(data):           return _run(Plan, data)
def validate_transport(data):      return _run(TransportResult, data)
def validate_hotels(data):         return _run(HotelsResult, data)
def validate_suggester(data):      return _run(SuggesterResult, data)
def validate_availability(data):   return _run(AvailabilityReport, data)
