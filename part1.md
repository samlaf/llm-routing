# Part 1: implementation and results

One model call per question. The model and its notation are in [math-model.md](math-model.md).

## Setup

- 100 BoolQ validation questions.
- Costs: small $0.25, medium $0.50, frontier $1.
- Budget: $50 total, a hard limit.

## Simulation

Real model calls are replaced by simulated models. Each question has a hidden tier $z(x)$, and $p_a(x) = P[z(x), a]$:

| tier | share | small | medium | frontier | best model |
|---|---|---|---|---|---|
| easy | 30% | 0.95 | 0.97 | 0.98 | small |
| medium | 30% | 0.60 | 0.92 | 0.95 | medium |
| hard | 25% | 0.52 | 0.60 | 0.92 | frontier |
| hopeless | 15% | 0.50 | 0.52 | 0.55 | small |

- Sending each tier to its best model costs $51.25 per 100 tasks, just over the budget. So the router must also trade tiers off.
- Tiers come from a score: `topic_weight × topic difficulty + (1 − topic_weight) × noise`.
  - Questions are clustered into 10 topics by their embeddings, and each topic gets a random difficulty.
  - Questions are ranked by score and cut into tiers by share.
  - The topic part is what a router can learn from text. The noise part is invisible to it.
  - The default `topic_weight` is 0.5.
- Each call is an independent draw: the model is right with probability $p_a(x)$.

## Code

| component | code |
|---|---|
| Task stream: BoolQ questions; the answer key stays in the verifier, out of the router's reach | `routing/tasks.py`, `data/boolq_100.jsonl` |
| Simulated models and hidden tiers | `routing/models.py` |
| Featurizer: frozen `BAAI/bge-small-en-v1.5`, vectors cached to disk | `routing/features.py` |
| Budget: hard limit; always keeps back the cheapest call for each question left | `routing/budget.py` |
| Episode runner: one call per question; raises an error on overspend | `routing/episode.py` |
| Routers: fixed baselines, `ClusterRouter`, `OracleRouter` | `routing/routers.py` |
| Comparison over 20 shuffled streams | `main.py` |

Run `uv run python main.py`. Test with `uv run pytest`.

### Routers

- **Fixed** (`all-small`, `all-medium`, `frontier-first`): always pick one model, and step down to cheaper ones once it can't be afforded.
- **`ClusterRouter`**:
  - *Memory:* k-means with 8 topics, fitted once on the embeddings of all 100 questions. This uses future questions' text, never their answers. Each (topic, model) cell keeps passes and tries.
  - *Estimator:* each cell's Beta posterior, shrunk toward that model's overall pass rate with strength $\kappa = 2$. The overall rate starts at ½ for every model.
  - *Exploration:* Thompson sampling.
  - *Allocator:* $\arg\max \tilde p_a - \lambda c_a$ over affordable models. $\lambda$ starts at 0.5 and is paced with step 0.1 toward a fixed target spend of $B/T$ per call.
- **`OracleRouter`**: follows the exact dynamic program on the true $p_a(x)$.

## Results

`main.py`, 20 seeds, pass rate from the verifier's draws:

| router | pass rate | spent | calls (small / medium / frontier) |
|---|---|---|---|
| all-small | 0.648 ± 0.045 | 25.00 | 100 / 0 / 0 |
| all-medium | 0.802 ± 0.036 | 50.00 | 0 / 100 / 0 |
| frontier-first | 0.738 ± 0.049 | 50.00 | 66 / 1 / 33 |
| cluster | 0.760 ± 0.047 | 48.59 | 35 / 51 / 15 |
| oracle | 0.843 ± 0.039 | 50.00 | 46 / 31 / 23 |

Ceilings by `topic_weight`, as expected pass rates over 20 seeds. The text oracle uses $q_a(x)$ = the expected pass rate given the question's topic, averaged over the noise by Monte Carlo. A one-off script computed these numbers; `main.py` doesn't report them yet.

| `topic_weight` | offline oracle | text oracle | all-medium |
|---|---|---|---|
| 0.5 (default) | 0.859 | 0.795 | 0.795 |
| 0.75 | 0.859 | 0.817 | 0.795 |
| 0.9 | 0.859 | 0.834 | 0.795 |
| 1.0 | 0.859 | 0.840 | 0.795 |

## Findings

- **At the default setting, no text-based router can beat always-medium.** The text oracle ties it at 0.795. All 6.4 points of the oracle's lead come from noise that the embeddings can't see.
- **`ClusterRouter` pays about 4 points to learn.** Its flat starting prior plus the cost penalty makes small look best, so it sends 35 questions to small. Small is poor outside the easy tier.
- **The oracle's lead is about the size the swap argument predicts.** Each swap gains about 0.32 − 2 × 0.02 = 0.28. About 22 swaps fit: easy and hopeless questions fund upgrades on hard ones. That gives about 6 points.
- **Verifier noise hides small differences.** A single run varies by about ±0.04, the same size as the gaps between routers.

## Next steps

- Add the text oracle to `main.py`, and score by expected passes.
- Report results across several `topic_weight` values.
- Give `ClusterRouter` an ordered prior ($p_s \le p_m \le p_f$), and pace $\lambda$ toward the remaining budget per remaining task.
- Try the shared-difficulty (IRT) estimator.
