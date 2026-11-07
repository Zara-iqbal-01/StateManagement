"""Metric aggregation for memory-ablation runs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from statistics import mean
from typing import Iterable

from .models import AgentResult


@dataclass(frozen=True)
class ExperimentMetrics:
    task_count: int
    completion_rate_pct: float
    avg_tool_calls: float
    avg_input_tokens: float
    avg_output_tokens: float
    avg_total_tokens: float
    avg_latency_seconds: float
    repeated_error_rate_pct: float
    retrieval_precision_pct: float | None
    knowledge_transfer_success_rate_pct: float
    stale_memory_error_rate_pct: float
    avg_retrieval_overhead_ms: float

    def to_dict(self) -> dict[str, float | int | None]:
        return asdict(self)


def aggregate(
    results: Iterable[AgentResult],
    *,
    relevant_retrieval_counts: Iterable[tuple[int, int]] = (),
) -> ExperimentMetrics:
    records = list(results)
    if not records:
        raise ValueError("At least one agent result is required")

    retrieval_counts = list(relevant_retrieval_counts)
    retrieved_total = sum(retrieved for retrieved, _ in retrieval_counts)
    relevant_total = sum(relevant for _, relevant in retrieval_counts)
    precision = (100 * relevant_total / retrieved_total) if retrieved_total else None

    percentage = lambda values: 100 * mean(values)
    return ExperimentMetrics(
        task_count=len(records),
        completion_rate_pct=percentage([record.completed for record in records]),
        avg_tool_calls=mean(record.tool_calls for record in records),
        avg_input_tokens=mean(record.input_tokens for record in records),
        avg_output_tokens=mean(record.output_tokens for record in records),
        avg_total_tokens=mean(record.input_tokens + record.output_tokens for record in records),
        avg_latency_seconds=mean(record.latency_ms for record in records) / 1000,
        repeated_error_rate_pct=percentage([record.repeated_error for record in records]),
        retrieval_precision_pct=precision,
        knowledge_transfer_success_rate_pct=percentage([record.transferred_knowledge for record in records]),
        stale_memory_error_rate_pct=percentage([record.stale_memory_error for record in records]),
        avg_retrieval_overhead_ms=mean(record.retrieval_overhead_ms for record in records),
    )


def baseline_changes(
    metrics: ExperimentMetrics,
    baseline: ExperimentMetrics,
) -> dict[str, dict[str, float | None]]:
    changes: dict[str, dict[str, float | None]] = {}
    for name, value in metrics.to_dict().items():
        baseline_value = baseline.to_dict()[name]
        if not isinstance(value, (int, float)) or not isinstance(baseline_value, (int, float)):
            continue
        absolute = value - baseline_value
        relative = None if baseline_value == 0 else 100 * absolute / baseline_value
        changes[name] = {"absolute": absolute, "relative_pct": relative}
    return changes
