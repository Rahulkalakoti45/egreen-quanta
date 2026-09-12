"""QUBO / Ising model construction and exact evaluation.

QUBO:  minimise  E(x) = x^T Q x   with  x in {0, 1}^n   (Q upper-triangular, diagonal = linear)
Ising: minimise  E(s) = s^T J s + h.s + c   with  s in {-1, +1}^n   via  x = (1 + s) / 2
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

_BRUTE_FORCE_MAX_N = 22


class QUBOModel:
    """Dense upper-triangular QUBO. Diagonal entries are the linear coefficients."""

    def __init__(self, n: int) -> None:
        if n <= 0:
            raise ValueError("n must be positive")
        self.n = n
        self.Q = np.zeros((n, n), dtype=np.float64)
        self.offset = 0.0
        self.labels: list[str] = [f"x{i}" for i in range(n)]

    # ---- construction ------------------------------------------------------

    def add_linear(self, i: int, w: float) -> None:
        self.Q[i, i] += w

    def add_quadratic(self, i: int, j: int, w: float) -> None:
        if i == j:
            self.Q[i, i] += w
            return
        a, b = (i, j) if i < j else (j, i)
        self.Q[a, b] += w

    def add_constant(self, c: float) -> None:
        self.offset += c

    def add_one_hot(self, indices: list[int], penalty: float, k: int = 1) -> None:
        """Penalise ``(sum_{i in indices} x_i - k)^2`` with weight ``penalty``.

        Expands to linear terms ``penalty*(1 - 2k)`` on each x_i and quadratic
        ``2*penalty`` on each pair, plus a constant ``penalty*k^2``.
        """
        for i in indices:
            self.add_linear(i, penalty * (1 - 2 * k))
        for a_idx, i in enumerate(indices):
            for j in indices[a_idx + 1 :]:
                self.add_quadratic(i, j, 2 * penalty)
        self.add_constant(penalty * k * k)

    # ---- evaluation ------------------------------------------------------

    def energy(self, x: np.ndarray) -> float:
        x = np.asarray(x, dtype=np.float64).reshape(-1)
        return float(x @ self.Q @ x + self.offset)

    def energies(self, xs: np.ndarray) -> np.ndarray:
        """Vectorised energy for a (m, n) batch of bitstrings."""
        xs = np.asarray(xs, dtype=np.float64)
        return np.einsum("mi,ij,mj->m", xs, self.Q, xs) + self.offset

    def to_ising(self) -> tuple[np.ndarray, np.ndarray, float]:
        """Return (h, J, offset) for the ``x = (1 + s) / 2`` substitution.

        Energy convention: ``E(s) = s @ J @ s + h @ s + offset`` with J symmetric,
        zero diagonal (so ``s @ J @ s`` double-counts each pair). Verified against
        ``QUBOModel.energy`` in the test-suite for random instances.
        """
        lin = np.diag(self.Q).astype(np.float64)
        upper = np.triu(self.Q, k=1)  # off-diagonal upper-triangular coefficients
        u_sym = upper + upper.T  # symmetric, zero diagonal

        h = lin / 2.0 + u_sym.sum(axis=1) / 4.0
        j_mat = u_sym / 8.0
        const = self.offset + lin.sum() / 2.0 + upper.sum() / 4.0
        return h, j_mat, float(const)

    def brute_force(self) -> tuple[np.ndarray, float]:
        if self.n > _BRUTE_FORCE_MAX_N:
            raise ValueError(f"brute force limited to n <= {_BRUTE_FORCE_MAX_N} (got {self.n})")
        best_x = np.zeros(self.n, dtype=np.int8)
        best_e = self.energy(best_x)
        for mask in range(1, 1 << self.n):
            x = np.array([(mask >> b) & 1 for b in range(self.n)], dtype=np.int8)
            e = self.energy(x)
            if e < best_e:
                best_e, best_x = e, x
        return best_x, best_e

    def can_brute_force(self) -> bool:
        return self.n <= _BRUTE_FORCE_MAX_N


@dataclass(slots=True)
class IsingModel:
    h: np.ndarray
    J: np.ndarray
    offset: float = 0.0
    labels: list[str] = field(default_factory=list)

    @property
    def n(self) -> int:
        return int(self.h.shape[0])

    def energy_spin(self, s: np.ndarray) -> float:
        s = np.asarray(s, dtype=np.float64).reshape(-1)
        return float(s @ self.J @ s + self.h @ s + self.offset)

    def local_field(self, s: np.ndarray) -> np.ndarray:
        """dE/ds_i contribution used by single-spin-flip Metropolis: 2*(J s)_i + h_i."""
        return 2.0 * (self.J @ s) + self.h

    def bits(self, s: np.ndarray) -> np.ndarray:
        return ((np.asarray(s) + 1) // 2).astype(np.int8)

    @classmethod
    def from_qubo(cls, model: QUBOModel) -> IsingModel:
        h, j, c = model.to_ising()
        return cls(h=h, J=j, offset=c, labels=list(model.labels))
