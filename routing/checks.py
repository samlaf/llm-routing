"""Checks a team can run on designs without the hidden testbench."""

import hashlib
import json
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

CHECKS = Path(__file__).parent.parent / "data" / "checks.jsonl"
IVERILOG = ["iverilog", "-g2012"]
SIM_TIMEOUT_S = 30
CYCLES = 200
# Rows of a counterexample shown to a model: enough context, not the whole run.
TRACE_ROWS = 24
# Spec port lines look like "- input  state (4 bits)", with loose spacing.
PORT = re.compile(
    r"^\s*-\s*(input|output)\s+(\w+)\s*,?\s*(?:\(\s*(\d+)\s*bits\s*\))?\s*$",
    re.MULTILINE,
)
MODULE = re.compile(r"\bmodule\s+(\w+)")
ACTIVE_HIGH_RESET = re.compile(r"^a?(sync_)?(reset|rst)$")


@dataclass(frozen=True)
class Port:
    direction: str
    name: str
    width: int


def ports(spec: str) -> list[Port]:
    return [Port(d, n, int(w or 1)) for d, n, w in PORT.findall(spec)]


def compiles(code: str) -> bool:
    with tempfile.TemporaryDirectory() as tmp:
        design = Path(tmp) / "design.sv"
        design.write_text(code)
        result = subprocess.run(
            IVERILOG + ["-s", "TopModule", "-o", str(Path(tmp) / "sim"), str(design)],
            capture_output=True,
        )
        return result.returncode == 0


def mismatches(spec: str, a: str, b: str) -> int | None:
    """Samples where two designs' outputs differ on the same random inputs.

    None if the pair doesn't compile together, which says at least one design
    is broken.
    """
    out = _simulate(spec, a, b, trace=False)
    found = re.search(r"^MISMATCHES (\d+)$", out or "", re.MULTILINE)
    return int(found.group(1)) if found else None


def counterexample(spec: str, a: str, b: str) -> str | None:
    """The inputs and both designs' outputs, up to the first sample where they
    differ, as a table to show a model. None if they never differ or can't run."""
    out = _simulate(spec, a, b, trace=True)
    if out is None or "\nFOUND" not in out:
        return None
    spec_ports = ports(spec)
    inputs = [p.name for p in spec_ports if p.direction == "input" and p.name != "clk"]
    outputs = [p.name for p in spec_ports if p.direction == "output"]
    header = (
        ["sample", "when"]
        + inputs
        + [f"{o} (A)" for o in outputs]
        + [f"{o} (B)" for o in outputs]
    )
    rows = [line.split()[1:] for line in out.splitlines() if line.startswith("ROW ")]
    shown = rows[-TRACE_ROWS:]
    table = [" | ".join(header)]
    for row in shown:
        when = "after clock edge" if row[1] == "1" else "inputs set"
        table.append(" | ".join([row[0], when, *row[2:]]))
    skipped = len(rows) - len(shown)
    note = f"({skipped} earlier samples not shown; the last row is the first mismatch)\n"
    return note + "\n".join(table)


def _simulate(spec: str, a: str, b: str, trace: bool) -> str | None:
    with tempfile.TemporaryDirectory() as tmp:
        files = []
        for suffix, code in (("_a", a), ("_b", b)):
            path = Path(tmp) / f"design{suffix}.sv"
            path.write_text(_rename_modules(code, suffix))
            files.append(str(path))
        bench = Path(tmp) / "bench.sv"
        bench.write_text(_bench(ports(spec), trace))
        binary = Path(tmp) / "sim"
        compiled = subprocess.run(
            IVERILOG + ["-s", "bench", "-o", str(binary), str(bench), *files],
            capture_output=True,
        )
        if compiled.returncode != 0:
            return None
        try:
            run = subprocess.run(
                ["vvp", str(binary)],
                cwd=tmp,
                capture_output=True,
                text=True,
                timeout=SIM_TIMEOUT_S,
            )
        except subprocess.TimeoutExpired:
            return None
        return run.stdout


def _rename_modules(code: str, suffix: str) -> str:
    # Both designs name their top TopModule, and may share helper names too.
    for name in set(MODULE.findall(code)):
        code = re.sub(rf"\b{name}\b", name + suffix, code)
    return code


