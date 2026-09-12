"""Schemas for the ML anomaly-detection API (Module 5)."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict, Field


class MlStatus(BaseModel):
    enabled: bool
    active_model_id: str | None
    feature_schema_version: int
    feature_count: int
    anomaly_weight: float


class TrainRequest(BaseModel):
    algo: str = Field(default="isolation_forest", pattern="^(isolation_forest|one_class_svm)$")
    source: str = Field(default="dataset", pattern="^(history|dataset)$")
    lookback_days: int = Field(default=30, ge=1, le=365)
    contamination: float = Field(default=0.08, gt=0, lt=0.5)
    activate: bool = False


class MlModelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: str
    algo: str
    params: dict
    metrics: dict
    feature_schema_version: int
    n_train: int
    threshold: float
    artifact_sha256: str
    is_active: bool
    source: str
    notes: str
    trained_by: str | None
    trained_at: dt.datetime


class ScoreRequest(BaseModel):
    event_id: str


class ScoreResponse(BaseModel):
    event_id: str
    anomaly_score: float | None
    flagged: bool
    threshold: float
    model_id: str | None
