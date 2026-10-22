# Part 3: splitting a design across agents

Parts 1 and 2 work on single-module problems, where there is little to split. Part 3 moves to multi-module designs, where a team can divide the work. Nothing is built yet. The model and its notation are in [math-model.md](math-model.md); sources are in [references.md](references.md).

## Cost of splitting

A strategy costs the sum of its calls, each priced per token as in [math-model.md](math-model.md).

**When splitting saves money.** Compare one frontier call that reads all $N$ inputs with *map-reduce*: one cheap call per input that writes short notes, then one frontier call that reads only the notes. Let $L$ be the length of each input, $h$ the instructions every call must read, $\ell$ the length of each note, and $\rho = \pi_{\text{cheap}} / \pi_{\text{frontier}}$ the price ratio. Ignoring the final answer, which is the same either way, map-reduce is cheaper exactly when

$$
\rho\,(h + L) + \ell \;<\; L .
$$

$N$ cancels out. Splitting saves money when each input is long compared with the overhead per call, not when there are many inputs. Prompt caching lowers the effective $h$.

## H2: an expensive architect with cheap implementers

> The frontier model writes the module hierarchy, the port interfaces and a spec per module. Cheap models write the modules in parallel, each checked by its own unit testbench, and integration is tested last. This matches frontier-alone quality at lower cost on **datapath** designs (arithmetic, memory, FIFOs). It fails on **control** designs, where FSMs coordinate other modules cycle by cycle.

- **Why it might hold:** module interfaces are explicit, so leaf modules are self-contained sub-problems. Unit testbenches show which module failed, which fixes the credit problem of judging only the final answer.
- **Why it might fail:**
  - Control logic couples modules through timing, which interfaces don't capture.
  - Errors compound: five modules at 90% each succeed together only 59% of the time.
  - The cost inequality above may not hold. Here $h$ is the interface spec each implementer reads, and $L$ is the module code it writes.
- **What we measure:**
  - pass rate and cost per design category, for frontier alone against architect plus implementers;
  - all 3 × 3 (architect, implementer) model pairs.
- **Data:** RTLLM 2.0 or a CVDP subset with multi-module designs. Both label designs by category (arithmetic, control, memory, misc).
- **Prior work:** [VerilogCoder](https://arxiv.org/abs/2408.08927) and [MAGE](https://arxiv.org/abs/2412.07822) (decomposition and checks, one model throughout), [EDAid](https://arxiv.org/html/2502.10857v1) (more small-model calls did not reach a bigger model).

## H3 (stretch): cheap readers for EDA reports

> Cheap sub-agents summarise long timing, synthesis and DRC reports. The frontier model reads only the summaries and chooses the fix.

- This is the case where $L$ is huge, so the cost inequality pays off most.
- **The grader:** did timing improve after re-running the flow? Each check takes minutes of OpenROAD time, and we'd build the benchmark ourselves.
- **Prior work:** [MARCO](https://developer.nvidia.com/blog/configurable-graph-based-task-solving-with-the-marco-multi-ai-agent-framework-for-chip-design/)'s timing-report agents; the [Kimi K3 post](https://www.luoluo.ai/blog/kimi-k3)'s inner loop.
