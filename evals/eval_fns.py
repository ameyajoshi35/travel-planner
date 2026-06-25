"""
Eval functions — pure, deterministic, no LLM calls.

Each function takes a plan dict (and optionally a TripContext) and returns:
  {
    "score":  float,   # 0.0 – 1.0
    "pass":   bool,    # True if the eval criterion is met
    "issues": list[str],
  }

These can be composed into a full eval report via run_all().
"""

from typing import Any, Dict, List

from travel_planner.models import TripContext
from travel_planner.schemas import validate_plan


# ── Keywords used by the relevance eval ───────────────────────────────────────

_EXPERIENCE_KEYWORDS: Dict[str, List[str]] = {
    "heritage":  ["temple", "fort", "palace", "museum", "heritage", "history", "monument", "ancient", "haveli"],
    "nature":    ["forest", "wildlife", "national park", "trek", "waterfall", "mountain", "valley", "garden", "jungle"],
    "beach":     ["beach", "sea", "ocean", "coast", "backwater", "lagoon", "snorkel", "dive", "bay"],
    "adventure": ["trek", "climb", "rafting", "camping", "bungee", "zip", "adventure", "paragliding", "skiing"],
    "religious": ["temple", "church", "mosque", "shrine", "pilgrimage", "prayer", "festival", "puja", "mandir"],
    "offbeat":   ["offbeat", "hidden", "unexplored", "lesser", "local", "village", "rural", "secluded"],
}


# ── 1. Schema validity ────────────────────────────────────────────────────────

_REQUIRED_PLAN_KEYS = {"trip_title", "destinations", "itinerary", "budget", "tips"}


def eval_schema(plan: dict) -> dict:
    """
    Plan must (a) contain all five required top-level keys and (b) pass
    Pydantic type validation. Pydantic fills defaults for missing keys, so we
    check key presence on the raw dict first.
    """
    missing_keys = _REQUIRED_PLAN_KEYS - set(plan.keys())
    if missing_keys:
        return {
            "name":   "schema_validity",
            "score":  0.0,
            "pass":   False,
            "issues": [f"missing required key(s): {', '.join(sorted(missing_keys))}"],
        }
    result = validate_plan(plan)
    passed = result is not None
    return {
        "name":   "schema_validity",
        "score":  1.0 if passed else 0.0,
        "pass":   passed,
        "issues": [] if passed else ["failed Pydantic schema validation — missing or wrong-typed fields"],
    }


# ── 2. Completeness ───────────────────────────────────────────────────────────

def eval_completeness(plan: dict) -> dict:
    """
    Plan must have all five core sections: trip_title, destinations,
    itinerary, budget, and tips.
    """
    checks: Dict[str, Any] = {
        "trip_title":   bool(plan.get("trip_title")),
        "destinations": bool(plan.get("destinations")),
        "itinerary":    bool(plan.get("itinerary")),
        "budget":       bool(plan.get("budget")),
        "tips":         bool(plan.get("tips")),
    }
    issues   = [k for k, v in checks.items() if not v]
    score    = sum(checks.values()) / len(checks)
    return {
        "name":   "completeness",
        "score":  score,
        "pass":   score >= 0.8,   # allow 1 missing section
        "issues": [f"missing section: {k}" for k in issues],
    }


# ── 3. Duration faithfulness ──────────────────────────────────────────────────

def eval_duration(plan: dict, ctx: TripContext) -> dict:
    """
    Number of itinerary days should match ctx.duration_days (±1 day tolerance).
    """
    days      = len(plan.get("itinerary", []))
    requested = ctx.duration_days or 7
    diff      = abs(days - requested)
    passed    = diff <= 1
    score     = max(0.0, 1.0 - diff / requested)
    return {
        "name":   "duration_faithfulness",
        "score":  round(score, 2),
        "pass":   passed,
        "issues": [] if passed else [f"requested {requested} days, plan has {days} days"],
    }


# ── 4. Budget faithfulness ────────────────────────────────────────────────────

