import pytest

from routing.budget import Budget
from routing.checks import Checker
from routing.models import Answer, Attempt, replay_models
from routing.tasks import Task, Verifier
from routing.teams import (
    Adjudication,
    Agreement,
    CompileCascade,
    Single,
    Team,
    run_team_episode,
)

TASK = Task("t", "spec")
CAPS = {"small": 0.01, "medium": 0.1, "frontier": 0.2}
# Small writes a right design twice and a wrong one once; frontier is always right.
ATTEMPTS = [
    Attempt("t", "small", "right", True, 0.01),
    Attempt("t", "small", "right_too", True, 0.01),
    Attempt("t", "small", "wrong", False, 0.01),
    Attempt("t", "medium", "right", True, 0.1),
    Attempt("t", "frontier", "best", True, 0.2),
]
VERIFIER = Verifier(known={(a.task, a.code): a.passed for a in ATTEMPTS})


def checker(**agreements: bool) -> Checker:
    """A checker where every design compiles, except "broken", and only the
    listed pairs (named a__b) agree."""
    codes = {a.code for a in ATTEMPTS} | {"broken"}
    compared = {}
    for a in codes:
        for b in codes:
            if a < b:
                agree = agreements.get(f"{a}__{b}") or agreements.get(f"{b}__{a}")
                compared[("t", a, b)] = 0 if agree else 5
    return Checker({"t": "spec"}, {c: c != "broken" for c in codes}, compared)


def team(dollars: float = 1.0, seed: int = 0) -> Team:
    return Team(TASK, replay_models(ATTEMPTS, seed), Budget(dollars, 1, CAPS))


def test_replay_never_repeats_an_attempt_within_a_problem():
    t = team()
    assert len(set(t.call("small", "small", "small"))) == 3
    with pytest.raises(ValueError):
        t.call("small")


def test_a_round_holds_at_most_four_calls():
    with pytest.raises(ValueError):
        team().call("small", "small", "small", "medium", "frontier")


def test_single_steps_down_when_the_budget_is_short():
    t = team(dollars=0.05)
    Single("frontier").solve(t, checker())
    assert t.calls == ["small"]


def test_compile_cascade_escalates_only_on_a_broken_design():
    ok = Checker({"t": "spec"}, {"right": True, "right_too": True, "wrong": True})
    t = team()
    CompileCascade().solve(t, ok)
    assert t.calls == ["small"]

    broken = Checker({"t": "spec"}, {"right": False, "right_too": False, "wrong": False})
    t = team()
    assert CompileCascade().solve(t, broken) == "best"
    assert t.calls == ["small", "frontier"]


def test_agreement_submits_an_agreed_design_in_one_round():
    t = team()
    design = Agreement(("small", "small", "small")).solve(t, checker(right__right_too=True))
    assert design in {"right", "right_too"}
    assert t.rounds == 1


def test_disagreement_escalates_to_the_best_affordable_model():
    t = team()
    assert Agreement(("small", "small", "small")).solve(t, checker()) == "best"
    assert t.calls[-1] == "frontier"
    assert t.rounds == 2


def test_agreement_prefers_the_bigger_models_design():
    t = team()
    # Medium writes "right", which agrees with every design small can write.
    agreements = checker(right__wrong=True, right__right_too=True)
    assert Agreement(("small", "medium")).solve(t, agreements) == "right"
    assert len(t.calls) == 2


def test_episode_charges_every_call_and_stays_within_budget():
    tasks = [TASK]
    result = run_team_episode(
        tasks,
        replay_models(ATTEMPTS, 0),
        Agreement(("small", "small")),
        checker(),
        VERIFIER,
        Budget(1.0, 1, CAPS),
    )
    assert result.calls["small"] == 2
    assert result.spent == pytest.approx(0.01 * 2 + 0.2 * result.calls["frontier"])
    assert result.spent <= 1.0


class FakeJudge:
    """Always writes "best", at a fixed cost, and remembers what it was shown."""

    def __init__(self):
        self.shown = []

    def judge(self, task, a, b):
        self.shown.append({a, b})
        return Answer("best", 0.05)


def judged_team(dollars: float = 1.0) -> tuple[Team, FakeJudge]:
    judge = FakeJudge()
    caps = CAPS | {"judge:small": 0.05}
    budget = Budget(dollars, 1, caps)
    return Team(TASK, replay_models(ATTEMPTS, 0), budget, {"small": judge}), judge


def test_adjudication_skips_the_judge_when_designs_agree():
    t, judge = judged_team()
    everything_agrees = checker(right__right_too=True, right__wrong=True, right_too__wrong=True)
    Adjudication("small").solve(t, everything_agrees)
    assert t.calls == ["small", "small"]
    assert judge.shown == []


def test_adjudication_shows_the_judge_both_designs_on_disagreement():
    t, judge = judged_team()
    assert Adjudication("small").solve(t, checker()) == "best"
    assert t.calls == ["small", "small", "judge:small"]
    assert t.rounds == 2
    assert len(judge.shown[0]) == 2


def test_adjudication_escalates_when_the_judge_is_unaffordable():
    t, _ = judged_team()
    t.budget.caps["judge:small"] = 10.0
    assert Adjudication("small").solve(t, checker()) == "best"
    assert t.calls[-1] == "frontier"
