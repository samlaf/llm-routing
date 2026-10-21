"""Frozen text embeddings of task specs."""

import numpy as np
from fastembed import TextEmbedding

from routing.tasks import DATA, Task

MODEL = "BAAI/bge-small-en-v1.5"
CACHE = DATA.with_name(f"{DATA.name}.{MODEL.split('/')[1]}.npz")


def embed(tasks: list[Task], cache=CACHE) -> dict[str, np.ndarray]:
    # The model is frozen, so vectors are computed once and kept on disk.
    # Tests and replayed runs then need neither the model nor the network.
    if cache.exists():
        saved = np.load(cache)
        vectors = dict(zip(saved["ids"].tolist(), saved["vectors"]))
        if all(t.id in vectors for t in tasks):
            return {t.id: vectors[t.id] for t in tasks}

    model = TextEmbedding(MODEL)
    vectors = np.array(list(model.embed([t.spec for t in tasks])))
    np.savez(cache, ids=np.array([t.id for t in tasks]), vectors=vectors)
    return {t.id: v for t, v in zip(tasks, vectors)}
