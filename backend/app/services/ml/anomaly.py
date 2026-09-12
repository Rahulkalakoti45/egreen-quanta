"""scikit-learn anomaly models with a uniform score(X) -> [0,1] interface."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

SUPPORTED_ALGOS = ("isolation_forest", "one_class_svm")


@dataclass(slots=True)
class TrainedModel:
    algo: str
    estimator: Any
    scaler: Any
    score_min: float
    score_max: float
    feature_schema_version: int
    params: dict = field(default_factory=dict)

    def score(self, x: np.ndarray) -> np.ndarray:
        """Return anomaly scores in [0, 1] (1 = most anomalous)."""
        x = np.atleast_2d(np.asarray(x, dtype=np.float64))
        xs = self.scaler.transform(x)
        raw = -self.estimator.score_samples(xs)  # higher = more anomalous
        span = self.score_max - self.score_min
        if span <= 1e-9:
            return np.full(raw.shape[0], 0.5)
        return np.clip((raw - self.score_min) / span, 0.0, 1.0)

    def save(self, path: str | Path) -> str:
        import joblib

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "algo": self.algo,
                "estimator": self.estimator,
                "scaler": self.scaler,
                "score_min": self.score_min,
                "score_max": self.score_max,
                "feature_schema_version": self.feature_schema_version,
                "params": self.params,
            },
            path,
        )
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @classmethod
    def load(cls, path: str | Path) -> TrainedModel:
        import joblib

        blob = joblib.load(Path(path))
        return cls(**blob)


def train_model(
    x: np.ndarray,
    *,
    algo: str = "isolation_forest",
    feature_schema_version: int,
    contamination: float = 0.08,
    random_state: int = 1337,
    params: dict | None = None,
) -> tuple[TrainedModel, dict]:
    """Fit a model on ``x`` (n_samples, n_features). Returns (model, metrics)."""
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler
    from sklearn.svm import OneClassSVM

    if algo not in SUPPORTED_ALGOS:
        raise ValueError(f"unsupported algo {algo!r}; choose one of {SUPPORTED_ALGOS}")
    if x.shape[0] < 20:
        raise ValueError("need at least 20 samples to train an anomaly model")

    params = params or {}
    scaler = StandardScaler().fit(x)
    xs = scaler.transform(x)

    if algo == "isolation_forest":
        est = IsolationForest(
            n_estimators=int(params.get("n_estimators", 200)),
            contamination=contamination,
            random_state=random_state,
            n_jobs=1,
        ).fit(xs)
    else:
        est = OneClassSVM(
            kernel=params.get("kernel", "rbf"),
            nu=float(params.get("nu", contamination)),
            gamma=params.get("gamma", "scale"),
        ).fit(xs)

    raw = -est.score_samples(xs)
    lo, hi = float(np.percentile(raw, 1)), float(np.percentile(raw, 99))
    model = TrainedModel(
        algo=algo,
        estimator=est,
        scaler=scaler,
        score_min=lo,
        score_max=hi if hi > lo else lo + 1e-6,
        feature_schema_version=feature_schema_version,
        params={"contamination": contamination, **params},
    )
    scores = model.score(x)
    metrics = {
        "n_train": int(x.shape[0]),
        "contamination": contamination,
        "mean_score": round(float(scores.mean()), 4),
        "p95_score": round(float(np.percentile(scores, 95)), 4),
        "flagged_frac": round(float((scores >= 0.7).mean()), 4),
    }
    return model, metrics
