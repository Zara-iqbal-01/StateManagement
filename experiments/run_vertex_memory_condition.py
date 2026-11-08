"""Run raw-trace or summary memory conditions through Vertex AI with ADC."""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

EXPERIMENT_ROOT = Path(__file__).resolve().parent
STATE_MANAGEMENT_ROOT = EXPERIMENT_ROOT.parent
sys.path.insert(0, str(STATE_MANAGEMENT_ROOT / "src"))

from state_management.models import MemoryMode, SelectionStrategy, TaskCase
from state_management.representations import raw_trace, summary
from state_management.retrieval import retrieve
from state_management.store import MemoryStore
from run_vertex_structured_lessons import call_with_system
from run_vertex_no_memory_baseline import adc_access_token


TASK_SYSTEM_PROMPT = """You are evaluating a financial-data assistant in a controlled benchmark.
Use only the data supplied in the current user message. A retrieved past experience is optional context; apply it only if it is relevant and never let it override the current supplied data.
Do not browse, call tools, use external knowledge, or claim that a value is live/current unless the current supplied data itself says so.
Answer the user directly. Preserve entity, plan, period, metric, and units exactly as supported by the current supplied data.
If the question is under-specified or cannot be answered from the current supplied data, state the ambiguity or limitation rather than silently assuming facts."""

SUMMARY_SYSTEM_PROMPT = """Summarize a completed benchmark task for possible reuse on closely related tasks.
Use only the question, supplied data, and assistant answer. Do not claim external facts were checked.
Write at most 90 words. Include the entity/plan/metric distinction that matters and one caution for a future related task."""


def count(usage: dict, key: str) -> int | None:
    value = usage.get(key)
    return int(value) if isinstance(value, int) else None


def main() -> None:
    if len(sys.argv) != 5:
        raise SystemExit("Usage: python run_vertex_memory_condition.py <raw_trace|summary> <tasks.jsonl> <results.jsonl> <memory.sqlite3>")
    mode_name, manifest_arg, results_arg, memory_arg = sys.argv[1:]
    if mode_name not in ("raw_trace", "summary"):
        raise SystemExit("Mode must be raw_trace or summary.")
    mode = MemoryMode(mode_name)
    manifest_path, results_path, memory_path = (Path(path).resolve() for path in (manifest_arg, results_arg, memory_arg))
    answers_dir = results_path.parent / f"{mode_name}_answers"
    project = os.environ.get("VERTEX_AI_PROJECT_ID", "dsi-tifin-harness")
    location = os.environ.get("VERTEX_AI_LOCATION", "global")
    model = os.environ.get("VERTEX_MODEL", "gemini-3.5-flash-lite")
    tasks = [json.loads(line) for line in manifest_path.read_text(encoding="utf-8").splitlines() if line]
    existing_ids = set()
    if results_path.exists():
        existing_ids = {json.loads(line)["run_id"] for line in results_path.read_text(encoding="utf-8").splitlines() if line}
    answers_dir.mkdir(parents=True, exist_ok=True)
    token = adc_access_token()
    store = MemoryStore(memory_path)

    try:
        for task in tasks:
            run_id = f"vertex-{mode_name}-relevance-k1-{task['task_id']}-r1"
            if run_id in existing_ids:
                print(f"Skipping existing {run_id}")
                continue
            retrieval_started = time.perf_counter()
            retrieved = []
            if task["turn"] in (2, 3):
                retrieved = retrieve(store.list(mode), task["question"], top_k=1, strategy=SelectionStrategy.RELEVANCE)
            retrieval_overhead_ms = round((time.perf_counter() - retrieval_started) * 1000, 3)
            past_context = f"\n\nRetrieved past experience:\n{retrieved[0].memory.content}" if retrieved else ""
            task_prompt = f"Current question:\n{task['question']}\n\nCurrent supplied data only:\n{task['provided_data']}{past_context}"

            answer_started = time.perf_counter()
            answer, answer_usage = call_with_system(
                token=token, project=project, location=location, model=model,
                prompt=task_prompt, system_prompt=TASK_SYSTEM_PROMPT,
            )
            answer_latency_ms = round((time.perf_counter() - answer_started) * 1000)
            storage_text = ""
            storage_usage: dict = {}
            storage_latency_ms = 0
            task_case = TaskCase(task["task_id"], task["question"], task["episode"], "")
            if mode is MemoryMode.RAW_TRACE:
                storage_text = json.dumps({"question": task["question"], "provided_data": task["provided_data"], "answer": answer}, ensure_ascii=False)
                memory = raw_trace(task_case, storage_text)
            else:
                summary_prompt = f"Task question:\n{task['question']}\n\nSupplied data:\n{task['provided_data']}\n\nAssistant answer:\n{answer}"
                storage_started = time.perf_counter()
                storage_text, storage_usage = call_with_system(
                    token=token, project=project, location=location, model=model,
                    prompt=summary_prompt, system_prompt=SUMMARY_SYSTEM_PROMPT,
                )
                storage_latency_ms = round((time.perf_counter() - storage_started) * 1000)
                memory = summary(task_case, storage_text)
            store.add(memory)

            answer_path = answers_dir / f"{run_id}.txt"
            answer_path.write_text(answer, encoding="utf-8")
            input_tokens = sum(value or 0 for value in (count(answer_usage, "promptTokenCount"), count(storage_usage, "promptTokenCount")))
            output_tokens = sum(value or 0 for value in (count(answer_usage, "candidatesTokenCount"), count(storage_usage, "candidatesTokenCount")))
            total_tokens = sum(value or 0 for value in (count(answer_usage, "totalTokenCount"), count(storage_usage, "totalTokenCount")))
            result = {
                "run_id": run_id, "condition": mode_name, "selection_strategy": "relevance", "top_k": 1,
                "task_id": task["task_id"], "source_row": task["source_row"], "episode": task["episode"], "turn": task["turn"], "repeat": 1,
                "completed": None, "tool_calls": 0, "input_tokens": input_tokens, "output_tokens": output_tokens,
                "total_tokens": total_tokens, "latency_ms": answer_latency_ms + storage_latency_ms,
                "answer_latency_ms": answer_latency_ms, "memory_write_latency_ms": storage_latency_ms,
                "retrieval_overhead_ms": retrieval_overhead_ms,
                "retrieved_memory_ids": [item.memory.id for item in retrieved],
                "retrieval_scores": [item.score for item in retrieved],
                "retrieval_relevant": all(item.memory.metadata.get("category") == task["episode"] for item in retrieved) if retrieved else None,
                "repeated_error": None, "transfer_success": None, "stale_memory_error": None,
                "memory_id": memory.id, "answer_path": f"experiments/runs/{mode_name}_answers/{answer_path.name}",
                "provider": "vertex_ai_adc", "project": project, "location": location, "model": model,
                "run_timestamp_utc": datetime.now(timezone.utc).isoformat(),
            }
            with results_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(result, ensure_ascii=False) + "\n")
            print(f"Completed {run_id}: {result['latency_ms']} ms, {total_tokens} tokens")
    finally:
        store.close()


if __name__ == "__main__":
    main()
