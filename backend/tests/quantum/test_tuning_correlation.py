"""Detection-weight tuning + correlation QUBO."""

from __future__ import annotations

import numpy as np
from app.services.quantum.correlation_qubo import correlate_qubo
from app.services.quantum.tuning import LabelledEvent, tune_weights


def _synthetic(rng: np.random.Generator, n: int = 220) -> list[LabelledEvent]:
    strong = {"T01": 0.75, "T09": 0.55, "T06": 0.45, "T03": 0.3}
    noisy = {"T05": 0.5, "T13": 0.55, "T02": 0.15}
    out = []
    for _ in range(n):
        mal = rng.random() < 0.4
        table = strong if mal else noisy
        fired = {r for r, p in table.items() if rng.random() < p}
        if not mal:
            fired |= {r for r in ("T13", "T05") if rng.random() < 0.4}
        out.append(LabelledEvent(fired=fired, malicious=mal))
    return out


def test_tuning_improves_f1() -> None:
    rng = np.random.default_rng(3)
    events = _synthetic(rng)
    rules = ["T01", "T02", "T03", "T05", "T06", "T09", "T13"]
    res = tune_weights(events, rules, seed=7)
    assert res.after["f1"] >= res.before["f1"] + 0.05
    # a noisy rule is weighted no higher than a discriminative one
    assert res.weights["T05"] <= res.weights["T01"]
    assert res.weights["T02"] <= res.weights["T01"]
    # the strongest signal keeps a positive weight
    assert res.weights["T01"] > 0


def test_tuning_is_reproducible() -> None:
    rng = np.random.default_rng(9)
    events = _synthetic(rng)
    rules = ["T01", "T03", "T06", "T09", "T13"]
    a = tune_weights(events, rules, seed=11)
    b = tune_weights(events, rules, seed=11)
    assert a.weights == b.weights


def test_correlation_separates_two_clusters() -> None:
    rng = np.random.default_rng(3)
    n = 10
    sim = np.zeros((n, n))
    for grp in (range(0, 4), range(4, 8)):
        for i in grp:
            for j in grp:
                if i < j:
                    sim[i, j] = sim[j, i] = rng.uniform(0.5, 0.9)
    res = correlate_qubo(sim, seed=7)
    assert len(res.clusters) == 2
    members = sorted(sorted(c) for c in res.clusters)
    assert members == [[0, 1, 2, 3], [4, 5, 6, 7]]
    assert sorted(res.singletons) == [8, 9]


def test_correlation_reports_both_modularities() -> None:
    rng = np.random.default_rng(5)
    n = 8
    sim = np.zeros((n, n))
    for i in range(4):
        for j in range(i + 1, 4):
            sim[i, j] = sim[j, i] = rng.uniform(0.6, 0.9)
    res = correlate_qubo(sim, seed=7)
    d = res.as_dict()
    assert "qubo_modularity" in d and "baseline_modularity" in d
