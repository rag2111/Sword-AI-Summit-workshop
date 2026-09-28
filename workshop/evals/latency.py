"""Latency percentiles from run timings or local trace spans (pure; unit-tested)."""

from __future__ import annotations

import math
from typing import Any


def percentile(values: list[float], p: float) -> float:
    """Linear interpolation between closest ranks (same as numpy's default 'linear' method)."""
    if not values:
        raise ValueError("percentile() of empty data")
    if not 0 <= p <= 100:
        raise ValueError("p must be within [0, 100]")
    ordered = sorted(float(v) for v in values)
    rank = (len(ordered) - 1) * p / 100
    low, high = math.floor(rank), math.ceil(rank)
    if low == high:
        return ordered[int(rank)]
    return ordered[low] + (ordered[high] - ordered[low]) * (rank - low)


def latency_summary(values_ms: list[float]) -> dict[str, Any]:
    values = [v for v in values_ms if v is not None and v > 0]
    if not values:
        return {"n": 0, "p50_ms": None, "p95_ms": None, "mean_ms": None, "max_ms": None}
    return {
        "n": len(values),
        "p50_ms": round(percentile(values, 50), 1),
        "p95_ms": round(percentile(values, 95), 1),
        "mean_ms": round(sum(values) / len(values), 1),
        "max_ms": round(max(values), 1),
    }


def latencies_from_spans(spans: list[dict[str, Any]], name: str = "care_agent.turn", trace_ids: set[str] | None = None) -> list[float]:
    """Durations of our turn spans (from .care_agent/spans.jsonl), optionally limited to some traces."""
    return [
        float(s["duration_ms"])
        for s in spans
        if s.get("name") == name and (trace_ids is None or s.get("trace_id") in trace_ids)
    ]