def eval_budget(plan: dict, ctx: TripContext) -> dict:
    """
    Estimated budget total should not exceed ctx.budget_total by more than 20%.
    """
    budget_data = plan.get("budget", {})
    total = sum(v for v in budget_data.values() if isinstance(v, (int, float)))

    if total == 0:
        return {
            "name":   "budget_faithfulness",
            "score":  0.5,
            "pass":   True,   # can't evaluate without data — neutral
            "issues": ["no numeric budget data found"],
        }

    ceiling = ctx.budget_total * 1.2
    passed  = total <= ceiling
    score   = min(1.0, ctx.budget_total / total) if total > 0 else 1.0
    return {
        "name":   "budget_faithfulness",
        "score":  round(score, 2),
        "pass":   passed,
        "issues": (
            [] if passed
            else [f"estimated ₹{int(total):,} exceeds budget ₹{ctx.budget_total:,} (ceiling ₹{int(ceiling):,})"]
        ),
    }


# ── 5. State / scope adherence ────────────────────────────────────────────────

def eval_scope(plan: dict, ctx: TripContext) -> dict:
    """
    The plan text (overview + destination descriptions) must mention the
    requested Indian state, confirming destinations are in the right region.
    """
    if not ctx.state:
        return {"name": "scope_adherence", "score": 1.0, "pass": True, "issues": []}

    state = ctx.state.lower()
    text  = " ".join([
        plan.get("overview", ""),
        plan.get("trip_title", ""),
        " ".join(
            d.get("description", "") + " " + d.get("name", "")
            for d in plan.get("destinations", [])
        ),
    ]).lower()

    passed = state in text
    return {
        "name":   "scope_adherence",
        "score":  1.0 if passed else 0.0,
        "pass":   passed,
        "issues": (
            [] if passed
            else [f"state '{ctx.state}' not referenced in plan — destinations may be off-scope"]
        ),
    }


# ── 6. Experience relevance ───────────────────────────────────────────────────

def eval_relevance(plan: dict, ctx: TripContext) -> dict:
    """
    The plan content (destinations + itinerary) should contain keywords that
    match at least half of the requested experience types.
    """
    if not ctx.experience_type:
        return {"name": "experience_relevance", "score": 1.0, "pass": True, "issues": []}

    full_text = " ".join([
        plan.get("overview", ""),
        " ".join(
            d.get("description", "") + " " + " ".join(d.get("highlights", []))
            for d in plan.get("destinations", [])
        ),
        " ".join(
            day.get("morning", "") + " " + day.get("afternoon", "") + " " + day.get("evening", "")
            for day in plan.get("itinerary", [])
        ),
    ]).lower()

    matched = [e for e in ctx.experience_type if any(kw in full_text for kw in _EXPERIENCE_KEYWORDS.get(e, [e]))]
    missed  = [e for e in ctx.experience_type if e not in matched]
    score   = len(matched) / len(ctx.experience_type)

    return {
        "name":   "experience_relevance",
        "score":  round(score, 2),
        "pass":   score >= 0.5,
        "issues": ([f"no content matching experience type(s): {', '.join(missed)}"] if missed else []),
    }


# ── Aggregate runner ──────────────────────────────────────────────────────────

def run_all(plan: dict, ctx: TripContext) -> dict:
    """
    Run all 6 evals and return a summary report.

    Returns:
        {
          "overall_pass": bool,
          "overall_score": float,      # mean of all scores
          "results": [eval_result, ...]
        }
    """
    results = [
        eval_schema(plan),
        eval_completeness(plan),
        eval_duration(plan, ctx),
        eval_budget(plan, ctx),
        eval_scope(plan, ctx),
        eval_relevance(plan, ctx),
    ]
    overall_score = sum(r["score"] for r in results) / len(results)
    overall_pass  = all(r["pass"] for r in results)
    return {
        "overall_pass":  overall_pass,
        "overall_score": round(overall_score, 3),
        "results":       results,
    }
