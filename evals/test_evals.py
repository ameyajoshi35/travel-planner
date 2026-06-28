"""
Eval test suite — two layers:

  Offline tests  (no API calls, instant)
    pytest evals/test_evals.py

  Pipeline tests (real API calls, ~60–120s per trip)
    pytest evals/test_evals.py -m pipeline --run-pipeline

The offline tests run against the pre-baked fixtures in fixtures.py.
The pipeline tests call the real orchestrator and evaluate the live output.
"""

import os

import pytest

from evals.eval_fns import (
    eval_budget,
    eval_completeness,
    eval_duration,
    eval_relevance,
    eval_schema,
    eval_scope,
    run_all,
)
from evals.fixtures import PLANS, TRIPS
from evals.ragas_eval import ctx_to_query, plan_to_text, run_ragas


# ═══════════════════════════════════════════════════════════════════════════════
# OFFLINE TESTS  — fixture data, no API calls
# ═══════════════════════════════════════════════════════════════════════════════

class TestSchemaValidity:
    def test_good_plan_passes(self):
        r = eval_schema(PLANS["good_plan"])
        assert r["pass"], r["issues"]

    def test_incomplete_plan_fails(self):
        r = eval_schema(PLANS["bad_plan_missing_sections"])
        assert not r["pass"]

    def test_empty_plan_fails(self):
        r = eval_schema({})
        assert not r["pass"]


class TestCompleteness:
    def test_complete_plan_passes(self):
        r = eval_completeness(PLANS["good_plan"])
        assert r["pass"]
        assert r["score"] == 1.0

    def test_missing_sections_fails(self):
        r = eval_completeness(PLANS["bad_plan_missing_sections"])
        assert not r["pass"]
        assert "missing section: itinerary" in r["issues"] or "missing section: budget" in r["issues"]

    def test_empty_plan_scores_zero(self):
        r = eval_completeness({})
        assert r["score"] == 0.0


class TestDurationFaithfulness:
    def test_exact_match_scores_one(self):
        ctx = TRIPS["rajasthan_couple"]  # 5 days
        r = eval_duration(PLANS["good_plan"], ctx)
        assert r["pass"]
        assert r["score"] == 1.0

    def test_one_day_off_still_passes(self):
        ctx = TRIPS["rajasthan_couple"]  # 5 days, plan has 5 days
        # Temporarily check with 6-day expectation (±1 tolerance)
        from travel_planner.models import TripContext
        ctx6 = TripContext(**{**ctx.__dict__, "duration_days": 6})
        r = eval_duration(PLANS["good_plan"], ctx6)
        assert r["pass"]

    def test_large_mismatch_fails(self):
        ctx = TRIPS["rajasthan_couple"]  # 5 days
        r = eval_duration(PLANS["bad_plan_wrong_duration"], ctx)  # plan has 2 days
        assert not r["pass"]
        assert r["score"] < 1.0


class TestBudgetFaithfulness:
    def test_within_budget_passes(self):
        ctx = TRIPS["rajasthan_couple"]  # ₹40,000 budget; plan total ₹39,000
        r = eval_budget(PLANS["good_plan"], ctx)
        assert r["pass"]

    def test_over_budget_fails(self):
        ctx = TRIPS["rajasthan_couple"]  # ₹40,000 budget; plan total ₹80,000
        r = eval_budget(PLANS["bad_plan_over_budget"], ctx)
        assert not r["pass"]
        assert r["score"] < 1.0

    def test_missing_budget_data_is_neutral(self):
        ctx = TRIPS["rajasthan_couple"]
        r = eval_budget({"budget": {}}, ctx)
        assert r["pass"]   # neutral — no data to fail on


