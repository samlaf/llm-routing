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
16 concurrent agents that can communicate
same total budget

## Docs

- [math-model.md](math-model.md): the model, theory and architecture.
- [part1.md](part1.md): Part 1 on VerilogEval: problem, hypothesis, method, status.
- [part2.md](part2.md): Part 2 on RTL: grader vs checks, hypotheses H1–H3, open questions.
- [references.md](references.md): every source, with what it says and why it matters here.

Run: `uv run main.py`. Test: `uv run pytest`.
