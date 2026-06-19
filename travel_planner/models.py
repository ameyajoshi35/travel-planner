from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class TripContext:
    # Hard requirements (planning blocked without these)
    travel_dates: Optional[str] = None
    duration_days: Optional[int] = None
    travel_month: Optional[str] = None
    starting_city: Optional[str] = None
    num_travelers: Optional[int] = None
    budget_total: Optional[int] = None  # in INR

    # Who is traveling
    traveler_type: Optional[str] = None  # solo / couple / family / friends
    has_kids: Optional[bool] = None
    kids_ages: Optional[List[int]] = None
    has_elderly: Optional[bool] = None

    # Preferences (soft)
    destination: Optional[str] = None  # None = unknown, agent will suggest
    experience_type: List[str] = field(default_factory=list)
    travel_mode: Optional[str] = None  # train / flight / road / mixed
    constraints: List[str] = field(default_factory=list)

    # Internal state
    is_confirmed: bool = False

    def is_complete(self) -> bool:
        dates_ok = self.travel_dates is not None or (
            self.duration_days is not None and self.travel_month is not None
        )
        return (
            dates_ok
            and self.starting_city is not None
            and self.num_travelers is not None
            and self.budget_total is not None
            and self.traveler_type is not None
        )

    def missing_fields(self) -> List[str]:
        missing = []
        if self.travel_dates is None and not (
            self.duration_days is not None and self.travel_month is not None
        ):
            missing.append("travel_dates (or duration + month)")
        if self.starting_city is None:
            missing.append("starting_city")
        if self.num_travelers is None:
            missing.append("num_travelers")
        if self.budget_total is None:
            missing.append("budget_total")
        if self.traveler_type is None:
            missing.append("traveler_type")
        return missing

    def update(self, data: dict) -> None:
        for key, value in data.items():
            if not hasattr(self, key):
                continue
            if value is None:
                continue
            # Don't overwrite list fields with empty lists
            if isinstance(value, list) and len(value) == 0:
                continue
            setattr(self, key, value)

    def to_json(self) -> str:
        return json.dumps(
            {
                "travel_dates": self.travel_dates,
                "duration_days": self.duration_days,
                "travel_month": self.travel_month,
                "starting_city": self.starting_city,
                "num_travelers": self.num_travelers,
                "budget_total": self.budget_total,
                "traveler_type": self.traveler_type,
                "has_kids": self.has_kids,
                "kids_ages": self.kids_ages,
                "has_elderly": self.has_elderly,
                "destination": self.destination,
                "experience_type": self.experience_type,
                "travel_mode": self.travel_mode,
                "constraints": self.constraints,
                "is_confirmed": self.is_confirmed,
            },
            indent=2,
        )
