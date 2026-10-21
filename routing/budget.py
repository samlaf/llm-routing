from dataclasses import dataclass


@dataclass
class Budget:
    dollars: float
    tasks_left: int
    # The most a single call to each model can cost. A live system gets this
    # from a cap on output tokens.
    caps: dict[str, float]

    def can_afford(self, model: str) -> bool:
        # Every task must get a call, and a call's cost is known only after it
        # returns. So keep back the cheapest model's worst case for each later
        # task.
        floor = min(self.caps.values())
        return self.caps[model] + floor * (self.tasks_left - 1) <= self.dollars

    def spend(self, model: str, cost: float) -> None:
        if not self.can_afford(model):
            raise ValueError(f"cannot afford {model} with {self}")
        if cost > self.caps[model]:
            raise ValueError(f"{model} cost ${cost} above its cap")
        self.dollars -= cost
        self.tasks_left -= 1
