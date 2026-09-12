"""Aggregate router for API v1. Each build module registers its sub-router here."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    api_keys,
    audit,
    auth,
    certificates,
    detections,
    ingest,
    ml,
    quantum,
    signatures,
    stream,
    system,
    threats,
    trust_store,
    users,
)

api_router = APIRouter()
api_router.include_router(system.router, tags=["system"])

# M1 — Identity & access
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(api_keys.router)

# M2 — Cryptographic core
api_router.include_router(signatures.router)
api_router.include_router(certificates.router)
api_router.include_router(trust_store.router)

# M3 — Threat detection engine
api_router.include_router(detections.router)
api_router.include_router(threats.router)

# M4 — Quantum-inspired optimisation
api_router.include_router(quantum.router)

# M5 — ML anomaly detection (optional)
api_router.include_router(ml.router)

# M6 — Audit logging
api_router.include_router(audit.router)

# M8 — Real-time & integrations
api_router.include_router(stream.router)
api_router.include_router(ingest.router)

# Registered as modules land:
#   quantum                         (M4)
#   ml                              (M5)
#   audit                           (M6)
#   ingest, stream                  (M8)
