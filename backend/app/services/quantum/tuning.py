"""Detection-weight tuning as a QUBO over labelled verification history.

For each rule we pick one weight *level* from a small discrete set so that the blended
score  S(event) = sum_r level(r) * fired(r, event)  best separates malicious from
benign events. One-hot per rule; objective rewards true-positive mass and penalises
false-positive mass and redundant highly-correlated rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from app.core.config import settings
from app.services.quantum.annealer import solve
from app.services.quantum.qubo import QUBOModel

DEFAULT_LEVELS = (0.0, 0.5, 1.0, 2.0)


@dataclass(slots=True)
class LabelledEvent:
    fired: set[str]
    malicious: bool


@dataclass(slots=True)
class TuningResult:
    weights: dict[str, float]
    levels: list[float]
    threshold: float
    before: dict[str, float]
    after: dict[str, float]
    solver: dict
    rules: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "weights": {k: round(v, 3) for k, v in self.weights.items()},
            "levels": list(self.levels),
            "threshold": round(self.threshold, 3),
            "before": self.before,
            "after": self.after,
            "solver": self.solver,
            "rules": self.rules,
        }


def _metrics(events: list[LabelledEvent], weights: dict[str, float], threshold: float) -> dict:
    tp = fp = tn = fn = 0
    for ev in events:
        score = sum(weights.get(r, 0.0) for r in ev.fired)
        flagged = score >= threshold
        if ev.malicious and flagged:
            tp += 1
        elif ev.malicious and not flagged:
            fn += 1
        elif not ev.malicious and flagged:
            fp += 1
        else:
            tn += 1
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
    }


def tune_weights(
    events: list[LabelledEvent],
    rules: list[str],
    *,
    levels: tuple[float, ...] = DEFAULT_LEVELS,
    current_weights: dict[str, float] | None = None,
    fp_cost: float = 1.4,
    threshold: float = 1.0,
    method: str = "auto",
    seed: int | None = None,
    sweeps: int | None = None,
) -> TuningResult:
    if not rules:
        raise ValueError("no rules to tune")
    seed = settings.quantum_seed if seed is None else seed
    current_weights = current_weights or dict.fromkeys(rules, 1.0)

    # Only tune rules that actually fire in the sample - tuning a silent rule's weight
    # is meaningless and just makes the QUBO harder to solve.
    fired_codes = {code for ev in events for code in ev.fired}
    tunable = [r for r in rules if r in fired_codes]
    untouched = {r: current_weights.get(r, 1.0) for r in rules if r not in fired_codes}
    if not tunable:
        raise ValueError("no rule fired in the labelled sample")
    rules = tunable
    n_rules = len(rules)
    n_lev = len(levels)

    n_mal = sum(1 for e in events if e.malicious) or 1
    n_ben = sum(1 for e in events if not e.malicious) or 1

    # per-rule true/false positive mass (normalised)
    tp_rate = dict.fromkeys(rules, 0.0)
    fp_rate = dict.fromkeys(rules, 0.0)
    for ev in events:
        for r in ev.fired:
            if r not in tp_rate:
                continue
            if ev.malicious:
                tp_rate[r] += 1.0 / n_mal
            else:
                fp_rate[r] += 1.0 / n_ben

    # rule co-occurrence among malicious events (redundancy)
    redundancy = np.zeros((n_rules, n_rules))
    idx = {r: i for i, r in enumerate(rules)}
    for ev in events:
        if not ev.malicious:
            continue
        present = [idx[r] for r in ev.fired if r in idx]
        for a_i in range(len(present)):
            for b_i in range(a_i + 1, len(present)):
                redundancy[present[a_i], present[b_i]] += 1.0 / n_mal

    # variables: v(r, l) = rule r takes level l
    model = QUBOModel(n_rules * n_lev)
    model.labels = [f"{rules[r]}={levels[lv_i]}" for r in range(n_rules) for lv_i in range(n_lev)]
    scale = 10.0
    lam = scale * 3.0

    for r_i, r in enumerate(rules):
        gain = tp_rate[r] - fp_cost * fp_rate[r]  # want high level when gain > 0
        for l_i, lv in enumerate(levels):
            # minimise negative of (gain * level)  => reward level when gain positive
            model.add_linear(r_i * n_lev + l_i, -scale * gain * lv)
        model.add_one_hot([r_i * n_lev + l_i for l_i in range(n_lev)], lam, k=1)

    # gently penalise two redundant rules both taking a high level (keeps the weight
    # set minimal without discarding a clean signal entirely)
    gamma = scale * 0.18
    for a in range(n_rules):
        for b in range(a + 1, n_rules):
            if redundancy[a, b] <= 0:
                continue
            for la, lva in enumerate(levels):
                for lb, lvb in enumerate(levels):
                    model.add_quadratic(
                        a * n_lev + la,
                        b * n_lev + lb,
                        gamma * redundancy[a, b] * lva * lvb,
                    )

    result = solve(model, method=method, seed=seed, sweeps=sweeps, trotter=24)
    bits = np.array(result.best_bits).reshape(n_rules, n_lev)

    tuned: dict[str, float] = dict(untouched)
    for r_i, r in enumerate(rules):
        chosen = np.where(bits[r_i] == 1)[0]
        tuned[r] = float(levels[int(chosen[0])]) if len(chosen) else current_weights.get(r, 1.0)

    # Guard: never ship a config worse than the current weights. Candidates: the QUBO
    # solution, current weights snapped to a level, and the current weights as-is.
    full_current = {**untouched, **{r: current_weights.get(r, 1.0) for r in rules}}
    snapped = {
        **untouched,
        **{r: _nearest_level(current_weights.get(r, 1.0), levels) for r in rules},
    }
    before = _metrics(events, full_current, threshold)
    candidates = [
        (tuned, _metrics(events, tuned, threshold)),
        (snapped, _metrics(events, snapped, threshold)),
        (full_current, before),
    ]
    tuned, after = max(candidates, key=lambda c: c[1]["f1"])

    return TuningResult(
        weights=tuned,
        levels=list(levels),
        threshold=threshold,
        before=before,
        after=after,
        solver=result.as_dict(),
        rules=list(rules),
    )


def _nearest_level(w: float, levels: tuple[float, ...]) -> float:
    return float(min(levels, key=lambda lv: abs(lv - w)))
