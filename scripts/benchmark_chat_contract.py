"""Simple benchmark runner for contract-stable chat endpoints."""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time
from typing import Any

import httpx


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, int(len(ordered) * 0.95) - 1)
    return ordered[index]


async def _run_once(client: httpx.AsyncClient, url: str, payload: dict[str, Any]) -> float:
    started = time.perf_counter()
    response = await client.post(url, json=payload)
    response.raise_for_status()
    return (time.perf_counter() - started) * 1000


async def benchmark(base_url: str, runs: int) -> None:
    chat_url = f"{base_url.rstrip('/')}/chat"
    payload = {"user_id": "bench-user", "query": "Say hello in one short sentence."}
    latencies: list[float] = []
    async with httpx.AsyncClient(timeout=120.0) as client:
        for _ in range(runs):
            latency = await _run_once(client, chat_url, payload)
            latencies.append(latency)
    print(f"runs={runs}")
    print(f"avg_ms={statistics.fmean(latencies):.2f}")
    print(f"p95_ms={_p95(latencies):.2f}")
    print(f"max_ms={max(latencies):.2f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark /chat endpoint latency.")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Base API URL")
    parser.add_argument("--runs", type=int, default=10, help="Number of benchmark runs")
    args = parser.parse_args()
    asyncio.run(benchmark(base_url=args.base_url, runs=args.runs))


if __name__ == "__main__":
    main()
