import pytest

from routing.tasks import BROKEN, DATA, Verifier, extract_code, load_tasks


def reference_as_design(task_id: str) -> str:
    ref = (DATA / f"{task_id}_ref.sv").read_text()
    return ref.replace("module RefModule", "module TopModule")


def test_loads_every_problem_but_the_broken_ones():
    ids = {t.id for t in load_tasks()}
    assert len(ids) == 150
    assert not ids & BROKEN


@pytest.mark.parametrize("task_id", ["Prob001_zero", "Prob079_fsm3onehot", "Prob153_gshare"])
def test_reference_design_passes(task_id):
    assert Verifier().check(task_id, reference_as_design(task_id))


def test_wrong_design_fails():
    wrong = "module TopModule(output zero);\n  assign zero = 1'b1;\nendmodule\n"
    assert not Verifier().check("Prob001_zero", wrong)


def test_design_that_does_not_compile_fails():
    assert not Verifier().check("Prob001_zero", "module TopModule(\n")


def test_known_verdicts_skip_simulation():
    verifier = Verifier(known={("Prob001_zero", "anything"): True})
    assert verifier.check("Prob001_zero", "anything")


@pytest.mark.parametrize(
    "reply",
    [
        "[BEGIN]\nmodule TopModule;\nendmodule\n[DONE]",
        "[BEGIN]\n```verilog\nmodule TopModule;\nendmodule\n```\n[DONE]",
        "Here it is:\n```verilog\nmodule TopModule;\nendmodule\n```",
        "[BEGIN]\nmodule TopModule;\nendmodule\n",
    ],
)
def test_extracts_code_from_reply(reply):
    assert extract_code(reply) == "module TopModule;\nendmodule\n"
