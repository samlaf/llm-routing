"""Reference levels: plans and estimates that use knowledge no deployed router has.

`p[model][task]` is a pass rate and `c[model][task]` an expected cost, both
estimated from recorded attempts.
"""

import numpy as np

from routing.tasks import Task

Table = dict[str, dict[str, float]]


def oracle_plan(
    tasks: list[Task], p: Table, c: Table, dollars: float, units: int = 20_000
) -> dict[str, str]:
    """One model per task, maximising expected passes within budget.

    Exact dynamic program over the budget in `units` steps. Costs round up to
    whole steps, so the plan's expected cost stays within budget.
    """
    models = list(p)
    unit = dollars / units
    cost = np.array([[int(np.ceil(c[m][t.id] / unit)) for t in tasks] for m in models])
    value = np.array([[p[m][t.id] for t in tasks] for m in models])

    # best[b]: max expected passes on the tasks after i with b steps left.
    best = np.zeros(units + 1)
    choice = np.zeros((len(tasks), units + 1), dtype=int)
    for i in reversed(range(len(tasks))):
        options = np.full((len(models), units + 1), -np.inf)
        for j in range(len(models)):
            u = cost[j, i]
            if u <= units:
                options[j, u:] = value[j, i] + best[: units + 1 - u]
        choice[i] = options.argmax(0)
        best = options.max(0)
    if best[units] == -np.inf:
        raise ValueError("budget too small to give every task a call")

    plan, b = {}, units
    for i, task in enumerate(tasks):
        j = choice[i, b]
        plan[task.id] = models[j]
        b -= cost[j, i]
    return plan


def best_mix(
    p: dict[str, float], c: dict[str, float], per_task: float
) -> dict[str, float]:
    """The share of tasks per model that maximises the average pass rate within
    budget, ignoring which task is which.

    A linear program in one share per model. Its optimum uses one model, or two
    whose costs straddle the budget per task.
    """
    best_value, best = -np.inf, {}
    for a in p:
        if c[a] <= per_task and p[a] > best_value:
            best_value, best = p[a], {a: 1.0}
        for b in p:
            if c[a] < per_task < c[b]:
                share = (c[b] - per_task) / (c[b] - c[a])
                value = share * p[a] + (1 - share) * p[b]
                if value > best_value:
                    best_value, best = value, {a: share, b: 1 - share}
    return best


def text_estimates(
    tasks: list[Task], features: dict[str, np.ndarray], table: Table, k: int = 10
) -> Table:
    """Each task's value as its text predicts it: the mean over the k most
    similar other tasks.

    Leave-one-out, so a task's own result never informs its estimate. The
    neighbours' results are known for every model, which no online router has.
    """
    vectors = np.stack([features[t.id] for t in tasks])
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    similarity = vectors @ vectors.T
    np.fill_diagonal(similarity, -np.inf)
    neighbours = np.argsort(-similarity, axis=1)[:, :k]
    return {
        m: {
            t.id: float(np.mean([table[m][tasks[j].id] for j in neighbours[i]]))
            for i, t in enumerate(tasks)
        }
        for m in table
    }
