"""VerilogEval spec-to-RTL problems and the verifier that holds their testbenches."""

import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

DATA = Path(__file__).parent.parent / "data" / "verilog-eval"

# Same flags as VerilogEval's own harness.
IVERILOG = ["iverilog", "-Wall", "-Winfloop", "-Wno-timescale", "-g2012", "-s", "tb"]
SIM_TIMEOUT_S = 30
PASSED = re.compile(r"^Mismatches: 0 in \d+ samples$", re.MULTILINE)
# Every testbench names `tb_mismatch` in $dumpvars before declaring it, which
# Icarus 13 rejects. The call only dumps waveforms and plays no part in grading.
DUMPVARS = re.compile(r"^\s*\$dumpvars\(.*\);\s*$", re.MULTILINE)


@dataclass(frozen=True)
class Task:
    # The reference design and testbench live in the Verifier, not here, so a
    # router can never read them.
    id: str
    spec: str


# Problems no correct design can pass, so they say nothing about the models.
BROKEN = {
    # The spec and reference use outputs Y1 and Y3; the testbench expects Y2 and Y4.
    "Prob099_m2014_q6c",
    # The reference sets an initial value the spec never mentions.
    "Prob034_dff8",
    "Prob053_m2014_q4d",
    "Prob104_mt2015_muxdff",
    # The reference reverses the select the spec describes.
    "Prob062_bugs_mux2",
    # The only spec that never names the module TopModule.
    "Prob131_mt2015_q4",
}

# VerilogEval's own spec-to-RTL prompt, without in-context examples or rules.
SYSTEM = "You are a Verilog RTL designer that only writes code using correct Verilog syntax."
INSTRUCTIONS = (
    "Enclose your code with [BEGIN] and [DONE]. Only output the code snippet\n"
    "and do NOT output anything else."
)


def load_tasks(path: Path = DATA) -> list[Task]:
    tasks = [
        Task(p.name.removesuffix("_prompt.txt"), p.read_text())
        for p in sorted(path.glob("*_prompt.txt"))
    ]
    return [t for t in tasks if t.id not in BROKEN]


def prompt_for(task: Task) -> str:
    return f"Question:\n{task.spec.strip()}\n{INSTRUCTIONS}\n\nAnswer:\n"


def extract_code(reply: str) -> str:
    """The design in a reply: inside [BEGIN] ... [DONE], minus any code fence."""
    marked = re.search(r"\[BEGIN\](.*?)(?:\[DONE\]|$)", reply, re.DOTALL)
    body = marked.group(1) if marked else reply
    fenced = re.search(r"```[a-zA-Z]*\n(.*?)```", body, re.DOTALL)
    return (fenced.group(1) if fenced else body).strip() + "\n"


class Verifier:
    """Passes a design if it matches the reference on the problem's testbench."""

    def __init__(self, path: Path = DATA, known: dict[tuple[str, str], bool] = {}):
        self.path = path
        # Simulation is deterministic, so a verdict computed once (for example
        # when an attempt was recorded) holds forever.
        self._verdicts = dict(known)

    def check(self, task_id: str, code: str) -> bool:
        key = (task_id, code)
        if key not in self._verdicts:
            self._verdicts[key] = self._simulate(task_id, code)
        return self._verdicts[key]

    def _simulate(self, task_id: str, code: str) -> bool:
        with tempfile.TemporaryDirectory() as tmp:
            design = Path(tmp) / "TopModule.sv"
            design.write_text(code)
            testbench = Path(tmp) / "test.sv"
            testbench.write_text(
                DUMPVARS.sub("", (self.path / f"{task_id}_test.sv").read_text())
            )
            binary = Path(tmp) / "sim"
            compiled = subprocess.run(
                IVERILOG
                + [
                    "-o",
                    str(binary),
                    str(testbench),
                    str(design),
                    str(self.path / f"{task_id}_ref.sv"),
                ],
                capture_output=True,
                text=True,
            )
            if compiled.returncode != 0:
                return False
            try:
                run = subprocess.run(
                    ["vvp", str(binary)],
                    cwd=tmp,
                    capture_output=True,
                    text=True,
                    timeout=SIM_TIMEOUT_S,
                )
            except subprocess.TimeoutExpired:
                return False
            return PASSED.search(run.stdout) is not None
