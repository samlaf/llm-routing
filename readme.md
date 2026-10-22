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

## Part 2

Same as part 1, but allowed to call multiple models in parallel
up to 4 concurrent agents per problem, which can communicate
same total budget

## Docs

- [math-model.md](math-model.md): the model, theory and architecture.
- [part1.md](part1.md): Part 1 on VerilogEval: problem, hypothesis, method, status.
- [part2.md](part2.md): Part 2: teams of up to 4 agents per problem (cascades, agreement, judges), with conclusions.
- [part3.md](part3.md): Part 3: splitting multi-module designs across agents (H2), and cheap readers for EDA reports (H3).
- [references.md](references.md): every source, with what it says and why it matters here.

Run: `uv run python part1.py`, `uv run python part2.py`. Test: `uv run pytest`.
