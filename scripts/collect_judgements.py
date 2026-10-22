"""Record a judgement by every model on every pair of small designs that disagree.

Writes data/judgements.jsonl. Re-running skips judgements already recorded.

    uv run python -m scripts.collect_judgements [--workers 8]
"""

import argparse
import itertools
import json
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from routing import llm
from routing.checks import load_checker
from routing.judge import JUDGEMENTS, evidence, pair_key, prompt
from routing.models import load_attempts
from routing.tasks import SYSTEM, Verifier, extract_code, load_tasks

MAX_FAILURES_IN_A_ROW = 10


def main() -> None:
    # Flush each line, so progress shows when output goes to a log file.
    sys.stdout.reconfigure(line_buffering=True)
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    specs = {t.id: t.spec for t in load_tasks()}
    attempts = [a for a in load_attempts() if a.task in specs]
    checker = load_checker(specs, [a.code for a in attempts])
    small = defaultdict(list)
    for a in attempts:
        if a.model == "small":
            small[a.task].append(a.code)
    pairs = {}
    for task, codes in small.items():
        for a, b in itertools.combinations(codes, 2):
            if not checker.agree(task, a, b):
                pairs[pair_key(task, a, b)] = sorted((a, b))

    done = set()
    if JUDGEMENTS.exists():
        for line in JUDGEMENTS.read_text().splitlines():
            r = json.loads(line)
            done.add((r["task"], r["a"], r["b"], r["model"]))
    jobs = [
        (key, model)
        for key in pairs
        for model in llm.MODELS
        if (*key, model) not in done
    ]
    print(f"{len(pairs)} disagreeing pairs; {len(done)} judgements recorded, {len(jobs)} to go")
    if not jobs:
        return

    overhead = {model: llm.overhead_tokens(model) for model in llm.MODELS}
    verifier = Verifier()
    prompts = {
        key: prompt(specs[key[0]], a, b, evidence(checker, specs[key[0]], a, b))
        for key, (a, b) in pairs.items()
    }
    failures = 0
    with ThreadPoolExecutor(args.workers) as pool, JUDGEMENTS.open("a") as out:
        futures = {
            pool.submit(llm.ask, model, prompts[key], SYSTEM): (key, model)
            for key, model in jobs
        }
        for n, future in enumerate(as_completed(futures), 1):
            (task, a, b), model = futures[future]
            try:
                reply = future.result()
            except Exception as e:
                failures += 1
                print(f"[{n}/{len(jobs)}] {task} {model} failed: {e}")
                if failures >= MAX_FAILURES_IN_A_ROW:
                    print("too many failures in a row; stopping")
                    pool.shutdown(cancel_futures=True)
                    break
                continue
            failures = 0

            code = extract_code(reply.text)
            input_tokens = reply.input_tokens - overhead[model]
            row = {
                "task": task,
                "a": a,
                "b": b,
                "model": model,
                "passed": verifier.check(task, code),
                "cost": llm.cost(model, input_tokens, reply.output_tokens),
                "input_tokens": input_tokens,
                "output_tokens": reply.output_tokens,
                "thinking_tokens": reply.thinking_tokens,
                "code": code,
                "reply": reply.text,
            }
            out.write(json.dumps(row) + "\n")
            print(
                f"[{n}/{len(jobs)}] {task} {model}: "
                f"{'pass' if row['passed'] else 'FAIL'} ${row['cost']:.5f}"
            )


if __name__ == "__main__":
    main()
