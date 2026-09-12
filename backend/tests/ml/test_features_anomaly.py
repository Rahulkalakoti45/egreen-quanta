"""Feature extraction + anomaly model training."""

from __future__ import annotations

import datetime as dt

import numpy as np
from app.services.ml.anomaly import TrainedModel, train_model
from app.services.ml.features import (
    FEATURE_DIM,
    FEATURE_SCHEMA_VERSION,
    event_to_vector,
)

_NOW = dt.datetime(2026, 9, 1, 14, 30, tzinfo=dt.UTC)


def _vec(**over) -> np.ndarray:
    base = {
        "key_type": "rsa",
        "key_bits": 2048,
        "curve": None,
        "hash_alg": "sha256",
        "envelope_type": "raw",
        "verdict": "valid",
        "chain_status": "trusted",
        "signing_time": None,
        "tsa_present": False,
        "created_at": _NOW,
        "finding_categories": [],
    }
    base.update(over)
    return event_to_vector(**base)


def test_vector_dimension_and_determinism() -> None:
    v1 = _vec()
    v2 = _vec()
    assert v1.shape == (FEATURE_DIM,)
    assert np.array_equal(v1, v2)


def test_handles_missing_and_unknown_values() -> None:
    v = _vec(key_type=None, key_bits=None, curve="brainpoolP256r1", hash_alg="whirlpool")
    assert v.shape == (FEATURE_DIM,)
    assert np.isfinite(v).all()


def test_finding_categories_counted() -> None:
    v = _vec(finding_categories=["forgery", "forgery", "chain"])
    # last block is finding_count + per-category counts
    assert v[-8:].sum() == 3  # 8 categories, total count 3 across them
    assert v[FEATURE_DIM - 9] == 3.0  # finding_count feature


def test_train_and_score_separates_outliers() -> None:
    rng = np.random.default_rng(0)
    normal = np.vstack(
        [
            _vec(
                key_bits=int(rng.choice([2048, 3072])),
                verdict="valid",
                created_at=_NOW.replace(hour=int(rng.integers(8, 18))),
            )
            for _ in range(120)
        ]
    )
    outliers = np.vstack(
        [
            _vec(
                key_type="dsa",
                key_bits=1024,
                hash_alg="md5",
                verdict="invalid",
                chain_status="error",
                finding_categories=["forgery", "weak_crypto", "chain"],
            )
            for _ in range(8)
        ]
    )
    x = np.vstack([normal, outliers])
    model, metrics = train_model(
        x, algo="isolation_forest", feature_schema_version=FEATURE_SCHEMA_VERSION
    )
    scores = model.score(x)
    assert scores[-8:].mean() > scores[:120].mean() + 0.2
    assert metrics["n_train"] == 128


def test_model_save_load_roundtrip(tmp_path) -> None:
    x = np.vstack([_vec(key_bits=b) for b in (2048, 3072, 4096) for _ in range(20)])
    model, _ = train_model(
        x, algo="isolation_forest", feature_schema_version=FEATURE_SCHEMA_VERSION
    )
    path = tmp_path / "m.joblib"
    sha = model.save(path)
    assert len(sha) == 64
    reloaded = TrainedModel.load(path)
    assert np.allclose(reloaded.score(x), model.score(x))
