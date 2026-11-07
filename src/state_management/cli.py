"""Command-line entry point for the memory ablation harness."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone

from .metrics import aggregate
from .models import AgentResult, MemoryMode, MemoryRecord, SelectionStrategy
from .retrieval import retrieve


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run controlled ablations of raw, summarized, and structured agent memory."
    )
    parser.add_argument("--version", action="version", version="state-management 0.1.0")
    subcommands = parser.add_subparsers(dest="command")
    demo = subcommands.add_parser("demo", help="Run a deterministic local demonstration.")
    demo.add_argument("--strategy", choices=[strategy.value for strategy in SelectionStrategy], default="relevance")
    demo.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()

    if args.command != "demo":
        parser.print_help()
        return

    if args.top_k < 1:
        parser.error("--top-k must be at least 1")
    now = datetime.now(timezone.utc)
    memories = [
        MemoryRecord("fund-plan", MemoryMode.STRUCTURED_LESSON,
                     "Direct Growth plan must be resolved before calculating return.", now - timedelta(days=2)),
        MemoryRecord("market-news", MemoryMode.RAW_TRACE,
                     "Recent market news and rate discussion.", now),
    ]
    selected = retrieve(memories, "Calculate return for Direct Growth fund", top_k=args.top_k,
                        strategy=SelectionStrategy(args.strategy))
    metrics = aggregate([
        AgentResult("demo-1", True, "demo", 2, 140, 55, 1_200,
                    retrieved_memory_ids=tuple(result.memory.id for result in selected), retrieval_overhead_ms=3.2)
    ], relevant_retrieval_counts=[(len(selected), 1)])
    print(json.dumps({
        "strategy": args.strategy,
        "top_k": args.top_k,
        "retrieved_task_ids": [result.memory.task_id for result in selected],
        "metrics": metrics.to_dict(),
    }, indent=2))
