"""Models a router can call, replayed from attempts recorded with real models.

A replayed call returns one attempt recorded for that problem, drawn at random,
so it costs and scores what a live call did, without making one.
"""

import json
import random
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean
from typing import Protocol

from routing import llm
from routing.tasks import Task

ATTEMPTS = Path(__file__).parent.parent / "data" / "attempts.jsonl"


@dataclass(frozen=True)
class Answer:
    code: str
    cost: float


@dataclass(frozen=True)
class Attempt:
    task: str
    model: str
    code: str
    passed: bool
    cost: float
    input_tokens: int = 0


class Model(Protocol):
    name: str

    def answer(self, task: Task) -> Answer: ...


def load_attempts(path: Path = ATTEMPTS) -> list[Attempt]:
    attempts = []
    for line in path.read_text().splitlines():
        r = json.loads(line)
        if r["output_tokens"] > llm.MAX_OUTPUT_TOKENS:
            # Recorded without a cap. With one, the reply would have been cut
            # off: no complete design, at the capped cost.
            cost = llm.cost(r["model"], r["input_tokens"], llm.MAX_OUTPUT_TOKENS)
            attempts.append(
                Attempt(r["task"], r["model"], "", False, cost, r["input_tokens"])
            )
        else:
            attempts.append(
                Attempt(
                    r["task"], r["model"], r["code"], r["passed"], r["cost"], r["input_tokens"]
                )
            )
    return attempts


def cost_caps(attempts: list[Attempt]) -> dict[str, float]:
    """The most one call to each model can cost, with output capped."""
    longest = max(a.input_tokens for a in attempts)
    return {
        m: llm.cost(m, longest, llm.MAX_OUTPUT_TOKENS)
        for m in by_model_and_task(attempts)
    }


def by_model_and_task(attempts: list[Attempt]) -> dict[str, dict[str, list[Attempt]]]:
    table: dict[str, dict[str, list[Attempt]]] = defaultdict(lambda: defaultdict(list))
    for a in attempts:
        table[a.model][a.task].append(a)
    return {m: dict(tasks) for m, tasks in table.items()}


def pass_rates(attempts: list[Attempt]) -> dict[str, dict[str, float]]:
    return {
        m: {t: mean(a.passed for a in tries) for t, tries in tasks.items()}
        for m, tasks in by_model_and_task(attempts).items()
    }


def mean_costs(attempts: list[Attempt]) -> dict[str, dict[str, float]]:
    return {
        m: {t: mean(a.cost for a in tries) for t, tries in tasks.items()}
        for m, tasks in by_model_and_task(attempts).items()
    }


@dataclass
class ReplayModel:
    """Answers with recorded attempts, never the same one twice per problem.

    Repeated calls to a model are independent samples, so a model can't agree
    with itself by replaying one attempt twice.
    """

    name: str
    attempts: dict[str, list[Attempt]]
    rng: random.Random
    used: dict[str, set[int]] = field(default_factory=lambda: defaultdict(set))

    def answer(self, task: Task) -> Answer:
        fresh = [
            i for i in range(len(self.attempts[task.id])) if i not in self.used[task.id]
        ]
        if not fresh:
            raise ValueError(f"no unused attempt of {self.name} on {task.id}")
        i = self.rng.choice(fresh)
        self.used[task.id].add(i)
        attempt = self.attempts[task.id][i]
        return Answer(attempt.code, attempt.cost)


def replay_models(attempts: list[Attempt], seed: int) -> dict[str, ReplayModel]:
    rng = random.Random(seed)
    return {
        m: ReplayModel(m, tasks, random.Random(rng.getrandbits(64)))
        for m, tasks in by_model_and_task(attempts).items()
    }
