"""Feature extraction for anomaly detection (pure NumPy, no scikit-learn import).

A ``VerificationEvent`` (+ its findings) becomes a fixed-length float vector. Bump
``FEATURE_SCHEMA_VERSION`` whenever the layout changes so stale models are rejected.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence

import numpy as np

FEATURE_SCHEMA_VERSION = 1

_ALGO_FAMILY = ["rsa", "ec", "ed25519", "ed448", "dsa", "unknown"]
_HASH = ["sha1", "sha224", "sha256", "sha384", "sha512", "sha3-256", "md5", "none"]
_ENVELOPE = ["raw", "pdf", "cms", "jws", "certificate"]
_VERDICT = ["valid", "invalid", "indeterminate"]
_CHAIN = ["trusted", "untrusted", "incomplete", "error", "none"]
_FINDING_CATEGORIES = [
    "forgery",
    "weak_crypto",
    "chain",
    "revocation",
    "validity",
    "policy",
    "timestamp",
    "quantum",
]

FEATURE_NAMES: list[str] = (
    [f"algo_{a}" for a in _ALGO_FAMILY]
    + [f"hash_{h}" for h in _HASH]
    + [f"env_{e}" for e in _ENVELOPE]
    + [f"verdict_{v}" for v in _VERDICT]
    + [f"chain_{c}" for c in _CHAIN]
    + [
        "key_bits_norm",
        "curve_id",
        "has_signing_time",
        "tsa_present",
        "hour_sin",
        "hour_cos",
        "finding_count",
    ]
    + [f"find_{c}" for c in _FINDING_CATEGORIES]
)

FEATURE_DIM = len(FEATURE_NAMES)

_CURVE_ID = {"secp256r1": 1, "secp384r1": 2, "secp521r1": 3, "secp256k1": 4}


def _one_hot(value: str | None, vocab: Sequence[str], fallback: str) -> list[float]:
    v = (value or fallback).lower()
    if v not in vocab:
        v = fallback
    return [1.0 if item == v else 0.0 for item in vocab]


def _algo_family(key_type: str | None) -> str:
    kt = (key_type or "unknown").lower()
    return kt if kt in _ALGO_FAMILY else "unknown"


def event_to_vector(
    *,
    key_type: str | None,
    key_bits: int | None,
    curve: str | None,
    hash_alg: str | None,
    envelope_type: str | None,
    verdict: str | None,
    chain_status: str | None,
    signing_time: dt.datetime | None,
    tsa_present: bool,
    created_at: dt.datetime,
    finding_categories: Sequence[str],
) -> np.ndarray:
    parts: list[float] = []
    parts += _one_hot(_algo_family(key_type), _ALGO_FAMILY, "unknown")
    parts += _one_hot(hash_alg, _HASH, "none")
    parts += _one_hot(envelope_type, _ENVELOPE, "raw")
    parts += _one_hot(verdict, _VERDICT, "indeterminate")
    parts += _one_hot(chain_status or "none", _CHAIN, "none")

    parts.append(float(np.clip((key_bits or 0) / 4096.0, 0.0, 4.0)))
    parts.append(float(_CURVE_ID.get((curve or "").lower(), 0)) / 4.0)
    parts.append(1.0 if signing_time is not None else 0.0)
    parts.append(1.0 if tsa_present else 0.0)

    hour = created_at.hour + created_at.minute / 60.0
    parts.append(float(np.sin(2 * np.pi * hour / 24.0)))
    parts.append(float(np.cos(2 * np.pi * hour / 24.0)))

    cats = list(finding_categories)
    parts.append(float(len(cats)))
    for c in _FINDING_CATEGORIES:
        parts.append(float(sum(1 for x in cats if x == c)))

    vec = np.asarray(parts, dtype=np.float64)
    if vec.shape[0] != FEATURE_DIM:  # pragma: no cover - guard against schema drift
        raise RuntimeError(f"feature vector dim {vec.shape[0]} != {FEATURE_DIM}")
    return vec


def events_to_matrix(rows: Sequence[dict]) -> np.ndarray:
    """``rows`` are dicts with the ``event_to_vector`` keyword keys."""
    if not rows:
        return np.zeros((0, FEATURE_DIM))
    return np.vstack([event_to_vector(**r) for r in rows])
