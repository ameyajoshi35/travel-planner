"""
Ragas observability layer for the travel planner pipeline.

Ragas treats the travel planner as a RAG system:
  user_input         — the natural-language trip request (derived from TripContext)
  retrieved_contexts — raw Tavily search snippets the planner used
  response           — the generated plan (converted to readable text)

Metric used
-----------
Faithfulness (LLM-only, no embeddings required)
  Measures what fraction of the claims in the response are supported by the
  retrieved contexts. A low score means the plan is hallucinating details that
  weren't in the search results.

Usage
-----
    from evals.ragas_eval import run_ragas
    scores = run_ragas(ctx, plan, contexts)
    # {"faithfulness": 0.87, "samples": 1, "errors": []}

Running the full pipeline and evaluating:
    pytest evals/test_evals.py -m pipeline --run-pipeline
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from travel_planner.models import TripContext


# ── Text helpers ──────────────────────────────────────────────────────────────

def ctx_to_query(ctx: TripContext) -> str:
    """Convert a TripContext into a natural-language trip request string."""
    parts = [f"Plan a {ctx.duration_days}-day trip"]
    if ctx.destination:
        parts.append(f"to {ctx.destination}")
    elif ctx.state:
        parts.append(f"in {ctx.state}, India")
    else:
        parts.append("in India")
    parts.append(f"departing from {ctx.starting_city}")
    parts.append(f"for {ctx.num_travelers} {ctx.traveler_type or 'travelers'}")
    parts.append(f"in {ctx.travel_month}")
    parts.append(f"with a total budget of ₹{ctx.budget_total:,}")
    if ctx.experience_type:
        parts.append(f"focusing on {', '.join(ctx.experience_type)}")
    if ctx.has_kids:
        parts.append("traveling with children")
    return " ".join(parts) + "."


def plan_to_text(plan: dict) -> str:
    """Flatten a plan dict into readable prose for Ragas evaluation."""
    lines: List[str] = []
    if plan.get("trip_title"):
        lines.append(f"Trip: {plan['trip_title']}")
    if plan.get("overview"):
        lines.append(f"Overview: {plan['overview']}")
    for dest in plan.get("destinations", []):
        desc = dest.get("description", "")
        lines.append(f"Destination: {dest.get('name', '')}. {desc}")
        if dest.get("highlights"):
            lines.append(f"Highlights: {', '.join(dest['highlights'])}")
    for day in plan.get("itinerary", []):
        lines.append(
            f"Day {day.get('day', '')}: "
            f"{day.get('morning', '')}. "
            f"{day.get('afternoon', '')}. "
            f"{day.get('evening', '')}."
        )
    budget = plan.get("budget", {})
    if budget:
        total = sum(v for v in budget.values() if isinstance(v, (int, float)))
        if total:
            lines.append(f"Estimated total budget: ₹{int(total):,}.")
    for tip in plan.get("tips", []):
        lines.append(f"Tip: {tip}")
    return "\n".join(lines)


# ── Ragas evaluation ──────────────────────────────────────────────────────────

def run_ragas(
    ctx: TripContext,
    plan: dict,
    contexts: List[str],
) -> Dict[str, Any]:
    """
    Run Ragas Faithfulness on a generated travel plan.

    Faithfulness = fraction of plan claims supported by the search contexts.
    Range: 0.0 (all hallucinated) → 1.0 (fully grounded).

    Returns:
        {
          "faithfulness": float | None,
          "samples":      int,
          "errors":       list[str],
        }
    """
    if not contexts:
        return {
            "faithfulness": None,
            "samples": 0,
            "errors": ["no search contexts — run the pipeline with --run-pipeline first"],
        }

    try:
        from ragas import evaluate
        from ragas.dataset_schema import EvaluationDataset, SingleTurnSample
        from ragas.llms import LangchainLLMWrapper
        from ragas.metrics import Faithfulness
        from langchain_groq import ChatGroq
    except ImportError as exc:
        return {
            "faithfulness": None,
            "samples": 0,
            "errors": [f"ragas not installed: {exc}. Run: pip install ragas"],
        }

    evaluator_llm = LangchainLLMWrapper(
        ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
    )

    sample = SingleTurnSample(
        user_input=ctx_to_query(ctx),
        retrieved_contexts=contexts,
        response=plan_to_text(plan),
    )
    dataset = EvaluationDataset(samples=[sample])

    try:
        result = evaluate(dataset, metrics=[Faithfulness(llm=evaluator_llm)])
        score = result["faithfulness"]
        return {
            "faithfulness": round(float(score), 3) if score is not None else None,
            "samples": len(dataset.samples),
            "errors": [],
        }
    except Exception as exc:
        return {
            "faithfulness": None,
            "samples": 1,
            "errors": [str(exc)],
        }
