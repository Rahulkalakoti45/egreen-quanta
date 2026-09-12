"""Orchestration for the quantum-inspired endpoints: history I/O + persistence."""

from __future__ import annotations

import datetime as dt

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationAppError
from app.models.alert import Alert
from app.models.detection_rule import DetectionRule
from app.models.quantum import QuantumExposureScore, QuantumRun
from app.models.verification_event import Finding, VerificationEvent
from app.services.detection.correlation import similarity
from app.services.quantum import pq_risk, tuning
from app.services.quantum.correlation_qubo import correlate_qubo


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


# ---- quantum-exposure portfolio ------------------------------------------------


async def score_portfolio(
    session: AsyncSession,
    *,
    lookback_days: int,
    data_lifetime_years: float,
    exposure: str,
    qc_year: int | None,
    created_by: str | None,
) -> dict:
    since = _utcnow() - dt.timedelta(days=lookback_days)
    rows = (
        (
            await session.execute(
                select(VerificationEvent).where(
                    VerificationEvent.created_at >= since,
                    VerificationEvent.key_type.is_not(None),
                )
            )
        )
        .scalars()
        .all()
    )
    if not rows:
        return {"items": [], "scored": 0, "by_band": {}, "mean_qes": 0.0}

    # group by signer key (fall back to algo+bits+curve)
    groups: dict[str, list[VerificationEvent]] = {}
    for ev in rows:
        key = ev.signer_spki_sha256 or f"{ev.key_type}:{ev.key_bits}:{ev.curve}"
        groups.setdefault(key, []).append(ev)

    assumptions = {"qc_year": qc_year} if qc_year else None
    items: list[dict] = []
    by_band: dict[str, int] = {}
    for key, evs in groups.items():
        sample = evs[0]
        res = pq_risk.score_qes(
            pq_risk.QESInput(
                algo=sample.key_type or "rsa",
                key_bits=sample.key_bits,
                curve=sample.curve,
                data_lifetime_years=data_lifetime_years,
                exposure=exposure,
                label=(sample.signer_subject or key)[:120],
            ),
            assumptions=assumptions,
        )
        session.add(
            QuantumExposureScore(
                event_id=sample.id,
                label=res.label,
                spki_sha256=sample.signer_spki_sha256,
                algo=sample.key_type,
                key_type=sample.key_type,
                key_bits=sample.key_bits,
                curve=sample.curve,
                qes=res.qes,
                band=res.band,
                factors={
                    "algo": res.algo_factor,
                    "strength": res.strength_factor,
                    "longevity": res.longevity_factor,
                    "exposure": res.exposure_factor,
                },
                assumptions=res.assumptions,
                recommendation=res.recommendation,
            )
        )
        by_band[res.band] = by_band.get(res.band, 0) + 1
        items.append(
            {
                "label": res.label,
                "spki_sha256": sample.signer_spki_sha256,
                "algo": sample.key_type,
                "key_bits": sample.key_bits,
                "curve": sample.curve,
                "qes": res.qes,
                "band": res.band,
                "event_count": len(evs),
            }
        )
    await session.commit()
    items.sort(key=lambda i: -i["qes"])
    mean_qes = round(float(np.mean([i["qes"] for i in items])), 1) if items else 0.0
    return {"items": items, "scored": len(items), "by_band": by_band, "mean_qes": mean_qes}


# ---- migration planner -------------------------------------------------------


async def run_migration_plan(session: AsyncSession, payload, *, created_by: str | None) -> dict:
    identities = [
        pq_risk.MigrationIdentity(
            name=i.name, qes=i.qes, criticality=i.criticality, effort=i.effort, label=i.label
        )
        for i in payload.identities
    ]
    plan = pq_risk.plan_migration(
        identities,
        waves=payload.waves,
        wave_capacity=payload.wave_capacity,
        method=payload.method,
        seed=payload.seed,
    )
    run = QuantumRun(
        run_type="migration_plan",
        method=plan.solver.get("method", ""),
        seed=plan.solver.get("seed", 0),
        wall_ms=plan.solver.get("wall_ms", 0.0),
        params={"waves": payload.waves, "wave_capacity": plan.wave_capacity, "n": len(identities)},
        result=plan.as_dict(),
        metrics={
            "cumulative_exposure": plan.cumulative_exposure,
            "baseline_exposure": plan.baseline_exposure,
            "improvement_pct": plan.improvement_pct,
        },
        input_ref=f"{len(identities)} identities",
        created_by=created_by,
    )
    session.add(run)
    await session.commit()
    out = plan.as_dict()
    out["run_id"] = run.id
    return out


# ---- detection tuning ------------------------------------------------------


def _synthetic_labelled(
    rules: list[str], n: int = 240, seed: int = 1337
) -> list[tuning.LabelledEvent]:
    rng = np.random.default_rng(seed)
    strong = {"T01": 0.75, "T09": 0.55, "T06": 0.45, "T07": 0.4, "T03": 0.3}
    noisy = {"T05": 0.45, "T13": 0.5, "T02": 0.12, "T04": 0.1}
    out: list[tuning.LabelledEvent] = []
    for _ in range(n):
        mal = rng.random() < 0.4
        fired: set[str] = set()
        table = strong if mal else noisy
        for r, p in table.items():
            if r in rules and rng.random() < p:
                fired.add(r)
        if not mal:
            for r, p in {"T13": 0.4, "T05": 0.35}.items():
                if r in rules and rng.random() < p:
                    fired.add(r)
        out.append(tuning.LabelledEvent(fired=fired, malicious=mal))
    return out


