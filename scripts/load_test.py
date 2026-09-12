#!/usr/bin/env python3
"""Tiny dependency-free load generator for Egreen Quanta.

Standard library only (urllib + asyncio threads) so it runs anywhere Python does.

Examples
--------
    # 30s of liveness probes, 32 in flight
    python scripts/load_test.py --scenario health -c 32 -d 30

    # 500 signature verifications against a running dev server
    python scripts/load_test.py --scenario verify -n 500 -c 16 \
        --base-url http://localhost:8000 --email admin@egreen.local --password 'EgreenQuanta!2026'

Reports throughput, latency percentiles and a status-code histogram. This is a
smoke / capacity sanity check, not a benchmarking harness. For numbers that mean
anything, point it at the Docker stack (gunicorn, multiple workers) rather than a
single-worker ``uvicorn --reload`` dev server.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SAMPLE = REPO / "datasets" / "documents" / "raw" / "rsa-pss.json"


class Result:
    __slots__ = ("errors", "latencies", "status")

    def __init__(self) -> None:
        self.latencies: list[float] = []
        self.status: Counter[int] = Counter()
        self.errors: Counter[str] = Counter()


def _request(method: str, url: str, *, body: bytes | None, headers: dict[str, str]) -> int:
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp.read()
            return int(resp.status)
    except urllib.error.HTTPError as exc:
        return int(exc.code)


def _login(base_url: str, email: str, password: str) -> str:
    body = json.dumps({"email": email, "password": password}).encode()
    req = urllib.request.Request(
        f"{base_url}/api/v1/auth/login",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return str(json.loads(resp.read())["access_token"])


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    k = max(0, min(len(ordered) - 1, round(pct / 100 * (len(ordered) - 1))))
    return ordered[k]


async def _worker(
    name: int,
    stop_at: float | None,
    budget: asyncio.Queue | None,
    make_call,
    out: Result,
) -> None:
    while True:
        if budget is not None:
            try:
                budget.get_nowait()
            except asyncio.QueueEmpty:
                return
        elif stop_at is not None and time.monotonic() >= stop_at:
            return
        start = time.perf_counter()
        try:
            code = await asyncio.to_thread(make_call)
            out.status[code] += 1
        except Exception as exc:
            out.errors[type(exc).__name__] += 1
        finally:
            out.latencies.append((time.perf_counter() - start) * 1000)


async def run(args: argparse.Namespace) -> Result:
    base = args.base_url.rstrip("/")
    headers = {"Content-Type": "application/json"}
    body: bytes | None = None
    path = "/healthz"

    if args.scenario == "verify":
        token = await asyncio.to_thread(_login, base, args.email, args.password)
        headers["Authorization"] = f"Bearer {token}"
        if not SAMPLE.exists():
            raise SystemExit(f"{SAMPLE} not found - run: python scripts/gen_sample_signatures.py")
        bundle = json.loads(SAMPLE.read_text())
        body = json.dumps(bundle).encode()
        path = "/api/v1/signatures/verify"

    method = "POST" if body is not None else "GET"
    url = f"{base}{path}"

    def make_call() -> int:
        return _request(method, url, body=body, headers=headers)

    out = Result()
    budget: asyncio.Queue | None = None
    stop_at: float | None = None
    if args.requests:
        budget = asyncio.Queue()
        for _ in range(args.requests):
            budget.put_nowait(1)
    else:
        stop_at = time.monotonic() + args.duration

    wall = time.perf_counter()
    await asyncio.gather(
        *(_worker(i, stop_at, budget, make_call, out) for i in range(args.concurrency))
    )
    out_wall = time.perf_counter() - wall
    _report(args, out, out_wall)
    return out


def _report(args: argparse.Namespace, out: Result, wall: float) -> None:
    n = len(out.latencies)
    ok = sum(c for s, c in out.status.items() if 200 <= s < 400)
    rps = n / wall if wall else 0.0
    lat = out.latencies
    print("\n=== Egreen Quanta load test ===")
    print(f"scenario     {args.scenario}")
    print(f"target       {args.base_url}")
    print(f"concurrency  {args.concurrency}")
    print(f"requests     {n} in {wall:.2f}s  ->  {rps:,.1f} req/s")
    print(f"success      {ok}/{n} ({(ok / n * 100) if n else 0:.1f}%)")
    print(
        "latency ms   "
        f"min {min(lat, default=0):.1f}  "
        f"p50 {_percentile(lat, 50):.1f}  "
        f"p90 {_percentile(lat, 90):.1f}  "
        f"p95 {_percentile(lat, 95):.1f}  "
        f"p99 {_percentile(lat, 99):.1f}  "
        f"max {max(lat, default=0):.1f}"
    )
    print(f"status codes {dict(sorted(out.status.items()))}")
    if out.errors:
        print(f"errors       {dict(out.errors)}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--scenario", choices=["health", "verify"], default="health")
    p.add_argument("--base-url", default="http://localhost:8000")
    p.add_argument("--email", default="admin@egreen.local")
    p.add_argument("--password", default="EgreenQuanta!2026")
    p.add_argument("-c", "--concurrency", type=int, default=16)
    p.add_argument("-n", "--requests", type=int, default=0, help="total requests (overrides -d)")
    p.add_argument("-d", "--duration", type=float, default=15.0, help="seconds to run")
    return p.parse_args()


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
