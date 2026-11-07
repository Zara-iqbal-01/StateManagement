import unittest

import state_management
from state_management.models import MemoryMode, SelectionStrategy


class PackageTests(unittest.TestCase):
    def test_package_version(self) -> None:
        self.assertEqual(state_management.__version__, "0.1.0")

    def test_memory_enums_are_stable(self) -> None:
        self.assertEqual(MemoryMode.STRUCTURED_LESSON.value, "structured_lesson")
        self.assertEqual(SelectionStrategy.RELEVANCE.value, "relevance")
