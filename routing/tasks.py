"""BoolQ tasks and the verifier that holds their answers."""

import json
from dataclasses import dataclass
from pathlib import Path

DATA = Path(__file__).parent.parent / "data" / "boolq_100.jsonl"


@dataclass(frozen=True)
class Task:
    # The answer lives in the Verifier, not here, so a router can never read it.
    id: str
    question: str
    passage: str


def load_boolq(path: Path = DATA) -> tuple[list[Task], dict[str, bool]]:
    tasks, truth = [], {}
    for line in path.read_text().splitlines():
        row = json.loads(line)
        tasks.append(Task(row["id"], row["question"], row["passage"]))
        truth[row["id"]] = row["answer"]
    return tasks, truth


class Verifier:
    def __init__(self, truth: dict[str, bool]):
        self._truth = truth

    def check(self, task_id: str, answer: bool) -> bool:
        return self._truth[task_id] == answer
