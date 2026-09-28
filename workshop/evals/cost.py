"""Tokens → euros using the price table in rubric.yaml (pure; unit-tested)."""

from __future__ import annotations

from typing import Any


def price_for(model: str, prices: dict[str, Any]) -> tuple[float, float]:
    """(input, output) EUR per 1k tokens. Unknown models cost 0 but are reported by the caller."""
    entry = (prices.get("models") or {}).get(model)
    if entry is None:
        return 0.0, 0.0
    return float(entry["input_per_1k_tokens"]), float(entry["output_per_1k_tokens"])


def cost_eur(model: str, input_tokens: int, output_tokens: int, prices: dict[str, Any]) -> float:
    price_in, price_out = price_for(model, prices)
    return round(input_tokens / 1000 * price_in + output_tokens / 1000 * price_out, 6)


def run_cost(rows: list[dict[str, Any]], model: str, prices: dict[str, Any]) -> dict[str, Any]:
    """Aggregate agent token usage for a run (judge tokens are an evaluation cost, not a product cost)."""
    input_tokens = sum(int(r.get("tokens", {}).get("input", 0)) for r in rows)
    output_tokens = sum(int(r.get("tokens", {}).get("output", 0)) for r in rows)
    total = cost_eur(model, input_tokens, output_tokens, prices)
    count = max(1, len(rows))
    return {
        "currency": prices.get("currency", "EUR"),
        "model": model,
        "priced": model in (prices.get("models") or {}),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_eur": round(total, 6),
        "per_task_eur": round(total / count, 6),
    }
