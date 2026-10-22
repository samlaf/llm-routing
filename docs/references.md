# References

Each source: what it says, and why it matters here. "Claim" marks results we have not checked ourselves.

## Routing between models

| source | what it says | link to this project |
|---|---|---|
| [RouteLLM](https://arxiv.org/abs/2406.18665) (Ong et al., 2024) | Strong-vs-weak routing trained on preference data; calls the strong model when $P(\text{strong wins} \mid x) \ge \alpha$. Best router: matrix factorisation. Routers transfer to unseen model pairs. No oracle reported; text-only routers are at chance on new domains. | $\alpha$ is our $\lambda$ for two models. Sharing structure across models, plus transfer across pairs, is evidence for one shared difficulty (the IRT estimator). |
| [LLMRouterBench](https://arxiv.org/abs/2601.07206) (Li et al., 2026) | 400K instances, 33 models, 10 routers under one protocol. A k-means × model accuracy table (Avengers) ties neural routers. Embedding choice moves results ~1 point. The best routers land below the best-model-per-dataset baseline. | Our cluster memory is that table plus a prior and Thompson sampling. Routers capture domain structure, not per-task structure: the gap between the text oracle and the offline oracle. |
| [Routing and cascading survey](https://arxiv.org/abs/2603.04445) (Moslem & Kelleher, 2026) | Taxonomy: when the decision is made, which signals it uses, how it is computed. Covers PILOT (online multiple-choice knapsack), UniRoute, FrugalGPT, AutoMix, Cascade Routing, R2-Reasoner, Router-R1. Notes that no method combines answer-level signals with online learning. | Part 1 is pre-generation, online, bandit-computed. Part 2's cascades use answer-level signals, the gap the survey names. |
| [Workload-Router-Pool](https://arxiv.org/abs/2603.21354) (Chen et al., 2026) | Vision paper for routing in LLM serving fleets. Separates signal extraction from the decision; a per-(model, domain) Beta scoreboard; too few samples per cell is the main limit. Switching models mid-session costs 4–13 points. | Same split as our featurizer vs allocator. For concurrent agents: count committed spend, share one outcome table. |
| [The Souq](https://robvc.com/research/the-souq) (Chitra, 2026) | Market structure of OpenRouter: capability routing (which model) vs execution routing (which provider); ranking by quality minus cost; cache-related overbilling. | Quality minus cost is our Lagrangian; $\lambda$ is the market price of a dollar. Session cost depends on cache reuse. |

## Orchestration and agents

| source | what it says | link to this project |
|---|---|---|
| [Agent orchestration](https://zeroentropy.dev/concepts/agent-orchestration/) (ZeroEntropy) | Workflow orchestration (a fixed graph) vs autonomous orchestration (a supervisor calls sub-agents as tools). Start autonomous, log decisions, then hardcode the dominant paths. Claim: naive multi-agent costs 5–10× for marginal gains. | The workflow-vs-autonomous split applies to routing too: a fixed cascade vs a model that decides to escalate. |
| [Is the agent harness dead?](https://finance.biggo.com/podcast/119b307cecd92bca) (Katz, 2026) | Coordinator bots direct worker agents. Cost cut through cache hit rate, token efficiency and model mix. Mostly anecdote. | Supports measuring cost in tokens, not calls. |

## Chip design: benchmarks

| source | what it says | link to this project |
|---|---|---|
| [VerilogEval v2](https://dl.acm.org/doi/10.1145/3718088) (NVIDIA, 2024; [code](https://github.com/NVlabs/verilog-eval)) | 156 single-module spec-to-RTL problems from HDLBits, graded by a testbench against a reference in Icarus Verilog. Frontier models are near saturation. | Part 1's task stream. |
| [EvolVE](https://arxiv.org/html/2601.18067v1) (2026) | Reports errors in VerilogEval v2's golden models and specs; proposes a corrected version. | We found one broken problem ourselves. Some failures may be the benchmark's fault. |
| [CVDP](https://arxiv.org/abs/2506.14074) (NVIDIA, 2025) | 783 problems in 13 categories: spec-to-RTL, module reuse, debugging, testbench and assertion generation. Single-call and multi-turn agentic formats, graded in Docker. ≤34% pass@1 at release. | Candidate for Part 2: headroom and multi-file tasks. |
| RTLLM 2.0 | ~50 larger designs, graded by testbench and synthesis, labelled by category (arithmetic, control, memory, misc). | Candidate for Part 2's datapath-vs-control split. |
| [Benchmarking LLMs for Verilog design flows](https://arxiv.org/abs/2607.22759) (2026) | 50 tasks across combinational, sequential and FSM designs, with small open models and a repair pipeline. Claim (from a search summary, not the abstract): small models suit leaf modules; stateful control needs a bigger model. | Prior evidence for H2. Unconfirmed. |

## Chip design: routing and cascades

| source | what it says | link to this project |
|---|---|---|
| [VeriDispatcher](https://arxiv.org/html/2511.22749v1) (2025) | Predicts difficulty from text embeddings, with one small classifier per model, and routes RTL tasks before generation. Claim: up to +18% accuracy on RTLLM with 40% of commercial calls. | The chip-design version of Part 1's router. |
| [AutoChip](https://arxiv.org/html/2311.04887v2) (Blocklove et al., 2024) | Repairs RTL using compiler and simulation feedback. Small models do the early rounds, a large model the last. Claim: same success as GPT-4o with feedback, at 41.9% lower cost. | Prior evidence for H1 (cascades driven by tool checks). |
| [David vs. Goliath](https://arxiv.org/abs/2512.05073) (2025) | Small models in an agentic workflow on CVDP. Claim: near large-model results "at a fraction of the cost". No numbers in the abstract. | Prior evidence for H1 and H2. |

## Chip design: multi-agent systems

| source | what it says | link to this project |
|---|---|---|
| [MAGE](https://arxiv.org/abs/2412.07822) (2024) | Multi-agent RTL generation: high-temperature sampling, testbench agent, checks of internal state at each clock edge. Claim: 95.7% on VerilogEval v2. | Shows checks and sampling help; uses one model throughout. |
| [VerilogCoder](https://arxiv.org/abs/2408.08927) (NVIDIA, 2024) | A planner splits the task into a graph of sub-tasks; an AST-based waveform tracer debugs. Claim: 94.2% on VerilogEval v2. | Task decomposition inside one RTL problem. |
| [MARCO](https://developer.nvidia.com/blog/configurable-graph-based-task-solving-with-the-marco-multi-ai-agent-framework-for-chip-design/) (NVIDIA) | Configurable task graphs, static or dynamic, with agents per sub-task: RTL fixing, Verilog generation, DRC code, timing-report summaries and timing-path debug. Doesn't say which model each agent uses. | Static vs dynamic graphs = workflow vs autonomous. Its timing-report agents are H3's "cheap readers". |
| [EDAid](https://arxiv.org/html/2502.10857v1) (Wu et al., 2025) | Three agents with different prompts write EDA scripts; a judge picks one by the probability of "yes". 8B multi-agent (84–88%) beats 8B single (76–78%) but stays below 70B single (94–96%). | More calls to a small model didn't replace a bigger model. A data point against "cheap ensembles beat big models". |
| [Hierarchical IRs, end-to-end multi-agent workflow](https://arxiv.org/abs/2608.30659) (2026) | Re-ran MAGE with GPT-5: GPT-5 alone and MAGE both passed 146/156 VerilogEval problems. Found problems with reset handling, synthesisability and ambiguous prompts. | VerilogEval is near saturation for frontier models: the room is in cost. |

## Chip design: industry views

| source | what it says | link to this project |
|---|---|---|
| [Meta harness on Kimi K3's chip](https://www.luoluo.ai/blog/kimi-k3) (Lee, 2026) | One agent writes SystemVerilog, runs Yosys and OpenROAD, reads reports and fixes. An outer harness changes how it reasons and logs every attempt. Clean synthesis with zero DRC errors still hid a wrong-math bug. | Cheap checks can pass wrong designs. The logged outer loop is our memory. |
| [When AI agents cross chip design silos](https://semiengineering.com/when-ai-agents-cross-chip-design-silos/) (SemiEngineering) | Industry moving to many small, specialised agents under an orchestrator, with humans as glue. Mostly quotes. | Context for Part 2. |
| [Mark Ren interview](https://semiwiki.com/forum/threads/the-researcher-behind-an-early-llm-for-chip-design-says-buying-ai-alone-may-not-determine-semiconductor-leadership.25784/) (SemiWiki) | ChipNeMo's lead, now at Agentrys: the lasting advantage is memory of a company's own workflows, checked against verifiable outcomes. Mostly vendor claims. | Our memory plus verifier loop, as a business thesis. |
