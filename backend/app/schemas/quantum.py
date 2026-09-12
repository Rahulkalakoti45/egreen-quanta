"""Schemas for the quantum-inspired optimisation API (Module 4)."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field

# ---- quantum-exposure scoring ----


class QESRequest(BaseModel):
    algo: str = "rsa"
    key_bits: int | None = Field(default=None, ge=1)
    curve: str | None = None
    data_lifetime_years: float = Field(default=7.0, ge=0, le=100)
    exposure: str = Field(default="transmitted", pattern="^(public|transmitted|internal|sealed)$")
    label: str = ""
    qc_year: int | None = Field(default=None, ge=2025, le=2100)


class QESResponse(BaseModel):
    qes: float
    band: str
    algo_factor: float
    strength_factor: float
    longevity_factor: float
    exposure_factor: float
    recommendation: str
    assumptions: dict
    label: str


class PortfolioRequest(BaseModel):
    lookback_days: int = Field(default=30, ge=1, le=365)
    data_lifetime_years: float = Field(default=7.0, ge=0, le=100)
    exposure: str = Field(default="transmitted", pattern="^(public|transmitted|internal|sealed)$")
    qc_year: int | None = None


class PortfolioItem(BaseModel):
    label: str
    spki_sha256: str | None
    algo: str | None
    key_bits: int | None
    curve: str | None
    qes: float
    band: str
    event_count: int


class PortfolioResponse(BaseModel):
    items: list[PortfolioItem]
    scored: int
    by_band: dict[str, int]
    mean_qes: float


# ---- migration planner ----


class MigrationIdentityIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    qes: float = Field(ge=0, le=100)
    criticality: int = Field(default=3, ge=1, le=5)
    effort: int = Field(default=2, ge=1, le=10)
    label: str = ""


class MigrationPlanRequest(BaseModel):
    identities: list[MigrationIdentityIn] = Field(min_length=1, max_length=40)
    waves: int = Field(default=4, ge=1, le=10)
    wave_capacity: int | None = Field(default=None, ge=1)
    method: str = Field(default="auto", pattern="^(auto|sa|sqa|brute)$")
    seed: int | None = None


class MigrationPlanResponse(BaseModel):
    waves: list[list[dict]]
    wave_capacity: int
    total_waves: int
    cumulative_exposure: float
    baseline_exposure: float
    improvement_pct: float
    solver: dict
    unassigned: list[str]
    notes: list[str]
    run_id: str


# ---- detection tuning ----


class TuningRequest(BaseModel):
    lookback_days: int = Field(default=30, ge=1, le=365)
    fp_cost: float = Field(default=1.4, ge=0.1, le=10)
    threshold: float = Field(default=1.0, ge=0)
    method: str = Field(default="auto", pattern="^(auto|sa|sqa|brute)$")
    seed: int | None = None
    synthetic: bool = Field(
        default=True, description="Fall back to a synthetic dataset if history is thin"
    )


class TuningResponse(BaseModel):
    weights: dict[str, float]
    levels: list[float]
    threshold: float
    before: dict
    after: dict
    solver: dict
    rules: list[str]
    sample_size: int
    source: str
    run_id: str


class TuningApplyRequest(BaseModel):
    run_id: str


# ---- correlation ----


class CorrelationRunRequest(BaseModel):
    lookback_hours: int = Field(default=24, ge=1, le=720)
    gamma: float | None = Field(default=None, ge=0)
    method: str = Field(default="auto", pattern="^(auto|sa|sqa|brute)$")
    seed: int | None = None


class CorrelationRunResponse(BaseModel):
    clusters: list[list[str]]
    cluster_density: list[float]
    singletons: list[str]
    qubo_modularity: float
    baseline_modularity: float
    event_count: int
    run_id: str


# ---- runs ----


class QuantumRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    run_type: str
    method: str
    seed: int
    wall_ms: float
    params: dict
    metrics: dict
    input_ref: str | None
    created_at: dt.datetime


class QuantumRunDetail(QuantumRunOut):
    result: dict
