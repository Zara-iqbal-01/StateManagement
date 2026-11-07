import unittest

from state_management.metrics import aggregate, baseline_changes
from state_management.models import AgentResult


class MetricsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.results = [
            AgentResult("a", True, "ok", 3, 100, 20, 1_000, retrieved_memory_ids=("m1",), retrieval_overhead_ms=10),
            AgentResult("b", False, "bad", 5, 200, 30, 3_000, repeated_error=True, stale_memory_error=True,
                        retrieved_memory_ids=("m2", "m3"), retrieval_overhead_ms=30),
        ]

    def test_aggregate_calculates_requested_metrics(self) -> None:
        metrics = aggregate(self.results, relevant_retrieval_counts=[(1, 1), (2, 1)])
        self.assertEqual(metrics.task_count, 2)
        self.assertEqual(metrics.completion_rate_pct, 50.0)
        self.assertEqual(metrics.avg_total_tokens, 175)
        self.assertAlmostEqual(metrics.retrieval_precision_pct or 0, 66.666, places=2)
        self.assertEqual(metrics.stale_memory_error_rate_pct, 50.0)

    def test_baseline_changes_reports_absolute_and_relative_deltas(self) -> None:
        baseline = aggregate([self.results[1]])
        candidate = aggregate([self.results[0]])
        changes = baseline_changes(candidate, baseline)
        self.assertEqual(changes["completion_rate_pct"]["absolute"], 100.0)
        self.assertEqual(changes["avg_tool_calls"]["relative_pct"], -40.0)
