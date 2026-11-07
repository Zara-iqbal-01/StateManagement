"""Construct equivalent raw, summarized, and structured memory records."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from .models import MemoryMode, MemoryRecord, TaskCase


def raw_trace(task: TaskCase, trace: str, *, created_at: datetime | None = None) -> MemoryRecord:
    return MemoryRecord(
        task_id=task.id,
        mode=MemoryMode.RAW_TRACE,
        content=trace,
        created_at=created_at or datetime.now(timezone.utc),
        metadata={"category": task.category, "representation": "raw"},
    )


def summary(
    task: TaskCase,
    summary_text: str,
    *,
    created_at: datetime | None = None,
) -> MemoryRecord:
    return MemoryRecord(
        task_id=task.id,
        mode=MemoryMode.SUMMARY,
        content=summary_text,
        created_at=created_at or datetime.now(timezone.utc),
        metadata={"category": task.category, "representation": "summary"},
    )


def structured_lesson(
    task: TaskCase,
    failure: str,
    corrective_action: str,
    validity_conditions: str,
    *,
    created_at: datetime | None = None,
) -> MemoryRecord:
    lesson = {
        "task_context": task.prompt,
        "failure": failure,
        "corrective_action": corrective_action,
        "validity_conditions": validity_conditions,
    }
    return MemoryRecord(
        task_id=task.id,
        mode=MemoryMode.STRUCTURED_LESSON,
        content=json.dumps(lesson, sort_keys=True),
        created_at=created_at or datetime.now(timezone.utc),
        metadata={"category": task.category, "representation": "structured_lesson"},
    )
