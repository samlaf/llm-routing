import pytest

from routing.budget import Budget


def test_reserves_cheapest_call_for_each_later_task():
    budget = Budget(dollars=1.0, tasks_left=3, floor_cost=0.25)
    assert budget.can_afford(0.5)
    assert not budget.can_afford(0.75)


def test_last_task_can_spend_everything():
    budget = Budget(dollars=1.0, tasks_left=1, floor_cost=0.25)
    assert budget.can_afford(1.0)


def test_spend_rejects_overspend():
    budget = Budget(dollars=1.0, tasks_left=3, floor_cost=0.25)
    with pytest.raises(ValueError):
        budget.spend(1.0)
