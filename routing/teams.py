"""Teams of agents that make several calls per problem, and the strategies they follow."""

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

from routing.budget import Budget
from routing.checks import Checker
from routing.models import Answer, Model
from routing.tasks import Task, Verifier

MAX_AGENTS = 4
# Where a team escalates, best first, when its own designs don't hold up.
ESCALATION = ("frontier", "medium")


class Judge(Protocol):
    def judge(self, task: str, a: str, b: str) -> Answer: ...


class Team:
    """One problem's calls: each round runs at most MAX_AGENTS calls at once."""

    def __init__(
        self,
        task: Task,
        models: Mapping[str, Model],
        budget: Budget,
        judges: Mapping[str, Judge] = {},
    ):
        self.task = task
        self.models = models
        self.budget = budget
        self.judges = judges
        self.calls: list[str] = []
        self.rounds = 0

    def can_call(self, *names: str) -> bool:
        return self.budget.can_afford(*names)

    def call(self, *names: str) -> list[str]:
        if not 0 < len(names) <= MAX_AGENTS:
            raise ValueError(f"a round runs 1 to {MAX_AGENTS} calls, not {len(names)}")
        if not self.can_call(*names):
            raise ValueError(f"cannot afford {names}")
        designs = []
        for name in names:
            answer = self.models[name].answer(self.task)
            self.budget.spend(name, answer.cost)
            designs.append(answer.code)
            self.calls.append(name)
        self.rounds += 1
        return designs

    def judge(self, model: str, a: str, b: str) -> str:
        """One round: `model` sees both designs and where they differ, and
        writes the design to submit."""
        name = f"judge:{model}"
        if not self.can_call(name):
            raise ValueError(f"cannot afford {name}")
        answer = self.judges[model].judge(self.task.id, a, b)
        self.budget.spend(name, answer.cost)
        self.calls.append(name)
        self.rounds += 1
        return answer.code

    def escalate(self, fallback: str) -> str:
        """The best affordable model's design, or `fallback` if none fits."""
        for name in ESCALATION:
            if self.can_call(name):
                return self.call(name)[0]
        return fallback


class Strategy(Protocol):
    def solve(self, team: Team, checker: Checker) -> str: ...


@dataclass
class Single:
    """One call to one model, stepping down to cheaper ones when the budget is short."""

    model: str
    ladder: tuple[str, ...] = ("frontier", "medium", "small")

    def solve(self, team: Team, checker: Checker) -> str:
        options = self.ladder[self.ladder.index(self.model) :]
        return team.call(next(m for m in options if team.can_call(m)))[0]


@dataclass
class CompileCascade:
    """Small writes a design; escalate if it doesn't compile."""

    def solve(self, team: Team, checker: Checker) -> str:
        [design] = team.call("small")
        return design if checker.compiles(design) else team.escalate(design)


@dataclass
class Agreement:
    """`agents` write designs at once. Submit one that another agrees with,
    preferring the biggest model's; with no agreement, escalate."""

    agents: tuple[str, ...]
    rank: tuple[str, ...] = ("frontier", "medium", "small")

    def solve(self, team: Team, checker: Checker) -> str:
        agents = self.agents if team.can_call(*self.agents) else ("small",)
        designs = sorted(
            zip(agents, team.call(*agents)), key=lambda pair: self.rank.index(pair[0])
        )
        for i, (_, design) in enumerate(designs):
            others = designs[:i] + designs[i + 1 :]
            if any(checker.agree(team.task.id, design, other) for _, other in others):
                return design
        return team.escalate(designs[0][1])


@dataclass
class Adjudication:
    """Two small designs at once; if they disagree, `judge` sees both and where
    they differ, and writes the design to submit."""

    judge: str

    def solve(self, team: Team, checker: Checker) -> str:
        if not team.can_call("small", "small"):
            return team.call("small")[0]
        a, b = team.call("small", "small")
        if checker.agree(team.task.id, a, b):
            return a
        if team.can_call(f"judge:{self.judge}"):
            return team.judge(self.judge, a, b)
        return team.escalate(a)


@dataclass
class TeamResult:
    passed: int = 0
    spent: float = 0.0
    rounds: int = 0
    calls: Counter[str] = field(default_factory=Counter)


def run_team_episode(
    tasks: list[Task],
    models: Mapping[str, Model],
    strategy: Strategy,
    checker: Checker,
    verifier: Verifier,
    budget: Budget,
    judges: Mapping[str, Judge] = {},
) -> TeamResult:
    result = TeamResult()
    for task in tasks:
        before = budget.dollars
        team = Team(task, models, budget, judges)
        design = strategy.solve(team, checker)
        budget.next_task()

        result.passed += verifier.check(task.id, design)
        result.spent += before - budget.dollars
        result.rounds += team.rounds
        result.calls.update(team.calls)
    return result
