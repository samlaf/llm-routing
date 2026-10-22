# Part 1: one call per RTL problem

One model call per problem. The model and its notation are in [math-model.md](math-model.md); sources are in [references.md](references.md).

## The problem

**Tasks:** the spec-to-RTL problems of [VerilogEval v2](https://github.com/NVlabs/verilog-eval): 156, minus six with verified defects (see Caveats), so 150 in all. Each is a natural-language spec plus a port list, and the model writes one Verilog module, `TopModule`. For example, `Prob079_fsm3onehot`:

```
Implement a module named TopModule with ports:
 - input in, input state (4 bits), output next_state (4 bits), output out
Implement only the combinational next-state and output logic of a Moore
machine with one-hot encoding A=0001, B=0010, C=0100, D=1000:
  State | Next (in=0), Next (in=1) | Output
  A     | A, B                      | 0
  B     | C, B                      | 0
  C     | A, D                      | 0
  D     | C, B                      | 1
```

The problems run from trivial (`zero`, `notgate`) through counters, shift registers and FSMs to hard ones (`gshare`, `conwaylife`, `lemmings4`). The `circuitN` problems give only a table of waveforms, and the model must infer the circuit.

**Verifier:** a hidden testbench drives random inputs into the model's module and a reference module, and counts mismatches. Zero mismatches is a pass. We run it with Icarus Verilog, using the benchmark's own compiler flags.

**Models:**

| | model | input $/M tokens | output $/M tokens |
|---|---|---|---|
| small | Claude Haiku 5.5 | 0.10 | 0.50 |
| medium | Claude Sonnet 5.5 | 2.00 | 10.00 |
| frontier | Claude Opus 5.5 | 4.00 | 20.00 |

All three run at the same effort level (`medium`), so they differ only in size. A call's cost is its tokens times the list price. Thinking counts as output.

## Hypothesis

> **H0: the spec text predicts which model passes well enough that a router beats the best fixed mix of models at the same budget.**

- **Why it might hold:** problem families differ sharply in difficulty, and the family usually shows in the text (FSM tables, Karnaugh maps, waveform tables).
- **Why it might fail:** if difficulty varies *within* families in ways the text doesn't show.
- **What would refute it:** the text oracle (below) scores no better than the best fixed mix.

## Method: collect once, replay many times

1. **Collect.** Call every model 5 times on every problem: 155 × 3 × 5 = 2,325 calls (`Prob099` was excluded before collection). Grade each attempt and record the code, the token counts and the cost. (`uv run python -m scripts.collect`)
2. **Replay.** A replayed model answers with one of its recorded attempts for that problem, drawn at random. The router sees only the verdict for the model it chose, so feedback is still bandit feedback.

Why replay:

- Pass rates, costs and correlations between models are all real. No simulator settings decide the result.
- We can run many shuffled streams at no further cost.
- The same records serve Part 2: cascades replay from them too.

**Budget.** $B$ is the expected cost of always calling medium on the stream, so $B/T$ is medium's average cost, as in the swap argument: $0.55 for 150 problems.

**Output cap.** A hard budget needs each call's worst case. Every model gets a cap of 4,096 output tokens. That bounds a call to $0.0022 (small), $0.044 (medium) or $0.087 (frontier). An attempt recorded with a longer reply counts as cut off: it costs the cap and fails. This affects 19 of Haiku's 775 attempts and none of Sonnet's or Opus's. A cap of 8,192 is impossible: reserving Haiku's worst case for every problem would cost more than the whole budget. Haiku's thinking is heavy-tailed: its median reply is 436 tokens, but 1% of replies exceed 5,700, and the longest is 8,692.

**Reference levels, all scored by expected passes:**

- **Offline oracle:** the exact knapsack on pass rates estimated from the 5 attempts.
- **Text oracle:** the same knapsack on pass rates predicted from the spec alone. For each problem, it averages the pass rates of its 10 nearest other problems in embedding space, with every model's results known. It gets the true expected costs, so it tests only whether text predicts pass rates.
- **Best fixed mix:** the best shares of models that ignore which problem is which.
- **Fixed baselines:** always small, always medium, frontier-first.
- **Learning router (`cluster`):** cluster memory, Thompson sampling and paced $\lambda$.

## Results

`uv run python part1.py`: 150 problems, 20 shuffled streams. "Expected" scores each choice by the model's estimated pass rate on that problem; "realized" counts the replayed verdicts.

| model | pass rate | mean cost per call |
|---|---|---|
| small | 0.935 | $0.00044 |
| medium | 0.965 | $0.0037 |
| frontier | 0.984 | $0.0063 |

| router | expected | realized | spent (of $0.55) | calls: small / medium / frontier |
|---|---|---|---|---|
| all-small | 0.935 | 0.936 | $0.07 | 150 / 0 / 0 |
| all-medium | 0.963 ± 0.004 | 0.965 | $0.51 | 12 / 138 / 0 |
| frontier-first | 0.962 ± 0.006 | 0.962 | $0.51 | 42 / 74 / 33 |
| best fixed mix (= all-medium) | 0.963 ± 0.004 | 0.965 | $0.51 | 12 / 138 / 0 |
| cluster (learning) | 0.955 ± 0.008 | 0.950 | $0.41 | 71 / 46 / 33 |
| text oracle | 0.944 ± 0.002 | 0.945 | $0.50 | 63 / 51 / 35 |
| offline oracle | 0.991 | 0.991 | $0.24 | 133 / 9 / 8 |

The offline oracle plans and is scored on the same 5 samples, so it is optimistic. Planned on samples 0–2 and scored on 3–4 (and the reverse), it reaches **0.972**.

## Findings

- **H0 is refuted on this benchmark.** The text oracle (0.944) scores *below* always-medium (0.963). It moves money to frontier on the wrong problems and downgrades problems that small then fails. The result holds for every neighbourhood size from 3 to 80 (0.939–0.956). Small fails at least once on 18 problems. Of the 20 problems the text rates hardest for small, only 4 are among them, close to the 2.4 expected by chance.
- **Per-problem routing is worth a lot, if you know the problem.** The held-out oracle reaches 0.972 against always-medium's 0.963, while spending under half the budget. It sends almost everything to small and upgrades about 17 problems. The value is in knowing *which* problems need a bigger model, and the spec text doesn't say.
- **The small model is the bargain.** Haiku passes 93.5% of problems at 1/8 of Sonnet's cost. Always-small spends 12% of the budget for 3 points less than always-medium.
- **Bigger is not always better per problem.** On `dualedge`, Haiku passes 5/5, Sonnet 3/5 and Opus 0/5. On `fsm_serialdata`, Sonnet passes 1/5 and Haiku 4/5.
- **The learning router can't beat always-medium,** since the text it learns from carries no signal. It pays about 1 point to explore.
- **The hard budget costs something.** Even always-medium drops 12 calls to small near the end of the stream, because medium's capped worst case is 12× its mean.

**What this means for Part 2:** the information that would pay for routing appears only *after* a model has tried. That is H1: let small try first, and use checks on its design to decide whether to escalate.

## Caveats

- **Six problems excluded for verified defects.** No correct design can pass them:
  - `Prob099_m2014_q6c`: spec and reference use outputs `Y1`/`Y3`; the testbench expects `Y2`/`Y4`.
  - `Prob034_dff8`, `Prob053_m2014_q4d`, `Prob104_mt2015_muxdff`: the reference sets an `initial` value the spec never mentions, so correct designs fail on the first sample.
  - `Prob062_bugs_mux2`: the reference reverses the select logic the spec describes.
  - `Prob131_mt2015_q4`: the only spec that never names the module `TopModule`; every model writes `top_module`.
  
  One more problem no model passes, `Prob093_ece241_2014_q3`, looks genuinely hard and stays in.
- **Icarus Verilog 13.** Every testbench names `tb_mismatch` in `$dumpvars` before declaring it. Icarus 12 accepted that; Icarus 13 rejects it. The verifier drops that line before simulating. It only dumps waveforms and plays no part in grading. All 150 reference designs pass their own testbenches.
- **Calls go through the Claude Code CLI** (`claude -p`), which uses the subscription login rather than an API key. Its own system prompt, tools and settings are switched off. It still adds a fixed preamble of about 590 input tokens per call, which we measure per model and subtract before computing cost.
- **No sampling control.** The CLI doesn't expose temperature. The 5 attempts show each model's natural variation.
- **Coarse pass rates.** 5 attempts give pass rates in steps of 0.2, which makes the in-sample oracle optimistic (0.991 against 0.972 held out).
- **One budget level.** All results use $B$ = always-medium. A sweep over $B$ would show where small-plus-upgrades beats medium.
- **Collection cost:** $7.98 at list prices (Haiku $0.35, Sonnet $2.82, Opus $4.81), billed to the subscription.

## Why real models instead of a simulation

The first version of Part 1 used 100 BoolQ true/false questions with simulated models. Each question had a hidden difficulty tier, partly predictable from its embedding. That study showed that the simulator's settings decided the answer: at the default setting, a router that knew the true expected pass rate of every topic scored the same as always-medium. All of the oracle's lead came from per-question noise no router could see. Real models and a real verifier remove that freedom. The result turned out similar, but now it is a measurement, not an assumption. The code and results are in git history (commit `57bc190`).

## Code

| component | code |
|---|---|
| Dataset, pinned to upstream commit `c498220` | `scripts/fetch_verilog_eval.py`, `data/verilog-eval/` |
| Task loader, prompt, code extraction, verifier | `routing/tasks.py` |
| Model client through the Claude Code CLI; prices; output cap | `routing/llm.py` |
| Collector | `scripts/collect.py` → `data/attempts.jsonl` |
| Replay models, pass-rate and cost tables, cost caps | `routing/models.py` |
| Budget with per-call caps | `routing/budget.py` |
| Routers: fixed, mix, plan-following, cluster | `routing/routers.py` |
| Offline oracle, best fixed mix, text estimates | `routing/oracles.py` |
| Spec embeddings (`bge-small-en-v1.5`), cached | `routing/features.py`, `data/verilog-eval.bge-small-en-v1.5.npz` |
| Comparison | `part1.py` |

Run `uv run python part1.py`. Test with `uv run pytest`.