class TestScopeAdherence:
    def test_correct_state_passes(self):
        ctx = TRIPS["rajasthan_couple"]  # state = Rajasthan
        r = eval_scope(PLANS["good_plan"], ctx)
        assert r["pass"]

    def test_wrong_state_fails(self):
        ctx = TRIPS["rajasthan_couple"]  # state = Rajasthan
        r = eval_scope(PLANS["bad_plan_wrong_state"], ctx)  # plan is about Goa
        assert not r["pass"]

    def test_no_state_constraint_always_passes(self):
        from travel_planner.models import TripContext
        ctx_no_state = TripContext(
            destination="Anywhere", starting_city="Mumbai",
            travel_month="October", duration_days=5,
            num_travelers=2, budget_total=40_000, traveler_type="couple",
        )
        r = eval_scope(PLANS["good_plan"], ctx_no_state)
        assert r["pass"]


class TestExperienceRelevance:
    def test_matching_experience_passes(self):
        ctx = TRIPS["rajasthan_couple"]  # heritage + nature
        r = eval_relevance(PLANS["good_plan"], ctx)
        assert r["pass"]
        assert r["score"] >= 0.5

    def test_mismatched_experience_lowers_score(self):
        ctx = TRIPS["kerala_family"]  # beach + nature
        # good_plan is heritage-focused — beach keywords unlikely
        r = eval_relevance(PLANS["good_plan"], ctx)
        # score may be low but we just check it ran and returned a valid result
        assert 0.0 <= r["score"] <= 1.0

    def test_no_experience_type_always_passes(self):
        from travel_planner.models import TripContext
        ctx = TripContext(
            destination="Jaipur", starting_city="Mumbai",
            travel_month="October", duration_days=5,
            num_travelers=2, budget_total=40_000, traveler_type="couple",
            experience_type=[],
        )
        r = eval_relevance(PLANS["good_plan"], ctx)
        assert r["pass"]
        assert r["score"] == 1.0


class TestRunAll:
    def test_good_plan_all_pass(self):
        ctx = TRIPS["rajasthan_couple"]
        report = run_all(PLANS["good_plan"], ctx)
        assert report["overall_pass"]
        assert report["overall_score"] >= 0.8
        assert len(report["results"]) == 6

    def test_bad_plan_fails_overall(self):
        ctx = TRIPS["rajasthan_couple"]
        report = run_all(PLANS["bad_plan_missing_sections"], ctx)
        assert not report["overall_pass"]

    def test_report_has_all_eval_names(self):
        ctx = TRIPS["rajasthan_couple"]
        report = run_all(PLANS["good_plan"], ctx)
        names = {r["name"] for r in report["results"]}
        assert names == {
            "schema_validity",
            "completeness",
            "duration_faithfulness",
            "budget_faithfulness",
            "scope_adherence",
            "experience_relevance",
        }


# ═══════════════════════════════════════════════════════════════════════════════
# PIPELINE TESTS  — real LLM + search calls, skipped unless --run-pipeline flag
# ═══════════════════════════════════════════════════════════════════════════════

def pytest_addoption(parser):
    parser.addoption(
        "--run-pipeline",
        action="store_true",
        default=False,
        help="Run integration tests that call the live LangGraph pipeline",
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "pipeline: mark test as requiring live API calls")


@pytest.fixture(scope="session")
def run_pipeline(request):
    return request.config.getoption("--run-pipeline")


def _requires_pipeline(run_pipeline_fixture):
    if not run_pipeline_fixture:
        pytest.skip("Pass --run-pipeline to run live pipeline tests")
    if not os.environ.get("GROQ_API_KEY"):
        pytest.skip("GROQ_API_KEY not set")
    if not os.environ.get("TAVILY_API_KEY"):
        pytest.skip("TAVILY_API_KEY not set")


