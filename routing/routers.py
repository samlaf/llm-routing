"""The router interface, baselines, and an oracle ceiling."""

from typing import Protocol

import numpy as np
from sklearn.cluster import KMeans

from routing.budget import Budget
from routing.models import COSTS, SimulatedModel
from routing.tasks import Task


class Router(Protocol):
    def choose(self, task: Task, budget: Budget) -> str: ...

    def update(self, task: Task, model: str, passed: bool) -> None: ...


class FixedRouter:
    """Always picks one model, and steps down to cheaper ones once it can't afford it."""

    def __init__(self, model: str, costs: dict[str, float] = COSTS):
        self.ladder = sorted(
            (name for name, cost in costs.items() if cost <= costs[model]),
            key=lambda name: -costs[name],
        )
        self.costs = costs

    def choose(self, task: Task, budget: Budget) -> str:
        return next(m for m in self.ladder if budget.can_afford(self.costs[m]))

    def update(self, task: Task, model: str, passed: bool) -> None:
        pass


class ClusterRouter:
    """Learns pass rates per (topic, model) and prices each dollar at λ.

    - Memory: k-means topics over the embeddings, with a Beta scoreboard per
      (topic, model), shrunk toward that model's global pass rate.
    - Exploration: Thompson sampling from those Betas.
    - Allocator: argmax p̃ − λ·cost, with λ paced so spend tracks the budget.

    Topics are fitted on the text of every task up front. That uses future
    questions' text, never their answers.
    """

    def __init__(
        self,
        features: dict[str, np.ndarray],
        costs: dict[str, float] = COSTS,
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
        self.target: float | None = None
        self.rng = np.random.default_rng(seed)

    def choose(self, task: Task, budget: Budget) -> str:
        if self.target is None:
            self.target = budget.dollars / budget.tasks_left
        k = self.topic[task.id]
        overall = (1 + self.passes.sum(0)) / (2 + self.tries.sum(0))
        alpha = self.prior_strength * overall + self.passes[k]
        beta = self.prior_strength * (1 - overall) + self.tries[k] - self.passes[k]
        score = self.rng.beta(alpha, beta) - self.lam * self.cost
        score[[not budget.can_afford(c) for c in self.cost]] = -np.inf
        i = int(np.argmax(score))
        self.lam = max(0.0, self.lam + self.step * (self.cost[i] - self.target))
        return self.models[i]

    def update(self, task: Task, model: str, passed: bool) -> None:
        k, i = self.topic[task.id], self.models.index(model)
        self.tries[k, i] += 1
        self.passes[k, i] += passed


class OracleRouter:
    """Follows the best offline plan for the true pass rates.

    Only the simulator knows those rates, so this is a ceiling to measure
    regret against, not a router we could deploy.
    """

    def __init__(self, plan: dict[str, str]):
        self.plan = plan

    def choose(self, task: Task, budget: Budget) -> str:
        return self.plan[task.id]

    def update(self, task: Task, model: str, passed: bool) -> None:
        pass


def oracle_plan(
    tasks: list[Task], models: dict[str, SimulatedModel], dollars: float
) -> dict[str, str]:
    """Pick one model per task to maximise expected passes within budget.

    Exact dynamic program over budget measured in units of the cheapest
    model's cost.
    """
    unit = min(m.cost for m in models.values())
    units = {name: round(m.cost / unit) for name, m in models.items()}
    capacity = round(dollars / unit)
    n = len(tasks)

    # best[i][b]: max expected passes on tasks[i:] with b units left.
    NEG = float("-inf")
    best = [[NEG] * (capacity + 1) for _ in range(n)] + [[0.0] * (capacity + 1)]
    choice: list[list[str | None]] = [[None] * (capacity + 1) for _ in range(n)]
    for i in range(n - 1, -1, -1):
        for b in range(capacity + 1):
            for name, model in models.items():
                left = b - units[name]
                if left < 0 or best[i + 1][left] == NEG:
                    continue
                value = model.p_correct(tasks[i].id) + best[i + 1][left]
                if value > best[i][b]:
                    best[i][b] = value
                    choice[i][b] = name

    plan, b = {}, capacity
    for i, task in enumerate(tasks):
        name = choice[i][b]
        if name is None:
            raise ValueError("budget too small to give every task a call")
        plan[task.id] = name
        b -= units[name]
    return plan
