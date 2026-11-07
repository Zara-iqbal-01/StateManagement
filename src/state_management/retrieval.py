"""Deterministic relevance and recency memory selection."""

from __future__ import annotations

import re
from collections.abc import Iterable

from .models import MemoryRecord, RetrievalResult, SelectionStrategy


def tokenize(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", value.lower()))


def relevance_score(query: str, memory: MemoryRecord) -> float:
    query_tokens = tokenize(query)
    memory_tokens = tokenize(memory.content)
    if not query_tokens or not memory_tokens:
        return 0.0
    return len(query_tokens & memory_tokens) / len(query_tokens | memory_tokens)


def retrieve(
    memories: Iterable[MemoryRecord],
    query: str,
    *,
    top_k: int,
    strategy: SelectionStrategy,
) -> list[RetrievalResult]:
    if top_k < 1:
        raise ValueError("top_k must be at least 1")

    results = [RetrievalResult(memory=memory, score=relevance_score(query, memory)) for memory in memories]
    if strategy is SelectionStrategy.RELEVANCE:
        results.sort(key=lambda result: (result.score, result.memory.created_at), reverse=True)
    else:
        results.sort(key=lambda result: result.memory.created_at, reverse=True)
    return results[:top_k]