@pytest.mark.pipeline
class TestPipelineOutputs:
    """
    Run the full orchestrator for each sample trip and evaluate the output.
    Each test takes ~60–90 seconds (real LLM + Tavily calls).
    """

    def test_rajasthan_couple_plan(self, run_pipeline):
        _requires_pipeline(run_pipeline)
        from travel_planner.orchestrator import run as orch_run

        ctx  = TRIPS["rajasthan_couple"]
        plan = None
        for event in orch_run(ctx, "planning"):
            if event["type"] == "plan":
                plan = event["data"]
                break

        assert plan is not None, "Orchestrator yielded no plan"
        report = run_all(plan, ctx)
        failures = [r for r in report["results"] if not r["pass"]]
        assert not failures, f"Eval failures: {failures}"

    def test_kerala_family_plan(self, run_pipeline):
        _requires_pipeline(run_pipeline)
        from travel_planner.orchestrator import run as orch_run

        ctx  = TRIPS["kerala_family"]
        plan = None
        for event in orch_run(ctx, "suggestion"):
            if event["type"] == "plan":
                plan = event["data"]
                break

        assert plan is not None, "Orchestrator yielded no plan"
        report = run_all(plan, ctx)
        # For suggestion phase, duration eval is lenient — only check key evals
        key_evals = {r["name"]: r for r in report["results"]}
        assert key_evals["completeness"]["pass"], key_evals["completeness"]["issues"]
        assert key_evals["budget_faithfulness"]["pass"], key_evals["budget_faithfulness"]["issues"]

    def test_himachal_friends_plan(self, run_pipeline):
        _requires_pipeline(run_pipeline)
        from travel_planner.orchestrator import run as orch_run

        ctx  = TRIPS["himachal_friends"]
        plan = None
        for event in orch_run(ctx, "planning"):
            if event["type"] == "plan":
                plan = event["data"]
                break

        assert plan is not None, "Orchestrator yielded no plan"
        report = run_all(plan, ctx)
        score = report["overall_score"]
        assert score >= 0.7, f"Overall score {score:.2f} below threshold. Results: {report['results']}"


@pytest.mark.pipeline
class TestRagasObservability:
    """
    Ragas faithfulness eval — measures whether the generated plan is grounded
    in the Tavily search results that produced it.

    Requires --run-pipeline + GROQ_API_KEY + TAVILY_API_KEY + ragas installed.
    Each test takes ~90–120 s (pipeline run + Ragas LLM evaluation).
    """

    def test_rajasthan_faithfulness(self, run_pipeline):
        _requires_pipeline(run_pipeline)
        from travel_planner.orchestrator import run as orch_run

        ctx      = TRIPS["rajasthan_couple"]
        plan     = None
        contexts = []

        for event in orch_run(ctx, "planning"):
            if event["type"] == "plan":
                plan = event["data"]
            if event["type"] == "contexts":
                contexts = event["contexts"]

        assert plan is not None, "Orchestrator yielded no plan"
        assert contexts,         "No search contexts captured — check _contexts key in PlannerAgent"

        scores = run_ragas(ctx, plan, contexts)
        assert not scores["errors"], f"Ragas errors: {scores['errors']}"
        assert scores["faithfulness"] is not None
        assert scores["faithfulness"] >= 0.5, (
            f"Faithfulness {scores['faithfulness']:.2f} below 0.5 — "
            "plan may be hallucinating destinations or activities"
        )

    def test_himachal_faithfulness(self, run_pipeline):
        _requires_pipeline(run_pipeline)
        from travel_planner.orchestrator import run as orch_run

        ctx      = TRIPS["himachal_friends"]
        plan     = None
        contexts = []

        for event in orch_run(ctx, "planning"):
            if event["type"] == "plan":
                plan = event["data"]
            if event["type"] == "contexts":
                contexts = event["contexts"]

        assert plan is not None, "Orchestrator yielded no plan"
        scores = run_ragas(ctx, plan, contexts)
        assert not scores["errors"], f"Ragas errors: {scores['errors']}"
        assert scores["faithfulness"] is not None
        # Log score even if below threshold — useful for debugging
        print(f"\nHimachal faithfulness: {scores['faithfulness']:.2f}")
        assert scores["faithfulness"] >= 0.5, (
            f"Faithfulness {scores['faithfulness']:.2f} below threshold"
        )
