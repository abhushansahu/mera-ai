"""Compare direct backend latency vs Go edge proxy latency."""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time
from typing import Any

import httpx


def p95(values: list[float]) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    idx = max(0, int(len(sorted_values) * 0.95) - 1)
    return sorted_values[idx]


async def run_samples(url: str, runs: int) -> list[float]:
    payload: dict[str, Any] = {
        "user_id": "bench-user",
        "query": "Return one short sentence only.",
    }
    latencies: list[float] = []
    async with httpx.AsyncClient(timeout=120.0) as client:
        for _ in range(runs):
            started = time.perf_counter()
            response = await client.post(url, json=payload)
            response.raise_for_status()
            latencies.append((time.perf_counter() - started) * 1000)
    return latencies


def print_stats(label: str, values: list[float]) -> None:
    print(
        f"{label}: avg_ms={statistics.fmean(values):.2f} "
        f"p95_ms={p95(values):.2f} max_ms={max(values):.2f}"
    )


async def main_async(args: argparse.Namespace) -> None:
    direct = await run_samples(f"{args.direct_base.rstrip('/')}/chat", args.runs)
    edge = await run_samples(f"{args.edge_base.rstrip('/')}/chat", args.runs)
    print_stats("direct", direct)
    print_stats("edge", edge)
    print(f"delta_p95_ms={p95(edge) - p95(direct):.2f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare direct API vs edge proxy latency.")
    parser.add_argument("--direct-base", default="http://localhost:8000")
    parser.add_argument("--edge-base", default="http://localhost:8081")
    parser.add_argument("--runs", type=int, default=10)
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
