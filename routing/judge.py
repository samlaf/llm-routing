"""A model that settles a disagreement between two designs, shown where they differ.

Judgements are recorded once for every pair of small designs that disagree, then
replayed, as attempts are.
"""

import json
import random
from dataclasses import dataclass
from pathlib import Path

from routing import llm
from routing.checks import Checker, counterexample, digest
from routing.models import Answer
from routing.tasks import INSTRUCTIONS

JUDGEMENTS = Path(__file__).parent.parent / "data" / "judgements.jsonl"


def evidence(checker: Checker, spec: str, a: str, b: str) -> str:
    broken = [name for name, code in (("A", a), ("B", b)) if not checker.compiles(code)]
    if len(broken) == 2:
        return "Neither design compiles."
    if broken:
        return f"Design {broken[0]} does not compile."
    trace = counterexample(spec, a, b)
    if trace is None:
        return "They could not be simulated together."
    return (
        "Simulated on the same inputs, they first differ at the last row below "
        f"(values in hexadecimal):\n\n{trace}"
    )


def prompt(spec: str, a: str, b: str, found: str) -> str:
    return (
        f"Question:\n{spec.strip()}\n\n"
        "Two engineers wrote designs for this spec, and the designs disagree.\n\n"
        f"Design A:\n```verilog\n{a.strip()}\n```\n\n"
        f"Design B:\n```verilog\n{b.strip()}\n```\n\n"
        f"{found}\n\n"
        "Decide which behavior the spec requires, then write a correct TopModule. "
        "It may be design A, design B, or a fix of either.\n"
        f"{INSTRUCTIONS}\n\nAnswer:\n"
    )


def pair_key(task: str, a: str, b: str) -> tuple[str, str, str]:
    """The same pair in either order: the judge always sees the designs in this order."""
    first, second = sorted((a, b))
    return (task, digest(first), digest(second))


@dataclass(frozen=True)
class Judgement:
    code: str
    passed: bool
    cost: float
    input_tokens: int


def load_judgements(path: Path = JUDGEMENTS) -> dict[tuple[str, str, str, str], list[Judgement]]:
    """Recorded judgements by (task, design digest, design digest, model)."""
    table: dict[tuple[str, str, str, str], list[Judgement]] = {}
    for line in path.read_text().splitlines():
        r = json.loads(line)
        if r["output_tokens"] > llm.MAX_OUTPUT_TOKENS:
            # As with attempts: an uncapped reply would have been cut off.
            cost = llm.cost(r["model"], r["input_tokens"], llm.MAX_OUTPUT_TOKENS)
            judgement = Judgement("", False, cost, r["input_tokens"])
        else:
            judgement = Judgement(r["code"], r["passed"], r["cost"], r["input_tokens"])
        table.setdefault((r["task"], r["a"], r["b"], r["model"]), []).append(judgement)
    return table


def judge_caps(table: dict[tuple[str, str, str, str], list[Judgement]]) -> dict[str, float]:
    """The most one judgement by each model can cost, with output capped."""
    longest = max(j.input_tokens for js in table.values() for j in js)
    return {f"judge:{m}": llm.cost(m, longest, llm.MAX_OUTPUT_TOKENS) for m in llm.MODELS}


@dataclass
class ReplayJudge:
    name: str
    table: dict[tuple[str, str, str, str], list[Judgement]]
    rng: random.Random

    def judge(self, task: str, a: str, b: str) -> Answer:
        judgement = self.rng.choice(self.table[(*pair_key(task, a, b), self.name)])
        return Answer(judgement.code, judgement.cost)


def replay_judges(table, seed: int) -> dict[str, ReplayJudge]:
    rng = random.Random(seed)
    return {m: ReplayJudge(m, table, random.Random(rng.getrandbits(64))) for m in llm.MODELS}