def _random(width: int) -> str:
    words = ", ".join(["$random(seed__)"] * -(-width // 32))
    return f"{{{words}}}"


def _bench(spec_ports: list[Port], trace: bool) -> str:
    inputs = [p for p in spec_ports if p.direction == "input"]
    outputs = [p for p in spec_ports if p.direction == "output"]
    clocked = any(p.name == "clk" for p in inputs)
    # Double underscores keep the bench's own names apart from any port name.
    lines = ["`timescale 1ps/1ps", "module bench;", "  integer seed__ = 1, i__, errors__ = 0;"]
    for p in inputs:
        lines.append(f"  reg [{p.width - 1}:0] {p.name} = 0;")
    for p in outputs:
        lines += [
            f"  wire [{p.width - 1}:0] {p.name}__a;",
            f"  wire [{p.width - 1}:0] {p.name}__b;",
        ]
    for suffix in ("a", "b"):
        connections = [f".{p.name}({p.name})" for p in inputs]
        connections += [f".{p.name}({p.name}__{suffix})" for p in outputs]
        lines.append(f"  TopModule_{suffix} dut_{suffix}({', '.join(connections)});")
    # Like the grader, an x bit matches anything: count a sample only when
    # some bit is known on both sides and differs.
    differ = " || ".join(f"((|({p.name}__a ^ {p.name}__b)) === 1'b1)" for p in outputs) or "0"
    shown = [p.name for p in inputs if p.name != "clk"]
    shown += [f"{p.name}__a" for p in outputs] + [f"{p.name}__b" for p in outputs]

    def compare(phase: int) -> str:
        if not trace:
            return f"if ({differ}) errors__ = errors__ + 1;"
        values = "".join(f", {name}" for name in shown)
        row = f'$display("ROW %0d {phase}{" %h" * len(shown)}", i__{values});'
        return f'begin {row} if ({differ}) begin $display("FOUND"); $finish; end end'

    stimulus = []
    for p in inputs:
        if p.name == "clk":
            continue
        if ACTIVE_HIGH_RESET.match(p.name):
            # Reset at first, then rarely, so state machines reach deep states.
            stimulus.append(f"{p.name} = (i__ < 2) || ($random(seed__) % 20 == 0);")
        else:
            stimulus.append(f"{p.name} = {_random(p.width)};")
    lines += [
        "  initial begin",
        f"    for (i__ = 0; i__ < {CYCLES}; i__ = i__ + 1) begin",
        *[f"      {s}" for s in stimulus],
        f"      #1 {compare(0)}",
    ]
    if clocked:
        lines += ["      clk = 1;", f"      #1 {compare(1)}", "      clk = 0;"]
    lines += [
        "      #1;",
        "    end",
        '    $display("MISMATCHES %0d", errors__);',
        "    $finish;",
        "  end",
        "endmodule",
    ]
    return "\n".join(lines) + "\n"


class Checker:
    """Runs checks once per design or pair; results can be preloaded."""

    def __init__(
        self,
        specs: dict[str, str],
        compiled: dict[str, bool] = {},
        compared: dict[tuple[str, str, str], int | None] = {},
    ):
        self.specs = specs
        self._compiled = dict(compiled)
        self._compared = dict(compared)

    def compiles(self, code: str) -> bool:
        if code not in self._compiled:
            self._compiled[code] = compiles(code)
        return self._compiled[code]

    def agree(self, task_id: str, a: str, b: str) -> bool:
        if not (self.compiles(a) and self.compiles(b)):
            return False
        if a == b:
            return True
        a, b = sorted((a, b))
        key = (task_id, a, b)
        if key not in self._compared:
            self._compared[key] = mismatches(self.specs[task_id], a, b)
        return self._compared[key] == 0


def digest(code: str) -> str:
    return hashlib.sha1(code.encode()).hexdigest()[:16]


def load_checker(specs: dict[str, str], codes: list[str], path: Path = CHECKS) -> Checker:
    """A Checker preloaded with results recorded for these designs."""
    by_digest = {digest(c): c for c in codes}
    compiled, compared = {}, {}
    for line in path.read_text().splitlines():
        row = json.loads(line)
        if "compiles" in row:
            if row["code"] in by_digest:
                compiled[by_digest[row["code"]]] = row["compiles"]
        elif row["a"] in by_digest and row["b"] in by_digest:
            a, b = sorted((by_digest[row["a"]], by_digest[row["b"]]))
            compared[(row["task"], a, b)] = row["mismatches"]
    return Checker(specs, compiled, compared)
