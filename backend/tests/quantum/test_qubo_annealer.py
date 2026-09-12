"""QUBO/Ising model + simulated (quantum) annealing convergence."""

from __future__ import annotations

import numpy as np
from app.services.quantum.annealer import (
    simulated_annealing,
    simulated_quantum_annealing,
    solve,
)
from app.services.quantum.qubo import IsingModel, QUBOModel


def _random_qubo(n: int, rng: np.random.Generator) -> QUBOModel:
    m = QUBOModel(n)
    for i in range(n):
        m.add_linear(i, float(rng.normal()))
        for j in range(i + 1, n):
            if rng.random() < 0.6:
                m.add_quadratic(i, j, float(rng.normal()))
    m.add_constant(float(rng.normal()))
    return m


def test_ising_conversion_matches_qubo() -> None:
    rng = np.random.default_rng(0)
    for _ in range(25):
        n = int(rng.integers(3, 9))
        m = _random_qubo(n, rng)
        ising = IsingModel.from_qubo(m)
        for _ in range(8):
            x = rng.integers(0, 2, size=n)
            assert abs(m.energy(x) - ising.energy_spin(2 * x - 1)) < 1e-8


def test_one_hot_penalty_minimised_by_valid_assignment() -> None:
    m = QUBOModel(4)
    m.add_one_hot([0, 1, 2, 3], penalty=5.0, k=1)
    x_star, e_star = m.brute_force()
    assert int(sum(x_star)) == 1
    assert abs(e_star) < 1e-9


def test_maxcut_sa_and_sqa_reach_optimum() -> None:
    rng = np.random.default_rng(1)
    sa_hits = sqa_hits = trials = 0
    for _ in range(6):
        n = int(rng.integers(9, 14))
        w = np.zeros((n, n))
        for i in range(n):
            for j in range(i + 1, n):
                if rng.random() < 0.5:
                    w[i, j] = w[j, i] = int(rng.integers(1, 5))
        m = QUBOModel(n)
        for i in range(n):
            for j in range(i + 1, n):
                if w[i, j]:
                    m.add_linear(i, -w[i, j])
                    m.add_linear(j, -w[i, j])
                    m.add_quadratic(i, j, 2 * w[i, j])
        _, opt = m.brute_force()
        sa = simulated_annealing(m, sweeps=900, restarts=6, seed=7)
        sqa = simulated_quantum_annealing(m, sweeps=700, trotter=16, seed=7)
        trials += 1
        sa_hits += sa.best_energy <= opt + 1e-6
        sqa_hits += sqa.best_energy <= opt + 1e-6
    assert sa_hits == trials
    assert sqa_hits == trials


def test_reproducible_from_seed() -> None:
    rng = np.random.default_rng(2)
    m = _random_qubo(12, rng)
    a = simulated_quantum_annealing(m, sweeps=300, trotter=12, seed=42)
    b = simulated_quantum_annealing(m, sweeps=300, trotter=12, seed=42)
    assert a.best_bits == b.best_bits
    assert a.energy_trajectory == b.energy_trajectory


def test_solve_auto_uses_brute_force_for_tiny() -> None:
    m = _random_qubo(6, np.random.default_rng(3))
    res = solve(m, method="auto")
    assert res.method == "brute_force"
    assert res.optimal is True


def test_trajectory_is_monotone_non_increasing() -> None:
    m = _random_qubo(14, np.random.default_rng(4))
    res = simulated_annealing(m, sweeps=400, restarts=1, seed=1)
    traj = res.energy_trajectory
    assert all(traj[i + 1] <= traj[i] + 1e-9 for i in range(len(traj) - 1))
