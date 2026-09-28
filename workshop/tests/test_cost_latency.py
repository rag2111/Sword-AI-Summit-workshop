import pytest

from evals.cost import cost_eur, price_for, run_cost
from evals.latency import latencies_from_spans, latency_summary, percentile
from evals.scoring import load_rubric


def test_cost_uses_price_table():
    prices = load_rubric()["prices"]
    assert price_for("gpt-6-luna", prices) == (0.00037, 0.00147)
    assert cost_eur("gpt-6-luna", 10_000, 1_000, prices) == pytest.approx(0.0037 + 0.00147)
    assert price_for("unknown-model", prices) == (0.0, 0.0)


def test_run_cost_per_task():
    prices = {"currency": "EUR", "models": {"m": {"input_per_1k_tokens": 1.0, "output_per_1k_tokens": 2.0}}}
    rows = [{"tokens": {"input": 1000, "output": 500}}, {"tokens": {"input": 1000, "output": 500}}]
    summary = run_cost(rows, "m", prices)
    assert summary["total_eur"] == 4.0 and summary["per_task_eur"] == 2.0 and summary["priced"]


def test_percentiles_match_numpy_linear():
    values = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
    assert percentile(values, 50) == 550
    assert percentile(values, 95) == pytest.approx(955)
    assert percentile([42], 95) == 42
    with pytest.raises(ValueError):
        percentile([], 50)


def test_latency_summary_ignores_failed_runs():
    summary = latency_summary([1000, 2000, 0, None, 3000])
    assert summary["n"] == 3 and summary["p50_ms"] == 2000 and summary["max_ms"] == 3000
    assert latency_summary([])["p50_ms"] is None


def test_latencies_from_spans():
    spans = [
        {"name": "care_agent.turn", "trace_id": "a", "duration_ms": 1200},
        {"name": "chat gpt-6-luna", "trace_id": "a", "duration_ms": 800},
        {"name": "care_agent.turn", "trace_id": "b", "duration_ms": 900},
    ]
    assert latencies_from_spans(spans) == [1200, 900]
    assert latencies_from_spans(spans, trace_ids={"b"}) == [900]