async def _labelled_from_history(
    session: AsyncSession, rules: list[str], since: dt.datetime
) -> list[tuning.LabelledEvent]:
    evs = (
        (
            await session.execute(
                select(VerificationEvent).where(VerificationEvent.created_at >= since)
            )
        )
        .scalars()
        .all()
    )
    alerted = set(
        (
            await session.execute(
                select(Alert.event_id).join(
                    VerificationEvent, VerificationEvent.id == Alert.event_id
                )
            )
        )
        .scalars()
        .all()
    )
    findings = (await session.execute(select(Finding.event_id, Finding.rule_code))).all()
    by_event: dict[str, set[str]] = {}
    for ev_id, code in findings:
        by_event.setdefault(ev_id, set()).add(code)

    out: list[tuning.LabelledEvent] = []
    for ev in evs:
        fired = {c for c in by_event.get(ev.id, set()) if c in rules}
        if not fired:
            continue
        malicious = ev.verdict == "invalid" or ev.id in alerted
        out.append(tuning.LabelledEvent(fired=fired, malicious=malicious))
    return out


async def run_tuning(session: AsyncSession, payload, *, created_by: str | None) -> dict:
    rule_rows = (await session.execute(select(DetectionRule))).scalars().all()
    rules = [r.code for r in rule_rows]
    current = {r.code: r.weight for r in rule_rows}
    since = _utcnow() - dt.timedelta(days=payload.lookback_days)

    events = await _labelled_from_history(session, rules, since)
    source = "history"
    if len(events) < 40 and payload.synthetic:
        events = _synthetic_labelled(rules, seed=payload.seed or settings.quantum_seed)
        source = "synthetic"
    if len(events) < 10:
        raise ValidationAppError("Not enough labelled events to tune; enable `synthetic`.")

    res = tuning.tune_weights(
        events,
        rules,
        current_weights=current,
        fp_cost=payload.fp_cost,
        threshold=payload.threshold,
        method=payload.method,
        seed=payload.seed,
    )
    run = QuantumRun(
        run_type="detection_tuning",
        method=res.solver.get("method", ""),
        seed=res.solver.get("seed", 0),
        wall_ms=res.solver.get("wall_ms", 0.0),
        params={
            "lookback_days": payload.lookback_days,
            "fp_cost": payload.fp_cost,
            "source": source,
        },
        result=res.as_dict(),
        metrics={
            "f1_before": res.before["f1"],
            "f1_after": res.after["f1"],
            "sample_size": len(events),
        },
        input_ref=f"{len(events)} labelled events ({source})",
        created_by=created_by,
    )
    session.add(run)
    await session.commit()
    out = res.as_dict()
    out.update({"run_id": run.id, "sample_size": len(events), "source": source})
    return out


async def apply_tuning(session: AsyncSession, run_id: str) -> dict:
    run = (
        await session.execute(select(QuantumRun).where(QuantumRun.id == run_id))
    ).scalar_one_or_none()
    if run is None or run.run_type != "detection_tuning":
        raise NotFoundError("Tuning run not found")
    weights: dict[str, float] = run.result.get("weights", {})
    rules = (await session.execute(select(DetectionRule))).scalars().all()
    changed = 0
    for rule in rules:
        if rule.code in weights and abs(rule.weight - weights[rule.code]) > 1e-9:
            rule.weight = float(weights[rule.code])
            changed += 1
    await session.commit()
    return {"applied": changed, "weights": weights}


# ---- correlation QUBO -------------------------------------------------------


async def run_correlation(session: AsyncSession, payload, *, created_by: str | None) -> dict:
    since = _utcnow() - dt.timedelta(hours=payload.lookback_hours)
    events = (
        (
            await session.execute(
                select(VerificationEvent)
                .where(VerificationEvent.created_at >= since)
                .order_by(VerificationEvent.created_at.desc())
                .limit(40)
            )
        )
        .scalars()
        .all()
    )
    if len(events) < 3:
        raise ValidationAppError("Need at least 3 events in the window to correlate")

    findings = (
        await session.execute(
            select(Finding.event_id, Finding.rule_code).where(
                Finding.event_id.in_([e.id for e in events])
            )
        )
    ).all()
    codes: dict[str, set[str]] = {}
    for ev_id, code in findings:
        codes.setdefault(ev_id, set()).add(code)

    n = len(events)
    sim = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            s = similarity(
                events[i], events[j], codes.get(events[i].id, set()), codes.get(events[j].id, set())
            )
            sim[i, j] = sim[j, i] = s

    labels = [
        (events[i].signer_subject or events[i].summary or events[i].id)[:40] for i in range(n)
    ]
    res = correlate_qubo(
        sim, gamma=payload.gamma, method=payload.method, seed=payload.seed, labels=labels
    )

    run = QuantumRun(
        run_type="correlation",
        method=res.solver_runs[0]["method"] if res.solver_runs else "",
        seed=payload.seed or settings.quantum_seed,
        wall_ms=sum(r.get("wall_ms", 0.0) for r in res.solver_runs),
        params={"lookback_hours": payload.lookback_hours, "n": n},
        result=res.as_dict(),
        metrics={
            "qubo_modularity": res.qubo_modularity,
            "baseline_modularity": res.baseline_modularity,
            "clusters": len(res.clusters),
        },
        input_ref=f"{n} events",
        created_by=created_by,
    )
    session.add(run)
    await session.commit()

    named_clusters = [[labels[i] for i in c] for c in res.clusters]
    return {
        "clusters": named_clusters,
        "cluster_density": res.cluster_density,
        "singletons": [labels[i] for i in res.singletons],
        "qubo_modularity": res.qubo_modularity,
        "baseline_modularity": res.baseline_modularity,
        "event_count": n,
        "run_id": run.id,
    }
