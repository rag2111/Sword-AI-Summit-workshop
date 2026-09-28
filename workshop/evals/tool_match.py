"""Deterministic expected-vs-actual tool-call matching (pure; unit-tested).

This is the offline fallback for ToolCallAccuracyEvaluator and a useful second opinion: an LLM
judge can be lenient, a string comparison cannot.
"""

from __future__ import annotations

from typing import Any


def short_name(name: str) -> str:
    """Strip server prefixes some MCP clients add (care_tools__get_care_plan -> get_care_plan)."""
    for separator in ("__", ".", "/"):
        if separator in name:
            name = name.rsplit(separator, 1)[-1]
    return name


def _norm(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip().lower()
    if isinstance(value, list):
        return sorted(_norm(v) for v in value)
    return value


def arguments_match(expected: dict[str, Any], actual: Any) -> bool:
    """Every expected argument must be present with an equal value (numbers: actual <= expected
    for `within_days`, so 'within 5 days' satisfies 'within 7 days')."""
    if not expected:
        return True
    if not isinstance(actual, dict):
        return False
    for key, want in expected.items():
        if key not in actual:
            return False
        got = actual[key]
        if key == "within_days" and isinstance(got, (int, float)) and isinstance(want, (int, float)):
            if got > want:
                return False
            continue
        if _norm(got) != _norm(want):
            return False
    return True


def tool_match_score(expected: list[dict[str, Any]], actual: list[dict[str, Any]], forbidden: list[str] | None = None) -> float:
    """Fraction of expected calls satisfied, minus a penalty for each forbidden tool used. 0..1."""
    forbidden = forbidden or []
    actual_names = [short_name(c.get("name", "")) for c in actual]
    used_forbidden = sum(1 for name in actual_names if name in forbidden)
    if not expected:
        return 0.0 if used_forbidden else 1.0
    satisfied = 0
    for want in expected:
        if any(
            short_name(call.get("name", "")) == want["name"] and arguments_match(want.get("arguments") or {}, call.get("arguments"))
            for call in actual
        ):
            satisfied += 1
    score = satisfied / len(expected) - 0.5 * used_forbidden
    return round(max(0.0, min(1.0, score)), 4)
