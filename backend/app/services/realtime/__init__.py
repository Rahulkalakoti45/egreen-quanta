"""Module 8 - real-time fan-out.

An in-process async pub/sub broker backs the SSE alert stream. In a multi-worker
deployment point ``REDIS_URL`` at Redis and swap ``broker`` for the Redis-backed
implementation (same ``publish`` / ``subscribe`` surface).
"""

from app.services.realtime.broker import broker

__all__ = ["broker"]
