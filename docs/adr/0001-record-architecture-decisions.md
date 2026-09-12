# 1. Record architecture decisions

- Status: accepted
- Date: 2026-09-09

## Context

Egreen Quanta is built module by module for SIH 2026 PS-141. Significant technical choices should
be traceable so reviewers (and the team) understand *why*, not just *what*.

## Decision

We keep short Architecture Decision Records (ADRs) in `docs/adr/`, numbered sequentially. Each
records context, the decision, and consequences. `docs/ARCHITECTURE.md` is the living overview;
ADRs capture the reasoning behind individual choices as they are made.

## Consequences

- Every non-obvious choice (DB portability, quantum-inspired solver in pure NumPy, ML off by
  default, SSE vs WebSocket, APScheduler vs Celery) gets a one-page ADR.
- ADRs are append-only; a superseded decision gets a new ADR that references the old one.
