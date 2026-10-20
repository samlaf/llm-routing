from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field

from routing.budget import Budget
from routing.models import Model
from routing.routers import Router
from routing.tasks import Task, Verifier


@dataclass
class Result:
    passed: int = 0
    spent: float = 0.0
    calls: Counter[str] = field(default_factory=Counter)
    log: list[tuple[str, str, bool]] = field(default_factory=list)


def run_episode(
    tasks: list[Task],
    models: Mapping[str, Model],
    router: Router,
    verifier: Verifier,
    dollars: float,
) -> Result:
    budget = Budget(dollars, len(tasks), min(m.cost for m in models.values()))
    result = Result()
    for task in tasks:
        name = router.choose(task, budget)
        model = models[name]
        budget.spend(model.cost)
        passed = verifier.check(task.id, model.answer(task))
        router.update(task, name, passed)

        result.passed += passed
        result.spent += model.cost
        result.calls[name] += 1
        result.log.append((task.id, name, passed))
    return result
