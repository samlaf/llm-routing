"""Record graded attempts by every model on every problem in data/attempts.jsonl.

Routers are evaluated by replaying these attempts, so experiments make no
further model calls. Re-running skips attempts already recorded, so an
interrupted run picks up where it stopped.

    uv run python -m scripts.collect [--samples 5] [--workers 8] [--limit N]
"""

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from routing import llm
from routing.models import ATTEMPTS
from routing.tasks import SYSTEM, Verifier, extract_code, load_tasks, prompt_for

# Many failures in a row usually mean a usage limit; retrying then only burns time.
MAX_FAILURES_IN_A_ROW = 10


def main() -> None:
    # Flush each line, so progress shows when output goes to a log file.
    sys.stdout.reconfigure(line_buffering=True)
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--limit", type=int, help="only the first N problems")
    args = parser.parse_args()

    tasks = load_tasks()[: args.limit]
    done = set()
    if ATTEMPTS.exists():
        for line in ATTEMPTS.read_text().splitlines():
            row = json.loads(line)
            done.add((row["task"], row["model"], row["sample"]))
    # Sample-major order, so a partial run still covers every problem.
    jobs = [
        (sample, model, task)
        for sample in range(args.samples)
        for model in llm.MODELS
        for task in tasks
        if (task.id, model, sample) not in done
    ]
    print(f"{len(done)} attempts recorded, {len(jobs)} to go")
    if not jobs:
        return

    overhead = {model: llm.overhead_tokens(model) for model in llm.MODELS}
    print(f"CLI overhead in input tokens: {overhead}")
    verifier = Verifier()
    failures = 0
    with (
        ThreadPoolExecutor(args.workers) as pool,
        ATTEMPTS.open("a") as out,
    ):
        futures = {
            pool.submit(llm.ask, model, prompt_for(task), SYSTEM): (sample, model, task)
            for sample, model, task in jobs
        }
        for n, future in enumerate(as_completed(futures), 1):
            sample, model, task = futures[future]
            try:
                reply = future.result()
            except Exception as e:
                failures += 1
                print(f"[{n}/{len(jobs)}] {task.id} {model} #{sample} failed: {e}")
                if failures >= MAX_FAILURES_IN_A_ROW:
                    print("too many failures in a row; stopping")
                    pool.shutdown(cancel_futures=True)
                    break
                continue
            failures = 0

            code = extract_code(reply.text)
            input_tokens = reply.input_tokens - overhead[model]
            row = {
                "task": task.id,
                "model": model,
                "sample": sample,
                "passed": verifier.check(task.id, code),
                "cost": llm.cost(model, input_tokens, reply.output_tokens),
                "input_tokens": input_tokens,
                "output_tokens": reply.output_tokens,
                "thinking_tokens": reply.thinking_tokens,
                "code": code,
                "reply": reply.text,
            }
            out.write(json.dumps(row) + "\n")
            out.flush()
            print(
                f"[{n}/{len(jobs)}] {task.id} {model} #{sample}: "
                f"{'pass' if row['passed'] else 'FAIL'} ${row['cost']:.5f}"
            )


if __name__ == "__main__":
    main()
