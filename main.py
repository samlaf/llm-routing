import random
import statistics
from collections.abc import Callable

import numpy as np

from routing.episode import run_episode
from routing.features import embed
from routing.models import SimulatedModel, simulated_models
from routing.routers import (
    ClusterRouter,
    FixedRouter,
    OracleRouter,
    Router,
    oracle_plan,
)
from routing.tasks import Task, Verifier, load_boolq

SEEDS = range(20)

RouterFactory = Callable[
    [list[Task], dict[str, SimulatedModel], dict[str, np.ndarray], float, int], Router
]

ROUTERS: dict[str, RouterFactory] = {
    "all-small": lambda *_: FixedRouter("small"),
    "all-medium": lambda *_: FixedRouter("medium"),
    "frontier-first": lambda *_: FixedRouter("frontier"),
    "cluster": lambda tasks, models, features, dollars, seed: ClusterRouter(
        features, seed=seed
    ),
    "oracle": lambda tasks, models, features, dollars, seed: OracleRouter(
        oracle_plan(tasks, models, dollars)
    ),
}


def main() -> None:
    tasks, truth = load_boolq()
    verifier = Verifier(truth)
    features = embed(tasks)
    dollars = len(tasks) / 2

    print(f"{len(tasks)} tasks, ${dollars:.2f} budget, {len(SEEDS)} seeds\n")
    print(f"{'router':<16}{'pass rate':>14}{'spent':>9}  calls (mean)")
    for name, make_router in ROUTERS.items():
        rates, spent, calls = [], [], {m: 0 for m in ("small", "medium", "frontier")}
        for seed in SEEDS:
            # Shuffle per seed: stream order matters to routers that learn.
            stream = random.Random(seed).sample(tasks, len(tasks))
            models = simulated_models(tasks, truth, features, seed)
            router = make_router(stream, models, features, dollars, seed)
            result = run_episode(stream, models, router, verifier, dollars)
            rates.append(result.passed / len(tasks))
            spent.append(result.spent)
            for m, n in result.calls.items():
                calls[m] += n
        mix = " ".join(f"{m}={n / len(SEEDS):.0f}" for m, n in calls.items())
        print(
            f"{name:<16}{statistics.mean(rates):>8.3f} ±{statistics.stdev(rates):.3f}"
            f"{statistics.mean(spent):>8.2f}  {mix}"
        )


if __name__ == "__main__":
    main()
