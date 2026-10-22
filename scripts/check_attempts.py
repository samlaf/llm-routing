"""Record check results for every recorded design in data/checks.jsonl.

Compiles each distinct design, and runs the differential test on every pair of
distinct designs for the same problem. Replays then look results up instead of
simulating.

    uv run python -m scripts.check_attempts [--workers 8]
"""

import argparse
import itertools
import json
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from routing.checks import CHECKS, compiles, digest, mismatches
from routing.models import load_attempts
from routing.tasks import load_tasks


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    specs = {t.id: t.spec for t in load_tasks()}
    designs = defaultdict(set)
    for a in load_attempts():
        if a.task in specs:
            designs[a.task].add(a.code)

    codes = sorted({c for cs in designs.values() for c in cs})
    with ThreadPoolExecutor(args.workers) as pool:
        compiled = dict(zip(codes, pool.map(compiles, codes)))
        pairs = [
            (task, a, b)
            for task, cs in designs.items()
            for a, b in itertools.combinations(sorted(c for c in cs if compiled[c]), 2)
        ]
        results = list(pool.map(lambda p: mismatches(specs[p[0]], p[1], p[2]), pairs))

    with CHECKS.open("w") as out:
        for code, ok in compiled.items():
            out.write(json.dumps({"code": digest(code), "compiles": ok}) + "\n")
        for (task, a, b), n in zip(pairs, results):
            row = {"task": task, "a": digest(a), "b": digest(b), "mismatches": n}
            out.write(json.dumps(row) + "\n")
    print(f"{len(codes)} designs, {len(pairs)} pairs -> {CHECKS}")


if __name__ == "__main__":
    main()
