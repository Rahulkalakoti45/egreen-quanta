"""Quantum-inspired incident grouping: dense-cluster extraction on the event graph.

For a window of events with pairwise similarity ``w_ij``, repeatedly pull out the
subset S maximising  sum_{i<j in S} w_ij - gamma * |S|  (a resolution-controlled
densest-subgraph / weighted-clique objective), each S becoming one incident. Compared
against the Module 3 greedy baseline via an internal-density metric.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from app.core.config import settings
from app.services.quantum.annealer import solve
from app.services.quantum.qubo import QUBOModel

_MIN_CLUSTER = 2
_MAX_CLUSTERS = 12


@dataclass(slots=True)
class QuboCluster:
    members: list[int]
    internal_weight: float
    density: float


@dataclass(slots=True)
class CorrelationResult:
    clusters: list[list[int]]
    cluster_density: list[float]
    singletons: list[int]
    qubo_modularity: float
    baseline_modularity: float
    solver_runs: list[dict]
    labels: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "clusters": self.clusters,
            "cluster_density": [round(d, 4) for d in self.cluster_density],
            "singletons": self.singletons,
            "qubo_modularity": round(self.qubo_modularity, 4),
            "baseline_modularity": round(self.baseline_modularity, 4),
            "solver_runs": self.solver_runs,
            "labels": self.labels,
        }


def _modularity(sim: np.ndarray, groups: list[list[int]]) -> float:
    total = sim.sum() / 2.0 or 1.0
    deg = sim.sum(axis=1)
    q = 0.0
    for g in groups:
        for i in g:
            for j in g:
                if i < j:
                    q += sim[i, j] - deg[i] * deg[j] / (2.0 * total)
    return q / total


def correlate_qubo(
    sim: np.ndarray,
    *,
    gamma: float | None = None,
    method: str = "auto",
    seed: int | None = None,
    labels: list[str] | None = None,
) -> CorrelationResult:
    sim = np.array(sim, dtype=np.float64)
    n = sim.shape[0]
    if sim.shape != (n, n):
        raise ValueError("similarity matrix must be square")
    np.fill_diagonal(sim, 0.0)
    seed = settings.quantum_seed if seed is None else seed
    if gamma is None:
        nz = sim[sim > 0]
        # a low percentile: pairs weaker than this are a *cost* to include together,
        # which stops the solver from merging two disjoint dense clusters.
        gamma = float(np.percentile(nz, 25)) if nz.size else 0.2

    remaining = set(range(n))
    clusters: list[list[int]] = []
    densities: list[float] = []
    solver_runs: list[dict] = []

    for _ in range(_MAX_CLUSTERS):
        if len(remaining) < _MIN_CLUSTER:
            break
        idx = sorted(remaining)
        sub = sim[np.ix_(idx, idx)]
        m = len(idx)

        model = QUBOModel(m)
        model.labels = [str(labels[i]) if labels else f"e{i}" for i in idx]
        # maximise sum_{i<j in S} (w_ij - gamma)  ->  minimise its negative
        for a in range(m):
            for b in range(a + 1, m):
                model.add_quadratic(a, b, -(sub[a, b] - gamma))

        result = solve(model, method=method, seed=seed, sweeps=900, trotter=20)
        solver_runs.append(result.as_dict())
        picked_local = [a for a, bit in enumerate(result.best_bits) if bit == 1]
        picked = [idx[a] for a in picked_local]

        if len(picked) < _MIN_CLUSTER:
            break
        internal = sum(sim[i, j] for a, i in enumerate(picked) for j in picked[a + 1 :])
        if internal <= 0:
            break
        pairs = len(picked) * (len(picked) - 1) / 2
        clusters.append(sorted(picked))
        densities.append(internal / pairs if pairs else 0.0)
        remaining -= set(picked)

    singletons = sorted(remaining)
    all_groups = clusters + [[s] for s in singletons]
    qubo_mod = _modularity(sim, all_groups)
    baseline_mod = _modularity(sim, _greedy_groups(sim))

    return CorrelationResult(
        clusters=clusters,
        cluster_density=densities,
        singletons=singletons,
        qubo_modularity=qubo_mod,
        baseline_modularity=baseline_mod,
        solver_runs=solver_runs,
        labels=[str(labels[i]) for i in range(n)] if labels else [f"e{i}" for i in range(n)],
    )


def _greedy_groups(sim: np.ndarray, link: float = 0.34) -> list[list[int]]:
    """Single-linkage grouping at threshold ``link`` (mirrors the Module 3 heuristic)."""
    n = sim.shape[0]
    parent = list(range(n))

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for i in range(n):
        for j in range(i + 1, n):
            if sim[i, j] >= link:
                parent[find(i)] = find(j)

    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return list(groups.values())
