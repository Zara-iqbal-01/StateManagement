import unittest
from datetime import datetime, timedelta, timezone

from state_management.models import MemoryMode, MemoryRecord, SelectionStrategy
from state_management.retrieval import retrieve


class RetrievalTests(unittest.TestCase):
    def setUp(self) -> None:
        now = datetime.now(timezone.utc)
        self.fund_memory = MemoryRecord(
            task_id="fund", mode=MemoryMode.SUMMARY,
            content="Resolve Direct Growth plan before calculating fund return.",
            created_at=now - timedelta(days=5),
        )
        self.recent_memory = MemoryRecord(
            task_id="rates", mode=MemoryMode.SUMMARY,
            content="Use the latest rate source.", created_at=now,
        )

    def test_relevance_prefers_matching_memory(self) -> None:
        result = retrieve(
            [self.recent_memory, self.fund_memory], "Calculate fund return for Direct Growth", top_k=1,
            strategy=SelectionStrategy.RELEVANCE,
        )
        self.assertEqual(result[0].memory.id, self.fund_memory.id)

    def test_recency_prefers_newest_memory(self) -> None:
        result = retrieve(
            [self.fund_memory, self.recent_memory], "Calculate fund return", top_k=1,
            strategy=SelectionStrategy.RECENCY,
        )
        self.assertEqual(result[0].memory.id, self.recent_memory.id)

    def test_top_k_must_be_positive(self) -> None:
        with self.assertRaises(ValueError):
            retrieve([], "query", top_k=0, strategy=SelectionStrategy.RELEVANCE)
