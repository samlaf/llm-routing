"""Copy VerilogEval v2's spec-to-RTL problems into data/verilog-eval."""

import shutil
import subprocess
import tempfile
from pathlib import Path

REPO = "https://github.com/NVlabs/verilog-eval"
# Pinned so the problem set never changes under recorded attempts.
COMMIT = "c498220d0a52248f8e3fdffe279075215bde2da6"
OUT = Path(__file__).parent.parent / "data" / "verilog-eval"


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["git", "clone", "-q", REPO, tmp], check=True)
        subprocess.run(["git", "-C", tmp, "checkout", "-q", COMMIT], check=True)
        src = Path(tmp) / "dataset_spec-to-rtl"
        files = [
            p
            for p in src.iterdir()
            if p.name.endswith(("_prompt.txt", "_ref.sv", "_test.sv"))
        ]
        OUT.mkdir(parents=True, exist_ok=True)
        for p in files:
            shutil.copy(p, OUT / p.name)
        shutil.copy(Path(tmp) / "LICENSE", OUT / "LICENSE")
    print(f"wrote {len(files) // 3} problems to {OUT}")


if __name__ == "__main__":
    main()
