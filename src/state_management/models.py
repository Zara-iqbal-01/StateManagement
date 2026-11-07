"""Typed records shared by storage, retrieval, and evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4


class MemoryMode(StrEnum):
    NONE = "none"
    RAW_TRACE = "raw_trace"
    SUMMARY = "summary"
    STRUCTURED_LESSON = "structured_lesson"


class SelectionStrategy(StrEnum):
    RELEVANCE = "relevance"
    RECENCY = "recency"


@dataclass(frozen=True)
class TaskCase:
    id: str
    prompt: str
    category: str
    expected_outcome: str
    related_to: str | None = None
    has_stale_information: bool = False


@dataclass(frozen=True)
class MemoryRecord:
    task_id: str
    mode: MemoryMode
    content: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid4()))


@dataclass(frozen=True)
class RetrievalResult:
    memory: MemoryRecord
    score: float


@dataclass(frozen=True)
class AgentResult:
    task_id: str
    completed: bool
    answer: str
    tool_calls: int
    input_tokens: int
    output_tokens: int
    latency_ms: float
    repeated_error: bool = False
    transferred_knowledge: bool = False
    stale_memory_error: bool = False
    retrieved_memory_ids: tuple[str, ...] = ()
    retrieval_overhead_ms: float = 0.0
