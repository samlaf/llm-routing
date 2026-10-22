import random
import statistics
from collections import Counter

from routing.budget import Budget
from routing.checks import load_checker
from routing.judge import judge_caps, load_judgements, replay_judges
from routing.llm import MODELS
from routing.models import cost_caps, load_attempts, mean_costs, pass_rates, replay_models
from routing.tasks import Verifier, load_tasks
from routing.teams import (
    Adjudication,
    Agreement,
    CompileCheck,
    Single,
    Strategy,
    run_team_episode,
)

SEEDS = range(50)

STRATEGIES: dict[str, Strategy] = {
    "all-small": Single("small"),
    "all-medium": Single("medium"),
    "all-frontier*": Single("frontier"),
    "compile-check": CompileCheck(),
    "agree: small x2": Agreement(("small", "small")),
    "agree: small x3": Agreement(("small", "small", "small")),
    "agree: small+medium": Agreement(("small", "medium")),
    "agree: small x2+medium": Agreement(("small", "small", "medium")),
    "judge: small": Adjudication("small"),
    "judge: medium": Adjudication("medium"),
    "judge: frontier": Adjudication("frontier"),
}
# Reference points that ignore the budget.
OVER_BUDGET = {"all-frontier*"}


def main() -> None:
    attempts = load_attempts()
    judgements = load_judgements()
    p, c = pass_rates(attempts), mean_costs(attempts)
    tasks = [t for t in load_tasks() if all(t.id in p[m] for m in MODELS)]
    caps = cost_caps(attempts) | judge_caps(judgements)
    # Same budget as Part 1: always-medium spends it exactly, in expectation.
    dollars = sum(c["medium"][t.id] for t in tasks)
    verifier = Verifier(
        known={(a.task, a.code): a.passed for a in attempts}
        | {(task, j.code): j.passed for (task, *_), js in judgements.items() for j in js}
    )
    checker = load_checker({t.id: t.spec for t in tasks}, [a.code for a in attempts])

    print("Replaying recorded calls, verdicts and checks from data/attempts.jsonl,")
    print("data/judgements.jsonl and data/checks.jsonl: no model calls, no simulation.")
    print("To record new ones: uv run poe record\n")
    print(f"{len(tasks)} problems, ${dollars:.4f} budget, {len(SEEDS)} seeds\n")
    print(f"{'strategy':<24}{'pass rate':>15}{'spent':>9}{'calls':>7}{'rounds':>8}  calls (mean)")
    for name, strategy in STRATEGIES.items():
        # Frontier's worst case on every problem, so the strategy never steps down.
        limit = caps["frontier"] * len(tasks) if name in OVER_BUDGET else dollars
        rates, spent, calls, rounds = [], [], [], []
        mix: Counter[str] = Counter()
        for seed in SEEDS:
            stream = random.Random(seed).sample(tasks, len(tasks))
            budget = Budget(limit, len(tasks), caps)
            result = run_team_episode(
                stream,
                replay_models(attempts, seed),
                strategy,
                checker,
                verifier,
                budget,
                replay_judges(judgements, seed),
            )
            rates.append(result.passed / len(tasks))
            spent.append(result.spent)
            calls.append(result.calls.total() / len(tasks))
            rounds.append(result.rounds / len(tasks))
            mix.update(result.calls)
        counts = " ".join(f"{m}={n / len(SEEDS):.0f}" for m, n in sorted(mix.items()))
        print(
            f"{name:<24}{statistics.mean(rates):>8.3f} ±{statistics.stdev(rates):.3f}"
            f"{statistics.mean(spent):>9.4f}{statistics.mean(calls):>7.2f}"
            f"{statistics.mean(rounds):>8.2f}  {counts}"
        )
    print(f"\n* over budget: a reference point, not a candidate (budget ${dollars:.2f})")


if __name__ == "__main__":
    main()
