import itertools
import random

import numpy as np
import pytest

from routing.budget import Budget
from routing.episode import run_episode
from routing.models import Attempt, mean_costs, pass_rates, replay_models
from routing.oracles import best_mix, oracle_plan, text_estimates
from routing.routers import ClusterRouter, FixedRouter, MixRouter, PlanRouter
from routing.tasks import Task, Verifier

MODELS = {"small": 0.01, "medium": 0.2, "frontier": 0.5}


def synthetic(n_tasks: int, seed: int = 0):
    """Tasks with random pass rates, a few recorded attempts each, and features."""
    rng = random.Random(seed)
    tasks = [Task(f"t{i}", "spec") for i in range(n_tasks)]
    attempts = []
    for t in tasks:
        for m, base in MODELS.items():
            for s in range(3):
                code = f"{t.id}-{m}-{s}"
                cost = base * rng.uniform(0.5, 1.5)
                attempts.append(Attempt(t.id, m, code, rng.random() < 0.3 + base, cost))
    vectors = np.random.default_rng(seed).normal(size=(n_tasks, 8))
    features = {t.id: v for t, v in zip(tasks, vectors)}
    return tasks, attempts, features


def setup(n_tasks: int = 30):
    tasks, attempts, features = synthetic(n_tasks)
    c = mean_costs(attempts)
    caps = {m: max(a.cost for a in attempts if a.model == m) for m in MODELS}
    avg_cost = {m: float(np.mean(list(c[m].values()))) for m in MODELS}
    dollars = sum(c["medium"].values())
    verifier = Verifier(known={(a.task, a.code): a.passed for a in attempts})
    return tasks, attempts, features, caps, avg_cost, dollars, verifier


def test_oracle_plan_matches_brute_force():
    tasks, attempts, _ = synthetic(6)
    p, c = pass_rates(attempts), mean_costs(attempts)
    dollars = sum(c["medium"].values())

    def total(assignment, table):
        return sum(table[m][t.id] for t, m in zip(tasks, assignment))

    best = max(
        total(a, p)
        for a in itertools.product(MODELS, repeat=len(tasks))
        if total(a, c) <= dollars
    )
    plan = [oracle_plan(tasks, p, c, dollars)[t.id] for t in tasks]
    assert total(plan, c) <= dollars
    # Costs round up to whole budget steps, so the plan can fall just short.
    assert total(plan, p) == pytest.approx(best, abs=0.05)


def test_best_mix_spends_budget_on_two_models():
    shares = best_mix(
        {"small": 0.5, "medium": 0.8, "frontier": 0.9},
        {"small": 0.0, "medium": 1.0, "frontier": 2.0},
        per_task=1.5,
    )
    assert shares == pytest.approx({"medium": 0.5, "frontier": 0.5})


def test_text_estimates_never_use_the_task_itself():
    tasks = [Task(f"t{i}", "spec") for i in range(3)]
    features = {"t0": np.array([1.0, 0]), "t1": np.array([1.0, 0.1]), "t2": np.array([0, 1.0])}
    table = {"small": {"t0": 1.0, "t1": 0.0, "t2": 0.5}}
    estimates = text_estimates(tasks, features, table, k=1)
    assert estimates["small"]["t0"] == 0.0
    assert estimates["small"]["t1"] == 1.0


@pytest.mark.parametrize(
    "make",
    [
        lambda f, cost, plan: FixedRouter("frontier", cost),
        lambda f, cost, plan: MixRouter({"small": 0.5, "frontier": 0.5}, cost, seed=0),
        lambda f, cost, plan: PlanRouter(plan, cost),
        lambda f, cost, plan: ClusterRouter(f, cost, n_topics=3),
    ],
    ids=["fixed", "mix", "plan", "cluster"],
)
def test_router_calls_every_task_within_budget(make):
    tasks, attempts, features, caps, avg_cost, dollars, verifier = setup()
    plan = {t.id: "frontier" for t in tasks}
    budget = Budget(dollars, len(tasks), caps)
    result = run_episode(
        tasks, replay_models(attempts, 0), make(features, avg_cost, plan), verifier, budget
    )
    assert result.calls.total() == len(tasks)
    assert result.spent <= dollars


def test_frontier_first_steps_down_when_budget_runs_low():
    tasks, attempts, _, caps, avg_cost, dollars, verifier = setup()
    budget = Budget(dollars, len(tasks), caps)
    result = run_episode(
        tasks, replay_models(attempts, 0), FixedRouter("frontier", avg_cost), verifier, budget
    )
    assert 0 < result.calls["frontier"] < len(tasks)
