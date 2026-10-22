import random
import statistics
from collections.abc import Callable

from routing.budget import Budget
from routing.episode import run_episode
from routing.features import embed
from routing.llm import MODELS
from routing.models import (
    cost_caps,
    load_attempts,
    mean_costs,
    pass_rates,
    replay_models,
)
from routing.oracles import best_mix, oracle_plan, text_estimates
from routing.routers import ClusterRouter, FixedRouter, MixRouter, PlanRouter, Router
from routing.tasks import Verifier, load_tasks

SEEDS = range(20)


def main() -> None:
    attempts = load_attempts()
    p, c = pass_rates(attempts), mean_costs(attempts)
    # Only problems every model has attempted, so every router sees the same stream.
    tasks = [t for t in load_tasks() if all(t.id in p[m] for m in MODELS)]
    caps = cost_caps(attempts)
    avg_p = {m: statistics.mean(p[m][t.id] for t in tasks) for m in MODELS}
    avg_cost = {m: statistics.mean(c[m][t.id] for t in tasks) for m in MODELS}
    # Always-medium spends the budget exactly, in expectation.
    dollars = sum(c["medium"][t.id] for t in tasks)
    verifier = Verifier(known={(a.task, a.code): a.passed for a in attempts})
    features = embed(tasks)

    print("Replaying recorded calls and verdicts from data/attempts.jsonl: no model calls.")
    print("To record new calls: uv run python -m scripts.collect\n")
    print(f"{len(tasks)} problems, {len(attempts)} attempts, ${dollars:.4f} budget\n")
    print(f"{'model':<10}{'pass rate':>10}{'mean cost':>12}{'cap':>10}")
    for m in MODELS:
        print(f"{m:<10}{avg_p[m]:>10.3f}{avg_cost[m]:>12.5f}{caps[m]:>10.5f}")
    print()

    plan = oracle_plan(tasks, p, c, dollars)
    # The question is whether text predicts pass rates, so the text oracle gets
    # the true expected costs.
    text_plan = oracle_plan(tasks, text_estimates(tasks, features, p), c, dollars)
    shares = best_mix(avg_p, avg_cost, dollars / len(tasks))

    routers: dict[str, Callable[[int], Router]] = {
        "all-small": lambda seed: FixedRouter("small", avg_cost),
        "all-medium": lambda seed: FixedRouter("medium", avg_cost),
        "frontier-first": lambda seed: FixedRouter("frontier", avg_cost),
        "best-mix": lambda seed: MixRouter(shares, avg_cost, seed),
        "cluster": lambda seed: ClusterRouter(features, avg_cost, seed=seed),
        "text-oracle": lambda seed: PlanRouter(text_plan, avg_cost),
        "oracle": lambda seed: PlanRouter(plan, avg_cost),
    }

    print(f"{'router':<16}{'expected':>15}{'realized':>10}{'spent':>9}  calls (mean)")
    for name, make_router in routers.items():
        expected, realized, spent = [], [], []
        calls = {m: 0 for m in MODELS}
        for seed in SEEDS:
            # Shuffle per seed: stream order matters to routers that learn.
            stream = random.Random(seed).sample(tasks, len(tasks))
            budget = Budget(dollars, len(tasks), caps)
            result = run_episode(
                stream, replay_models(attempts, seed), make_router(seed), verifier, budget
            )
            expected.append(statistics.mean(p[m][t] for t, m, _ in result.log))
            realized.append(result.passed / len(tasks))
            spent.append(result.spent)
            for m, n in result.calls.items():
                calls[m] += n
        mix = " ".join(f"{m}={n / len(SEEDS):.0f}" for m, n in calls.items())
        print(
            f"{name:<16}{statistics.mean(expected):>8.3f} ±{statistics.stdev(expected):.3f}"
            f"{statistics.mean(realized):>10.3f}{statistics.mean(spent):>9.4f}  {mix}"
        )


if __name__ == "__main__":
    main()
