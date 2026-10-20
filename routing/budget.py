from dataclasses import dataclass


@dataclass
class Budget:
    dollars: float
    tasks_left: int
    floor_cost: float

    def can_afford(self, cost: float) -> bool:
        # Every task must get a call, so keep enough back to send each later
        # task to the cheapest model.
        return cost + self.floor_cost * (self.tasks_left - 1) <= self.dollars

    def spend(self, cost: float) -> None:
        if not self.can_afford(cost):
            raise ValueError(f"cannot afford ${cost} with {self}")
        self.dollars -= cost
        self.tasks_left -= 1
