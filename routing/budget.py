from dataclasses import dataclass


@dataclass
class Budget:
    dollars: float
    # Problems still to solve, counting the current one.
    tasks_left: int
    # The most a single call to each model can cost. A live system gets this
    # from a cap on output tokens.
    caps: dict[str, float]

    def can_afford(self, *models: str) -> bool:
        """Whether one round of calls fits.

        Every problem must get a call, and a call's cost is known only after it
        returns. So keep back the cheapest model's worst case for each later
        problem.
        """
        floor = min(self.caps.values())
        worst = sum(self.caps[m] for m in models)
        return worst + floor * (self.tasks_left - 1) <= self.dollars

    def spend(self, model: str, cost: float) -> None:
        if not self.can_afford(model):
            raise ValueError(f"cannot afford {model} with {self}")
        if cost > self.caps[model]:
            raise ValueError(f"{model} cost ${cost} above its cap")
        self.dollars -= cost

    def next_task(self) -> None:
        self.tasks_left -= 1
