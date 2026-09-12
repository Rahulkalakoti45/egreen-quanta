"""Quantum Exposure Score + PQC migration planner."""

from __future__ import annotations

from app.services.quantum.pq_risk import (
    MigrationIdentity,
    QESInput,
    plan_migration,
    score_qes,
)


def test_qes_orders_by_key_strength() -> None:
    weak = score_qes(QESInput(algo="rsa", key_bits=1024, data_lifetime_years=8)).qes
    mid = score_qes(QESInput(algo="rsa", key_bits=2048, data_lifetime_years=8)).qes
    strong = score_qes(QESInput(algo="rsa", key_bits=4096, data_lifetime_years=8)).qes
    assert weak >= mid >= strong


def test_post_quantum_algorithms_score_zero() -> None:
    for algo in ("ml-dsa", "SLH-DSA", "dilithium", "sphincs+", "xmss"):
        r = score_qes(QESInput(algo=algo, data_lifetime_years=25, exposure="public"))
        assert r.qes == 0.0
        assert r.band == "ok"


def test_longevity_and_exposure_scale_risk() -> None:
    short_sealed = score_qes(
        QESInput(algo="rsa", key_bits=3072, data_lifetime_years=1, exposure="sealed")
    ).qes
    long_public = score_qes(
        QESInput(algo="rsa", key_bits=3072, data_lifetime_years=15, exposure="public")
    ).qes
    assert long_public > short_sealed
    assert long_public >= 70


def test_ecdsa_is_flagged() -> None:
    r = score_qes(QESInput(algo="ec", curve="secp256r1", data_lifetime_years=6, exposure="public"))
    assert r.algo_factor == 1.0
    assert r.qes >= 70


def test_migration_plan_assigns_each_identity_once() -> None:
    ids = [
        MigrationIdentity(f"id{i}", qes=q, criticality=c, effort=e)
        for i, (q, c, e) in enumerate(
            [(90, 5, 3), (70, 4, 2), (60, 3, 2), (50, 2, 1), (40, 3, 2), (30, 1, 1)]
        )
    ]
    plan = plan_migration(ids, waves=3, seed=7)
    placed = [m["name"] for wave in plan.waves for m in wave]
    assert sorted(placed) == sorted(i.name for i in ids)
    assert not plan.unassigned


def test_migration_plan_front_loads_high_risk() -> None:
    ids = [
        MigrationIdentity("critical", qes=95, criticality=5, effort=1),
        MigrationIdentity("low1", qes=20, criticality=1, effort=1),
        MigrationIdentity("low2", qes=15, criticality=1, effort=1),
        MigrationIdentity("low3", qes=10, criticality=1, effort=1),
    ]
    plan = plan_migration(ids, waves=4, wave_capacity=1, seed=7)
    # the critical identity must land in the first wave
    assert any(m["name"] == "critical" for m in plan.waves[0])
    assert plan.cumulative_exposure <= plan.baseline_exposure + 1e-6
