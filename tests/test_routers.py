import itertools

import numpy as np
import pytest

from routing.episode import run_episode
from routing.features import embed
from routing.models import simulated_models
from routing.routers import FixedRouter, OracleRouter, oracle_plan
from routing.tasks import Task, Verifier, load_boolq


def test_boolq_sample_loads():
    tasks, truth = load_boolq()
    assert len(tasks) == 100
    assert set(truth.values()) == {True, False}


@pytest.mark.parametrize("model", ["small", "medium", "frontier"])
def test_fixed_router_calls_every_task_within_budget(model):
    tasks, truth = load_boolq()
    models = simulated_models(tasks, truth, embed(tasks), seed=0)
    result = run_episode(tasks, models, FixedRouter(model), Verifier(truth), 50.0)
    assert result.calls.total() == len(tasks)
    assert result.spent <= 50.0


def test_frontier_first_steps_down_when_budget_runs_low():
    tasks, truth = load_boolq()
    models = simulated_models(tasks, truth, embed(tasks), seed=0)
    result = run_episode(tasks, models, FixedRouter("frontier"), Verifier(truth), 50.0)
    assert result.calls["frontier"] == 33
    assert result.spent == 50.0


def test_oracle_plan_matches_brute_force():
    tasks = [Task(f"t{i}", "q", "p") for i in range(6)]
    truth = {t.id: True for t in tasks}
    rng = np.random.default_rng(0)
    features = {t.id: rng.normal(size=8) for t in tasks}
    models = simulated_models(tasks, truth, features, seed=3)
    dollars = 3.0

    def expected(assignment):
        return sum(models[m].p_correct(t.id) for t, m in zip(tasks, assignment))

    feasible = (
        a
        for a in itertools.product(models, repeat=len(tasks))
        if sum(models[m].cost for m in a) <= dollars
    )
    best = max(expected(a) for a in feasible)

    plan = oracle_plan(tasks, models, dollars)
    assert sum(models[m].cost for m in plan.values()) <= dollars
    assert expected([plan[t.id] for t in tasks]) == pytest.approx(best)


def test_oracle_spends_within_budget_on_full_stream():
    tasks, truth = load_boolq()
    models = simulated_models(tasks, truth, embed(tasks), seed=0)
    router = OracleRouter(oracle_plan(tasks, models, 50.0))
    result = run_episode(tasks, models, router, Verifier(truth), 50.0)
    assert result.calls.total() == len(tasks)
    assert result.spent <= 50.0
