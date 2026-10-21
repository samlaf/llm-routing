import pytest

from routing.budget import Budget

CAPS = {"small": 0.25, "medium": 0.5, "frontier": 1.0}


def test_reserves_cheapest_worst_case_for_each_later_task():
    budget = Budget(dollars=1.0, tasks_left=3, caps=CAPS)
    assert budget.can_afford("medium")
    assert not budget.can_afford("frontier")


def test_last_task_can_spend_everything():
    budget = Budget(dollars=1.0, tasks_left=1, caps=CAPS)
    assert budget.can_afford("frontier")


def test_spend_rejects_unaffordable_model():
    budget = Budget(dollars=1.0, tasks_left=3, caps=CAPS)
    with pytest.raises(ValueError):
        budget.spend("frontier", 0.1)


def test_spend_rejects_cost_above_cap():
    budget = Budget(dollars=1.0, tasks_left=1, caps=CAPS)
    with pytest.raises(ValueError):
        budget.spend("small", 0.3)


def test_spend_charges_actual_cost():
    budget = Budget(dollars=1.0, tasks_left=2, caps=CAPS)
    budget.spend("medium", 0.2)
    assert budget.dollars == pytest.approx(0.8)
    assert budget.tasks_left == 1
