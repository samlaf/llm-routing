# Agent Routing Problem

## Part 1

Given:
- 3 models (small, medium, frontier)
  - cost vs prob of success tradeoff
  - these aren't known... need to learn them
- stream of tasks
- verifier
  - look at output, decide binary: pass or fail


Build:
1. router: which model to call
2. learning mechanism: to learn the router (memory system?)

Optimize:
- objective: pass rate on the stream
- constraint: budget on $ cost (hard constraint: 50% can be sent to frontier, 30% to medium, 20% to small)

### Implementation

Setup: 100 BoolQ true/false questions; costs $1 / $0.50 / $0.25; budget $50; one call per question. Full model + system disgram in [math-model.md](math-model.md).

- `routing/models.py`: simulated models. Each question has a hidden tier (easy / medium / hard / hopeless) with its own pass rates.
- `routing/features.py`: frozen text embeddings (`bge-small-en-v1.5`).
- `routing/routers.py`:
  - baselines: always small, always medium, frontier-first.
  - `ClusterRouter`: k-means memory + Thompson sampling + paced λ.
  - `OracleRouter`: the ceiling; knows the true pass rates.
- `main.py`: compares routers over 20 shuffled streams.

Finding: the learned router (0.77) loses to always-medium (0.80). In the simulation, difficulty is barely predictable from text: a perfect text-based router reaches only 0.80.

Run: `uv run main.py`. Test: `uv run pytest`.

## Part 2

Same as part 1, but allowed to call multiple models in parallel
16 concurrent agents that can communicate
same total budget

### Implementation

TODO
