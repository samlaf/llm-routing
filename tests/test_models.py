import random
from collections import Counter

import numpy as np

from routing.models import TIER_SHARES, hidden_tiers, simulated_models
from routing.tasks import Task, Verifier


def make_tasks(n: int, centers: int = 5):
    tasks = [Task(f"t{i}", "q", "p") for i in range(n)]
    truth = {t.id: i % 2 == 0 for i, t in enumerate(tasks)}
    rng = np.random.default_rng(0)
    means = rng.normal(scale=10, size=(centers, 8))
    features = {t.id: means[i % centers] + rng.normal(size=8) for i, t in enumerate(tasks)}
    return tasks, truth, features


def test_pass_rate_never_below_a_coin_flip():
    tasks, truth, features = make_tasks(50)
    models = simulated_models(tasks, truth, features, seed=0)
    for model in models.values():
        assert all(0.5 <= model.p_correct(t.id) <= 1.0 for t in tasks)


def test_tiers_follow_shares():
    tasks, _, features = make_tasks(100)
    counts = Counter(hidden_tiers(tasks, features, random.Random(0)).values())
    assert counts == {tier: round(share * 100) for tier, share in TIER_SHARES.items()}


def test_without_noise_easy_and_hopeless_never_share_a_topic():
    tasks, _, features = make_tasks(100, centers=2)
    tiers = hidden_tiers(tasks, features, random.Random(0), n_topics=2, topic_weight=1.0)
    topic_of = {t.id: i % 2 for i, t in enumerate(tasks)}
    topics = {
        tier: {topic_of[tid] for tid, x in tiers.items() if x == tier}
        for tier in ("easy", "hopeless")
    }
    assert topics["easy"].isdisjoint(topics["hopeless"])


def test_bigger_models_pass_more_often():
    tasks, truth, features = make_tasks(50)
    models = simulated_models(tasks, truth, features, seed=0)
    for t in tasks:
        p = {name: m.p_correct(t.id) for name, m in models.items()}
        assert p["small"] < p["medium"] < p["frontier"]


def test_answers_match_p_correct():
    tasks, truth, features = make_tasks(1)
    verifier = Verifier(truth)
    model = simulated_models(tasks, truth, features, seed=0)["medium"]
    model.rng = random.Random(1)
    trials = 20_000
    passed = sum(verifier.check("t0", model.answer(tasks[0])) for _ in range(trials))
    assert abs(passed / trials - model.p_correct("t0")) < 0.02
