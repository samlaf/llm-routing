"""Models a router can call, and a simulator that stands in for real ones."""

import random
from dataclasses import dataclass
from typing import Protocol

import numpy as np
from sklearn.cluster import KMeans

from routing.tasks import Task

COSTS = {"small": 0.25, "medium": 0.5, "frontier": 1.0}

# Each tier has a different best model, so routing pays off only if the
# router can tell tiers apart:
# - easy: small is nearly as good as frontier.
# - medium: medium closes most of the gap.
# - hard: only frontier does well.
# - hopeless: nothing beats a coin flip by much, so frontier is wasted.
PASS_RATES = {
    "easy": {"small": 0.95, "medium": 0.97, "frontier": 0.98},
    "medium": {"small": 0.60, "medium": 0.92, "frontier": 0.95},
    "hard": {"small": 0.52, "medium": 0.60, "frontier": 0.92},
    "hopeless": {"small": 0.50, "medium": 0.52, "frontier": 0.55},
}
# Sending every tier to its best model costs $51.25 per 100 tasks, just
# over the $50 budget, so the router must also trade tiers off.
TIER_SHARES = {"easy": 0.30, "medium": 0.30, "hard": 0.25, "hopeless": 0.15}


class Model(Protocol):
    name: str
    cost: float

    def answer(self, task: Task) -> bool: ...


@dataclass
class SimulatedModel:
    name: str
    cost: float
    pass_rate: dict[str, float]
    truth: dict[str, bool]
    rng: random.Random

    def p_correct(self, task_id: str) -> float:
        return self.pass_rate[task_id]

    def answer(self, task: Task) -> bool:
        truth = self.truth[task.id]
        return truth if self.rng.random() < self.p_correct(task.id) else not truth


def hidden_tiers(
    tasks: list[Task],
    features: dict[str, np.ndarray],
    rng: random.Random,
    n_topics: int = 10,
    topic_weight: float = 0.5,
) -> dict[str, str]:
    """Assign each task a tier, in the proportions of TIER_SHARES.

    Tasks are clustered into topics by embedding, and each topic gets a
    random difficulty. Tasks are ranked by a score that is part topic
    difficulty, part noise. The topic part is what a router can learn from
    the embeddings. The noise part is what no router can see.
    """
    vectors = np.stack([features[t.id] for t in tasks])
    n_topics = min(n_topics, len(tasks))
    topics = KMeans(n_topics, random_state=rng.getrandbits(32)).fit_predict(vectors)
    topic_difficulty = [rng.random() for _ in range(n_topics)]
    score = {
        t.id: topic_weight * topic_difficulty[k] + (1 - topic_weight) * rng.random()
        for t, k in zip(tasks, topics)
    }
    ranked = sorted(tasks, key=lambda t: score[t.id])

    tiers, start = {}, 0.0
    for tier, share in TIER_SHARES.items():
        end = start + share * len(tasks)
        for t in ranked[round(start) : round(end)]:
            tiers[t.id] = tier
        start = end
    return tiers


def simulated_models(
    tasks: list[Task],
    truth: dict[str, bool],
    features: dict[str, np.ndarray],
    seed: int,
) -> dict[str, SimulatedModel]:
    rng = random.Random(seed)
    tiers = hidden_tiers(tasks, features, rng)
    return {
        name: SimulatedModel(
            name,
            COSTS[name],
            {task_id: PASS_RATES[tier][name] for task_id, tier in tiers.items()},
            truth,
            random.Random(rng.getrandbits(64)),
        )
        for name in COSTS
    }
