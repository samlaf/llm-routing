import json

import pytest

from routing import llm
from routing.models import (
    Attempt,
    cost_caps,
    load_attempts,
    mean_costs,
    pass_rates,
    replay_models,
)
from routing.tasks import Task

ATTEMPTS = [
    Attempt("t0", "small", "a", True, 0.1),
    Attempt("t0", "small", "b", False, 0.3),
    Attempt("t0", "frontier", "c", True, 1.0),
]


def test_tables_average_over_attempts():
    assert pass_rates(ATTEMPTS)["small"]["t0"] == 0.5
    assert mean_costs(ATTEMPTS)["small"]["t0"] == pytest.approx(0.2)


def test_replay_answers_with_a_recorded_attempt():
    answers = {
        replay_models(ATTEMPTS, seed)["small"].answer(Task("t0", "spec"))
        for seed in range(50)
    }
    assert {(a.code, a.cost) for a in answers} == {("a", 0.1), ("b", 0.3)}


def test_replay_never_repeats_an_attempt_within_an_episode():
    model = replay_models(ATTEMPTS, seed=0)["small"]
    task = Task("t0", "spec")
    assert {model.answer(task).code, model.answer(task).code} == {"a", "b"}
    with pytest.raises(ValueError):
        model.answer(task)


def test_replies_over_the_output_cap_fail_at_the_capped_cost(tmp_path):
    def row(output_tokens):
        return {
            "task": "t0",
            "model": "small",
            "code": "module TopModule; endmodule\n",
            "passed": True,
            "cost": 0.1,
            "input_tokens": 100,
            "output_tokens": output_tokens,
        }

    path = tmp_path / "attempts.jsonl"
    path.write_text(
        "\n".join(json.dumps(row(n)) for n in (10, llm.MAX_OUTPUT_TOKENS + 1))
    )
    kept, cut = load_attempts(path)
    assert kept.passed and kept.cost == 0.1
    assert not cut.passed and cut.code == ""
    assert cut.cost == pytest.approx(llm.cost("small", 100, llm.MAX_OUTPUT_TOKENS))
    assert cost_caps([kept, cut])["small"] == pytest.approx(cut.cost)


def test_replay_is_deterministic_per_seed():
    def draws(seed):
        model = replay_models(ATTEMPTS, seed)["small"]
        return [model.answer(Task("t0", "spec")).code for _ in range(2)]

    assert draws(1) == draws(1)
