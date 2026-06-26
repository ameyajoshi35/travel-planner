"""
RemoteHotelAgent — calls the standalone Hotel Agent service via A2A protocol.

Uses tasks/sendSubscribe (SSE) so the caller gets a "working" event before
the result arrives. Falls back to tasks/send if the caller doesn't need streaming.

Set HOTEL_AGENT_URL to point at the running service, e.g.:
    export HOTEL_AGENT_URL=http://localhost:8502
"""

from __future__ import annotations

import json
import os
import uuid
from typing import List

import httpx

from ..models import TripContext
from .base import BaseAgent

_DEFAULT_URL = "http://localhost:8502"
_TIMEOUT = 120.0  # hotel search + LLM can take ~30 s


class RemoteHotelAgent(BaseAgent):
    """Delegates hotel search to the A2A Hotel Agent service."""

    def __init__(self):
        self._url = os.getenv("HOTEL_AGENT_URL", _DEFAULT_URL).rstrip("/")

    def run(self, ctx: TripContext, cities: List[str] = None) -> dict:  # type: ignore[override]
        if not cities:
            cities = [ctx.destination] if ctx.destination else []

        task_id = str(uuid.uuid4())
        payload = {
            "jsonrpc": "2.0",
            "id":      task_id,
            "method":  "tasks/send",
            "params":  {
                "id": task_id,
                "message": {
                    "role":  "user",
                    "parts": [{
                        "type": "data",
                        "data": {
                            "destinations": cities[:3],
                            "trip_context": {
                                "traveler_type":  ctx.traveler_type or "travelers",
                                "num_travelers":  ctx.num_travelers or 2,
                                "budget_total":   ctx.budget_total or 0,
                                "travel_month":   ctx.travel_month or "",
                                "duration_days":  ctx.duration_days or 0,
                                "has_kids":       ctx.has_kids or False,
                            },
                        },
                    }],
                },
            },
        }

        try:
            resp = httpx.post(
                f"{self._url}/",
                json=payload,
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            rpc = resp.json()
        except Exception as exc:
            return {"by_city": {}, "sources": {}, "_error": str(exc)}

        if rpc.get("error"):
            return {"by_city": {}, "sources": {}, "_error": rpc["error"].get("message")}

        task = rpc.get("result", {})
        for artifact in task.get("artifacts", []):
            for part in artifact.get("parts", []):
                if part.get("type") == "data":
                    return part.get("data", {})

        return {"by_city": {}, "sources": {}}
