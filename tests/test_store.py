import unittest
from pathlib import Path

from state_management.models import MemoryMode, MemoryRecord
from state_management.store import MemoryStore


class MemoryStoreTests(unittest.TestCase):
    def test_add_and_filter_memories(self) -> None:
        database_path = Path(__file__).parent / ".state-management-test.sqlite3"
        database_path.unlink(missing_ok=True)
        try:
            store = MemoryStore(database_path)
            store.add(MemoryRecord(task_id="task-1", mode=MemoryMode.RAW_TRACE, content="raw"))
            store.add(MemoryRecord(task_id="task-1", mode=MemoryMode.SUMMARY, content="summary"))

            self.assertEqual(len(store.list()), 2)
            summaries = store.list(MemoryMode.SUMMARY)
            self.assertEqual([memory.content for memory in summaries], ["summary"])
            store.close()
        finally:
            database_path.unlink(missing_ok=True)
