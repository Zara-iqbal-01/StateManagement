import json
import unittest

from state_management.models import MemoryMode, TaskCase
from state_management.representations import raw_trace, structured_lesson, summary


class RepresentationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.task = TaskCase("task-1", "Find the correct fund plan.", "repeated", "Direct Growth")

    def test_representations_preserve_task_identity(self) -> None:
        memories = [
            raw_trace(self.task, "tool trace"),
            summary(self.task, "Earlier search selected the wrong plan."),
            structured_lesson(self.task, "Used Regular", "Resolve plan first", "Only when a plan is specified"),
        ]

        self.assertEqual({memory.task_id for memory in memories}, {"task-1"})
        self.assertEqual([memory.mode for memory in memories], [
            MemoryMode.RAW_TRACE,
            MemoryMode.SUMMARY,
            MemoryMode.STRUCTURED_LESSON,
        ])
        lesson = json.loads(memories[2].content)
        self.assertEqual(lesson["corrective_action"], "Resolve plan first")
