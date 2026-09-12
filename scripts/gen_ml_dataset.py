#!/usr/bin/env python3
"""Generate datasets/labeled_events.csv for the ML anomaly module.

    python scripts/gen_ml_dataset.py

Mostly "normal" verification events with a small fraction of anomalies (odd algo/hash
combinations, unusual finding mixes, off-hours bursts). The ``is_anomaly`` column is
only used to *evaluate* the unsupervised model, never to train it.
"""

from __future__ import annotations

import csv
import datetime as dt
import random
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "datasets" / "labeled_events.csv"
N = 900
ANOMALY_FRAC = 0.07
SEED = 1337

COLUMNS = [
    "created_at",
    "key_type",
    "key_bits",
    "curve",
    "hash_alg",
    "envelope_type",
    "verdict",
    "chain_status",
    "signing_time",
    "tsa_present",
    "finding_categories",
    "is_anomaly",
]


def _normal(rng: random.Random, base: dt.datetime) -> dict:
    key_type = rng.choices(["rsa", "ec", "ed25519"], weights=[5, 4, 2])[0]
    if key_type == "rsa":
        key_bits, curve = rng.choice([2048, 3072, 4096]), ""
    elif key_type == "ec":
        key_bits, curve = 256, rng.choice(["secp256r1", "secp384r1"])
    else:
        key_bits, curve = 256, ""
    verdict = rng.choices(["valid", "indeterminate", "invalid"], weights=[80, 12, 8])[0]
    cats: list[str] = []
    if verdict == "invalid":
        cats = ["forgery"]
    elif verdict == "indeterminate":
        cats = rng.choice([["chain"], ["revocation"], ["timestamp"], []])
    return {
        "created_at": (base - dt.timedelta(minutes=rng.randint(0, 43200))).isoformat(),
        "key_type": key_type,
        "key_bits": key_bits,
        "curve": curve,
        "hash_alg": rng.choices(["sha256", "sha384", "sha512"], weights=[8, 2, 1])[0],
        "envelope_type": rng.choices(["raw", "pdf", "cms", "jws"], weights=[5, 3, 2, 2])[0],
        "verdict": verdict,
        "chain_status": rng.choices(
            ["trusted", "untrusted", "incomplete", "none"], weights=[7, 1, 1, 3]
        )[0],
        "signing_time": "" if rng.random() < 0.4 else base.isoformat(),
        "tsa_present": int(rng.random() < 0.5),
        "finding_categories": "|".join(cats),
        "is_anomaly": 0,
    }


def _anomaly(rng: random.Random, base: dt.datetime) -> dict:
    kind = rng.choice(["weak_combo", "finding_storm", "odd_algo", "offhours_fail"])
    row = _normal(rng, base)
    row["is_anomaly"] = 1
    if kind == "weak_combo":
        row.update(key_type="rsa", key_bits=1024, hash_alg="sha1", verdict="invalid")
        row["finding_categories"] = "weak_crypto|forgery"
    elif kind == "finding_storm":
        row["verdict"] = "invalid"
        row["finding_categories"] = "|".join(
            rng.sample(["forgery", "weak_crypto", "chain", "revocation", "policy", "validity"], 4)
        )
    elif kind == "odd_algo":
        row.update(key_type="dsa", key_bits=1024, hash_alg="md5", chain_status="error")
        row["finding_categories"] = "weak_crypto"
    else:  # offhours_fail
        t = base.replace(hour=rng.choice([1, 2, 3, 4]), minute=rng.randint(0, 59))
        row["created_at"] = t.isoformat()
        row["verdict"] = "invalid"
        row["finding_categories"] = "forgery|policy"
    return row


def main() -> None:
    rng = random.Random(SEED)
    base = dt.datetime(2026, 9, 1, 12, 0, tzinfo=dt.UTC)
    rows = []
    for _ in range(N):
        rows.append(_anomaly(rng, base) if rng.random() < ANOMALY_FRAC else _normal(rng, base))
    rng.shuffle(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    anomalies = sum(r["is_anomaly"] for r in rows)
    print(f"[gen_ml_dataset] wrote {len(rows)} rows ({anomalies} anomalies) to {OUT}")


if __name__ == "__main__":
    main()
