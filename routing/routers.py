"""The router interface, baselines, the learning router, and routers that follow a plan."""

import random
from typing import Protocol

import numpy as np
from sklearn.cluster import KMeans

from routing.budget import Budget
from routing.tasks import Task


class Router(Protocol):
    def choose(self, task: Task, budget: Budget) -> str: ...

    def update(self, task: Task, model: str, passed: bool) -> None: ...


def step_down(model: str, costs: dict[str, float], budget: Budget) -> str:
    """`model` if the budget allows it, else the dearest cheaper model it allows."""
    ladder = sorted(
        (name for name, cost in costs.items() if cost <= costs[model]),
        key=lambda name: -costs[name],
    )
    return next(m for m in ladder if budget.can_afford(m))


class FixedRouter:
    """Always picks one model, stepping down once the budget can't afford it."""

    def __init__(self, model: str, costs: dict[str, float]):
        self.model = model
        self.costs = costs

    def choose(self, task: Task, budget: Budget) -> str:
        return step_down(self.model, self.costs, budget)

    def update(self, task: Task, model: str, passed: bool) -> None:
        pass


class MixRouter:
    """Draws each task's model from fixed shares, ignoring the task itself."""

    def __init__(self, shares: dict[str, float], costs: dict[str, float], seed: int):
        self.shares = shares
        self.costs = costs
        self.rng = random.Random(seed)

    def choose(self, task: Task, budget: Budget) -> str:
        model = self.rng.choices(list(self.shares), weights=list(self.shares.values()))[0]
        return step_down(model, self.costs, budget)

    def update(self, task: Task, model: str, passed: bool) -> None:
        pass


class PlanRouter:
    """Follows a plan made in advance, stepping down when costs run over.

    The oracles make plans from knowledge no deployed router has, so these are
    reference levels to measure against, not routers we could deploy.
    """

    def __init__(self, plan: dict[str, str], costs: dict[str, float]):
        self.plan = plan
        self.costs = costs

    def choose(self, task: Task, budget: Budget) -> str:
        return step_down(self.plan[task.id], self.costs, budget)

    def update(self, task: Task, model: str, passed: bool) -> None:
        pass


class ClusterRouter:
    """Learns pass rates per (topic, model) and prices each dollar at λ.

    - Memory: k-means topics over the embeddings, with a Beta scoreboard per
      (topic, model), shrunk toward that model's overall pass rate.
    - Exploration: Thompson sampling from those Betas.
    - Allocator: argmax p̃ − λ·cost, with λ paced so spend tracks the budget.

    Topics are fitted on the text of every task up front. That uses future
    tasks' text, never their results.
    """

    def __init__(
        self,
        features: dict[str, np.ndarray],
        costs: dict[str, float],
        n_topics: int = 8,
        prior_strength: float = 2.0,
        lam: float = 0.5,
        step: float = 0.1,
        seed: int = 0,
    ):
        ids = list(features)
        topics = KMeans(n_topics, random_state=seed).fit_predict(
            np.stack([features[i] for i in ids])
        )
        self.topic = dict(zip(ids, topics))
        self.models = list(costs)
        self.cost = np.array([costs[m] for m in self.models])
        self.passes = np.zeros((n_topics, len(self.models)))
        self.tries = np.zeros((n_topics, len(self.models)))
        self.prior_strength = prior_strength
        self.lam = lam
        self.step = step
        self.per_task: float | None = None
        self.rng = np.random.default_rng(seed)

    def choose(self, task: Task, budget: Budget) -> str:
        if self.per_task is None:
            self.per_task = budget.dollars / budget.tasks_left
        # Costs in units of the budget per task, so λ is unitless.
        cost = self.cost / self.per_task
        k = self.topic[task.id]
        overall = (1 + self.passes.sum(0)) / (2 + self.tries.sum(0))
        alpha = self.prior_strength * overall + self.passes[k]
        beta = self.prior_strength * (1 - overall) + self.tries[k] - self.passes[k]
        score = self.rng.beta(alpha, beta) - self.lam * cost
        score[[not budget.can_afford(m) for m in self.models]] = -np.inf
        i = int(np.argmax(score))
        self.lam = max(0.0, self.lam + self.step * (cost[i] - 1))
        return self.models[i]

    def update(self, task: Task, model: str, passed: bool) -> None:
        k, i = self.topic[task.id], self.models.index(model)
        self.tries[k, i] += 1
        self.passes[k, i] += passed
