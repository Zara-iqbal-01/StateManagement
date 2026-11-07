"""SQLite persistence for experimental memories."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from .models import MemoryMode, MemoryRecord


class MemoryStore:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.database_path)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                mode TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                metadata_json TEXT NOT NULL
            )
            """
        )
        self._connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_memories_task_mode ON memories(task_id, mode)"
        )
        self._connection.commit()

    def close(self) -> None:
        self._connection.close()

    def add(self, memory: MemoryRecord) -> None:
        self._connection.execute(
            """
            INSERT INTO memories (id, task_id, mode, content, created_at, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                memory.id,
                memory.task_id,
                memory.mode.value,
                memory.content,
                memory.created_at.isoformat(),
                json.dumps(memory.metadata, sort_keys=True),
            ),
        )
        self._connection.commit()

    def list(self, mode: MemoryMode | None = None) -> list[MemoryRecord]:
        query = "SELECT id, task_id, mode, content, created_at, metadata_json FROM memories"
        values: tuple[str, ...] = ()
        if mode is not None:
            query += " WHERE mode = ?"
            values = (mode.value,)
        query += " ORDER BY created_at DESC, id DESC"
        rows = self._connection.execute(query, values).fetchall()
        return [self._to_memory(row) for row in rows]

    def clear(self) -> None:
        self._connection.execute("DELETE FROM memories")
        self._connection.commit()

    @staticmethod
    def _to_memory(row: sqlite3.Row) -> MemoryRecord:
        return MemoryRecord(
            id=row["id"],
            task_id=row["task_id"],
            mode=MemoryMode(row["mode"]),
            content=row["content"],
            created_at=datetime.fromisoformat(row["created_at"]),
            metadata=json.loads(row["metadata_json"]),
        )
