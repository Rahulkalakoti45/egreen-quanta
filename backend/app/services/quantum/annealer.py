"""Simulated Annealing and Simulated Quantum Annealing over Ising models.

SA  - single-spin-flip Metropolis with a geometric inverse-temperature schedule.
SQA - discrete-time path-integral Monte Carlo: ``trotter`` coupled replicas with an
      imaginary-time ferromagnetic coupling that grows as the transverse field
      ``gamma`` is swept high -> low. Classically emulates quantum tunnelling.

Both are deterministic given ``seed`` and report the full best-energy trajectory.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

from app.services.quantum.qubo import IsingModel, QUBOModel


@dataclass(slots=True)
class AnnealResult:
    method: str
    best_bits: list[int]
    best_energy: float
    energy_trajectory: list[float]
    sweeps: int
    restarts: int
    seed: int
    wall_ms: float
    optimal: bool | None = None
    optimality_gap: float | None = None
    params: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "method": self.method,
            "best_bits": self.best_bits,
            "best_energy": self.best_energy,
            "energy_trajectory": self.energy_trajectory,
            "sweeps": self.sweeps,
            "restarts": self.restarts,
            "seed": self.seed,
            "wall_ms": round(self.wall_ms, 2),
            "optimal": self.optimal,
            "optimality_gap": self.optimality_gap,
            "params": self.params,
        }


def _as_ising(model: IsingModel | QUBOModel) -> IsingModel:
    return model if isinstance(model, IsingModel) else IsingModel.from_qubo(model)


def _beta_schedule(beta0: float, beta1: float, steps: int) -> np.ndarray:
    return np.geomspace(max(beta0, 1e-6), max(beta1, beta0 + 1e-6), steps)


def simulated_annealing(
    model: IsingModel | QUBOModel,
    *,
    sweeps: int = 2000,
    restarts: int = 8,
    beta0: float = 0.1,
    beta1: float = 10.0,
    seed: int = 1337,
) -> AnnealResult:
    ising = _as_ising(model)
    n = ising.n
    rng = np.random.default_rng(seed)
    start = time.perf_counter()

    betas = _beta_schedule(beta0, beta1, sweeps)
    best_energy = np.inf
    best_s = np.ones(n, dtype=np.int64)
    trajectory: list[float] = []

    for r in range(max(1, restarts)):
        s = rng.choice(np.array([-1, 1], dtype=np.int64), size=n)
        field_vec = 2.0 * (ising.J @ s) + ising.h
        energy = ising.energy_spin(s)
        for sweep in range(sweeps):
            beta = betas[sweep]
            order = rng.permutation(n)
            for i in order:
                delta = -2.0 * s[i] * field_vec[i]
                if delta <= 0.0 or rng.random() < np.exp(-beta * delta):
                    s[i] = -s[i]
                    field_vec += 4.0 * s[i] * ising.J[i]  # s[i] already flipped
                    energy += delta
            if energy < best_energy:
                best_energy, best_s = energy, s.copy()
            if r == 0:
                trajectory.append(float(best_energy))

    wall_ms = (time.perf_counter() - start) * 1000.0
    return _finalize(
        ising,
        model,
        "simulated_annealing",
        best_s,
        float(best_energy),
        trajectory,
        sweeps,
        max(1, restarts),
        seed,
        wall_ms,
        {"beta0": beta0, "beta1": beta1},
    )


def simulated_quantum_annealing(
    model: IsingModel | QUBOModel,
    *,
    sweeps: int = 1500,
    trotter: int = 20,
    beta: float = 8.0,
    gamma0: float = 3.0,
    gamma1: float = 1e-3,
    seed: int = 1337,
) -> AnnealResult:
    ising = _as_ising(model)
    n = ising.n
    p = max(2, trotter)
    rng = np.random.default_rng(seed)
    start = time.perf_counter()

    gammas = np.linspace(gamma0, gamma1, sweeps)
    replicas = rng.choice(np.array([-1, 1], dtype=np.int64), size=(p, n))
    fields = np.array([2.0 * (ising.J @ replicas[k]) + ising.h for k in range(p)])

    best_energy = np.inf
    best_s = replicas[0].copy()
    trajectory: list[float] = []

    for sweep in range(sweeps):
        gamma = max(gammas[sweep], 1e-9)
        # imaginary-time coupling; -> large as gamma -> 0, chaining replicas together
        jperp = -0.5 * p / beta * np.log(np.tanh(beta * gamma / p) + 1e-300)

        for k in range(p):
            kp, km = (k + 1) % p, (k - 1) % p
            neighbour = replicas[kp] + replicas[km]
            order = rng.permutation(n)
            for i in order:
                d_classical = (-2.0 * replicas[k, i] * fields[k, i]) / p
                d_kinetic = 2.0 * jperp * replicas[k, i] * neighbour[i]
                delta = d_classical + d_kinetic
                if delta <= 0.0 or rng.random() < np.exp(-beta * delta):
                    replicas[k, i] = -replicas[k, i]
                    fields[k] += 4.0 * replicas[k, i] * ising.J[i]

        # best classical config across replicas this sweep
        energies = np.array([ising.energy_spin(replicas[k]) for k in range(p)])
        k_star = int(np.argmin(energies))
        if energies[k_star] < best_energy:
            best_energy, best_s = float(energies[k_star]), replicas[k_star].copy()
        trajectory.append(float(best_energy))

    wall_ms = (time.perf_counter() - start) * 1000.0
    return _finalize(
        ising,
        model,
        "simulated_quantum_annealing",
        best_s,
        float(best_energy),
        trajectory,
        sweeps,
        1,
        seed,
        wall_ms,
        {"trotter": p, "beta": beta, "gamma0": gamma0, "gamma1": gamma1},
    )


def _finalize(
    ising: IsingModel,
    original: IsingModel | QUBOModel,
    method: str,
    best_s: np.ndarray,
    best_energy: float,
    trajectory: list[float],
    sweeps: int,
    restarts: int,
    seed: int,
    wall_ms: float,
    params: dict,
) -> AnnealResult:
    bits = ((best_s + 1) // 2).astype(int).tolist()
    optimal: bool | None = None
    gap: float | None = None
    if isinstance(original, QUBOModel) and original.can_brute_force():
        _, opt_e = original.brute_force()
        gap = round(best_energy - opt_e, 9)
        optimal = abs(gap) < 1e-6
    return AnnealResult(
        method=method,
        best_bits=bits,
        best_energy=round(best_energy, 9),
        energy_trajectory=[round(e, 6) for e in trajectory],
        sweeps=sweeps,
        restarts=restarts,
        seed=seed,
        wall_ms=wall_ms,
        optimal=optimal,
        optimality_gap=gap,
        params=params,
    )


def solve(
    model: QUBOModel,
    *,
    method: str = "auto",
    seed: int = 1337,
    sweeps: int | None = None,
    restarts: int = 8,
    trotter: int = 20,
) -> AnnealResult:
    """Dispatch: exact for tiny models, otherwise the requested heuristic.

    ``auto`` brute-forces n <= 18, else runs SA *and* SQA and keeps the lower-energy
    result (the SQA convergence trajectory is retained for display).
    """
    if method == "auto":
        method = "brute" if model.n <= 18 else "best"

    if method == "brute" and model.can_brute_force():
        start = time.perf_counter()
        x, e = model.brute_force()
        return AnnealResult(
            method="brute_force",
            best_bits=[int(v) for v in x],
            best_energy=round(float(e), 9),
            energy_trajectory=[round(float(e), 6)],
            sweeps=0,
            restarts=1,
            seed=seed,
            wall_ms=(time.perf_counter() - start) * 1000.0,
            optimal=True,
            optimality_gap=0.0,
        )
    if method == "sa":
        return simulated_annealing(model, sweeps=sweeps or 2000, restarts=restarts, seed=seed)
    if method == "sqa":
        return simulated_quantum_annealing(model, sweeps=sweeps or 1500, trotter=trotter, seed=seed)

    # method == "best" (or "brute" on an oversized model): race SA and SQA.
    sa = simulated_annealing(model, sweeps=sweeps or 2200, restarts=max(restarts, 12), seed=seed)
    sqa = simulated_quantum_annealing(model, sweeps=sweeps or 1600, trotter=trotter, seed=seed)
    winner, loser = (sqa, sa) if sqa.best_energy <= sa.best_energy else (sa, sqa)
    winner.method = f"{winner.method}+best"
    winner.params = {**winner.params, "runner_up": {loser.method: loser.best_energy}}
    return winner
