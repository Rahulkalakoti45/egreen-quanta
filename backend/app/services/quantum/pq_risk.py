"""Quantum Exposure Score (QES) and the PQC migration planner (Module 4 hero).

QES estimates how exposed a signature/certificate is to a cryptographically-relevant
quantum computer (CRQC) and to "harvest-now, decrypt-later". The migration planner then
uses simulated quantum annealing over a scheduling QUBO to order a portfolio of signing
identities into migration waves that minimise cumulative risk-exposure-time under a
per-wave capacity budget.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import numpy as np

from app.core.config import settings
from app.services.quantum.annealer import solve
from app.services.quantum.qubo import QUBOModel

# --- algorithm families ------------------------------------------------------

_SHOR_BREAKABLE = {"rsa", "dsa", "ec", "ecdsa", "ecdh", "ed25519", "ed448", "dh", "elgamal"}
_POST_QUANTUM = {
    "ml-dsa",
    "mldsa",
    "dilithium",
    "slh-dsa",
    "slhdsa",
    "sphincs+",
    "sphincs",
    "falcon",
    "lms",
    "xmss",
    "hss",
    "ml-kem",
    "mlkem",
    "kyber",
}

# Symmetric-equivalent classical strength (bits) -> relative CRQC feasibility in [0, 1].
# RSA/FFC via Shor is "easy" once a CRQC exists; ECC needs far fewer logical qubits, so a
# given classical strength is *sooner* broken for ECC than RSA.
_RSA_STRENGTH = {1024: 1.00, 2048: 0.90, 3072: 0.78, 4096: 0.66, 7680: 0.42, 15360: 0.22}
_ECC_STRENGTH = {256: 0.95, 384: 0.82, 521: 0.68}

_EXPOSURE = {"public": 1.0, "transmitted": 0.75, "internal": 0.35, "sealed": 0.1}

_WEIGHTS = {"algo": 1.0, "strength": 0.9, "longevity": 0.8, "exposure": 0.6}


@dataclass(slots=True)
class QESInput:
    algo: str = "rsa"
    key_bits: int | None = None
    curve: str | None = None
    data_lifetime_years: float = 7.0
    exposure: str = "transmitted"
    label: str = ""


@dataclass(slots=True)
class QESResult:
    qes: float
    band: str  # immediate | plan | monitor | ok
    algo_factor: float
    strength_factor: float
    longevity_factor: float
    exposure_factor: float
    recommendation: str
    assumptions: dict
    label: str = ""

    def as_dict(self) -> dict:
        return {
            "qes": self.qes,
            "band": self.band,
            "algo_factor": round(self.algo_factor, 3),
            "strength_factor": round(self.strength_factor, 3),
            "longevity_factor": round(self.longevity_factor, 3),
            "exposure_factor": round(self.exposure_factor, 3),
            "recommendation": self.recommendation,
            "assumptions": self.assumptions,
            "label": self.label,
        }


def _interp(table: dict[int, float], value: int) -> float:
    from itertools import pairwise

    keys = sorted(table)
    if value <= keys[0]:
        return table[keys[0]]
    if value >= keys[-1]:
        return table[keys[-1]]
    for lo, hi in pairwise(keys):
        if lo <= value <= hi:
            t = (value - lo) / (hi - lo)
            return table[lo] + t * (table[hi] - table[lo])
    return table[keys[-1]]


def _algo_norm(algo: str) -> str:
    return algo.strip().lower().replace("_", "-").split("-with-")[0]


def score_qes(inp: QESInput, *, assumptions: dict | None = None) -> QESResult:
    now_year = dt.datetime.now(dt.UTC).year
    qc_year = int((assumptions or {}).get("qc_year", settings.qc_year_assumption))
    horizon = max(1, qc_year - now_year)
    weights = {**_WEIGHTS, **(assumptions or {}).get("weights", {})}

    algo = _algo_norm(inp.algo)

    if algo in _POST_QUANTUM:
        algo_factor = 0.0
        strength_factor = 0.0
    elif algo in _SHOR_BREAKABLE or algo.startswith(("rsa", "ec", "ed", "dsa")):
        algo_factor = 1.0
        if algo.startswith("ec") or algo.startswith("ed"):
            bits = 256
            if inp.curve:
                for c, b in (("521", 521), ("384", 384), ("256", 256), ("25519", 256)):
                    if c in inp.curve:
                        bits = b
                        break
            strength_factor = _interp(_ECC_STRENGTH, bits)
        else:
            strength_factor = _interp(_RSA_STRENGTH, int(inp.key_bits or 2048))
    else:
        algo_factor = 0.5
        strength_factor = 0.5

    # HNDL: does the data need to stay trustworthy past the likely CRQC arrival?
    longevity_factor = float(np.clip(inp.data_lifetime_years / horizon, 0.0, 1.0))
    exposure_factor = _EXPOSURE.get(inp.exposure.lower(), 0.5)

    # ``algo_factor`` is a hard gate: a post-quantum algorithm is not at risk no matter
    # how long-lived or exposed the data is. Strength / longevity / exposure then set
    # *how* urgent a Shor-breakable signature's migration is, via a weighted mean.
    ctx_num = (
        weights["strength"] * strength_factor
        + weights["longevity"] * longevity_factor
        + weights["exposure"] * exposure_factor
    )
    ctx_den = weights["strength"] + weights["longevity"] + weights["exposure"]
    context = ctx_num / ctx_den if ctx_den else 0.0

    qes = round(100.0 * algo_factor * (0.2 + 0.8 * context), 1)

    band = "ok" if qes < 25 else "monitor" if qes < 50 else "plan" if qes < 75 else "immediate"
    rec = _recommendation(algo, band)

    return QESResult(
        qes=qes,
        band=band,
        algo_factor=algo_factor,
        strength_factor=strength_factor,
        longevity_factor=longevity_factor,
        exposure_factor=exposure_factor,
        recommendation=rec,
        assumptions={"qc_year": qc_year, "horizon_years": horizon, "weights": weights},
        label=inp.label,
    )


def _recommendation(algo: str, band: str) -> str:
    if algo in _POST_QUANTUM:
        return "Already post-quantum. Maintain crypto-agility."
    target = "ML-DSA (FIPS 204) for general signing, or SLH-DSA / LMS for firmware & code signing"
    if band == "immediate":
        return f"Migrate now to {target}; re-sign long-lived artifacts."
    if band == "plan":
        return f"Schedule migration to {target} within the current planning cycle."
    if band == "monitor":
        return f"Track NIST guidance; prepare a migration path to {target}."
    return "Low exposure. Revisit if data lifetime or CRQC estimates change."


# --- migration planner (scheduling QUBO) ------------------------------------


@dataclass(slots=True)
class MigrationIdentity:
    name: str
    qes: float
    criticality: int = 3  # 1..5
    effort: int = 2  # capacity units to migrate this identity
    label: str = ""


@dataclass(slots=True)
class MigrationPlan:
    waves: list[list[dict]]
    wave_capacity: int
    total_waves: int
    cumulative_exposure: float
    baseline_exposure: float
    improvement_pct: float
    solver: dict
    unassigned: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "waves": self.waves,
            "wave_capacity": self.wave_capacity,
            "total_waves": self.total_waves,
            "cumulative_exposure": round(self.cumulative_exposure, 2),
            "baseline_exposure": round(self.baseline_exposure, 2),
            "improvement_pct": round(self.improvement_pct, 1),
            "solver": self.solver,
            "unassigned": self.unassigned,
            "notes": self.notes,
        }


def plan_migration(
    identities: list[MigrationIdentity],
    *,
    waves: int = 4,
    wave_capacity: int | None = None,
    method: str = "auto",
    seed: int | None = None,
    sweeps: int | None = None,
) -> MigrationPlan:
    n = len(identities)
    if n == 0:
        raise ValueError("no identities to plan")
    w = max(1, waves)
    total_effort = sum(max(1, i.effort) for i in identities)
    cap = wave_capacity or max(1, -(-total_effort // w))  # ceil division
    seed = settings.quantum_seed if seed is None else seed

    # variable index: v(i, k) = i * w + k  ->  identity i migrated in wave k (0-based)
    model = QUBOModel(n * w)
    model.labels = [f"{identities[i].name}@wave{k + 1}" for i in range(n) for k in range(w)]

    weight_scale = max(1.0, max(i.qes for i in identities))
    lam = 4.0 * weight_scale  # one-hot penalty
    mu = 0.6 * weight_scale / max(1, cap)  # capacity penalty

    # objective: migrate high risk*criticality early  (wave index k+1)
    for i, ident in enumerate(identities):
        risk = ident.qes * (0.6 + 0.1 * np.clip(ident.criticality, 1, 5))
        for k in range(w):
            model.add_linear(i * w + k, risk * (k + 1))
        # exactly one wave per identity
        model.add_one_hot([i * w + k for k in range(w)], lam, k=1)

    # per-wave capacity: penalise (sum effort*x - cap)^2
    for k in range(w):
        idxs = [i * w + k for i in range(n)]
        efforts = [max(1, identities[i].effort) for i in range(n)]
        for a, i_idx in enumerate(idxs):
            e_i = efforts[a]
            model.add_linear(i_idx, mu * (e_i * e_i - 2 * cap * e_i))
            for b in range(a + 1, len(idxs)):
                model.add_quadratic(i_idx, idxs[b], mu * 2 * e_i * efforts[b])
        model.add_constant(mu * cap * cap)

    result = solve(model, method=method, seed=seed, sweeps=sweeps, trotter=24)
    bits = np.array(result.best_bits).reshape(n, w)

    wave_lists: list[list[dict]] = [[] for _ in range(w)]
    unassigned: list[str] = []
    for i, ident in enumerate(identities):
        chosen = np.where(bits[i] == 1)[0]
        if len(chosen) == 0:
            unassigned.append(ident.name)
            continue
        k = int(chosen[0])  # if the penalty failed and >1, take the earliest
        wave_lists[k].append(
            {
                "name": ident.name,
                "qes": ident.qes,
                "criticality": ident.criticality,
                "effort": ident.effort,
                "label": ident.label,
            }
        )

    cumulative = sum(member["qes"] * (k + 1) for k, wl in enumerate(wave_lists) for member in wl)
    # baseline: risk-sorted greedy fill by capacity
    baseline = _greedy_baseline(identities, w, cap)
    improvement = 100.0 * (baseline - cumulative) / baseline if baseline > 0 else 0.0

    notes: list[str] = []
    if unassigned:
        notes.append(f"{len(unassigned)} identities unplaced - increase waves or capacity.")
    load = [sum(m["effort"] for m in wl) for wl in wave_lists]
    if any(load_k > cap for load_k in load):
        notes.append(f"Some waves exceed capacity {cap} (soft constraint): loads {load}.")

    return MigrationPlan(
        waves=wave_lists,
        wave_capacity=cap,
        total_waves=w,
        cumulative_exposure=cumulative,
        baseline_exposure=baseline,
        improvement_pct=improvement,
        solver=result.as_dict(),
        unassigned=unassigned,
        notes=notes,
    )


def _greedy_baseline(identities: list[MigrationIdentity], waves: int, cap: int) -> float:
    order = sorted(identities, key=lambda i: -i.qes)
    load = [0] * waves
    total = 0.0
    for ident in order:
        placed = False
        for k in range(waves):
            if load[k] + max(1, ident.effort) <= cap:
                load[k] += max(1, ident.effort)
                total += ident.qes * (k + 1)
                placed = True
                break
        if not placed:
            total += ident.qes * waves
    return total
