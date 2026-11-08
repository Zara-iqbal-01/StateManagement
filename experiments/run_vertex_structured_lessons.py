"""Run the structured-lesson memory condition through Vertex AI with ADC."""

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
from state_management.representations import structured_lesson
from state_management.retrieval import retrieve
from state_management.store import MemoryStore
from run_vertex_no_memory_baseline import adc_access_token, call_vertex


TASK_SYSTEM_PROMPT = """You are evaluating a financial-data assistant in a controlled benchmark.
Use only the data supplied in the current user message. You may use a retrieved structured lesson only as a corrective guideline and only when its validity conditions fit the current task.
Do not browse, call tools, use external knowledge, or claim that a value is live/current unless the current supplied data itself says so.
Answer the user directly. Preserve entity, plan, period, metric, and units exactly as supported by the current supplied data.
If the question is under-specified or cannot be answered from the current supplied data, state the ambiguity or limitation rather than silently assuming facts."""

LESSON_SYSTEM_PROMPT = """Create one structured lesson from a completed benchmark task.
Use only the task question, supplied data, and assistant answer. Do not claim that external facts were checked.
Return only a JSON object with exactly these non-empty string fields: failure, corrective_action, validity_conditions.
If the answer did not show an error, describe the main failure to avoid on a close future task."""


def call_with_system(*, token: str, project: str, location: str, model: str, prompt: str, system_prompt: str) -> tuple[str, dict]:
    # Reuse the Vertex caller while temporarily selecting its system prompt through a local request.
    from urllib.error import HTTPError, URLError
    from urllib.request import Request, urlopen

    url = (
        f"https://aiplatform.googleapis.com/v1/projects/{project}/locations/{location}"
        f"/publishers/google/models/{model}:generateContent"
    )
    body = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
    }
    request = Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=90) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Vertex HTTP {error.code}: {detail}") from error
    except URLError as error:
        raise RuntimeError(f"Vertex network error: {error}") from error
    candidates = payload.get("candidates", [])
    text = "".join(part.get("text", "") for part in candidates[0].get("content", {}).get("parts", [])) if candidates else ""
    if not text:
        raise RuntimeError(f"Vertex response contains no text: {payload}")
    return text, payload.get("usageMetadata", {})


def parse_lesson(text: str) -> dict[str, str]:
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = candidate.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    lesson = json.loads(candidate)
    required = ("failure", "corrective_action", "validity_conditions")
    if any(not isinstance(lesson.get(key), str) or not lesson[key].strip() for key in required):
        raise ValueError("Lesson JSON must contain non-empty required strings.")
    return {key: lesson[key].strip() for key in required}


def token_count(usage: dict, name: str) -> int | None:
    value = usage.get(name)
    return int(value) if isinstance(value, int) else None


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit("Usage: python run_vertex_structured_lessons.py <tasks.jsonl> <results.jsonl> <memory.sqlite3>")
    manifest_path = Path(sys.argv[1]).resolve()
    results_path = Path(sys.argv[2]).resolve()
    memory_path = Path(sys.argv[3]).resolve()
    answers_dir = results_path.parent / "structured_answers"
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
            run_id = f"vertex-structured_lesson-relevance-k1-{task['task_id']}-r1"
            if run_id in existing_ids:
                print(f"Skipping existing {run_id}")
                continue

            retrieval_started = time.perf_counter()
            retrieved = []
            if task["turn"] in (2, 3):
                retrieved = retrieve(
                    store.list(MemoryMode.STRUCTURED_LESSON),
                    task["question"],
                    top_k=1,
                    strategy=SelectionStrategy.RELEVANCE,
                )
            retrieval_overhead_ms = round((time.perf_counter() - retrieval_started) * 1000, 3)
            lesson_context = ""
            if retrieved:
                lesson_context = f"\n\nRetrieved structured lesson:\n{retrieved[0].memory.content}"

            task_prompt = (
                f"Current question:\n{task['question']}\n\n"
                f"Current supplied data only:\n{task['provided_data']}"
                f"{lesson_context}"
            )
            answer_started = time.perf_counter()
            answer, answer_usage = call_with_system(
                token=token, project=project, location=location, model=model,
                prompt=task_prompt, system_prompt=TASK_SYSTEM_PROMPT,
            )
            answer_latency_ms = round((time.perf_counter() - answer_started) * 1000)

            lesson_prompt = (
                f"Task question:\n{task['question']}\n\nSupplied data:\n{task['provided_data']}\n\n"
                f"Assistant answer:\n{answer}"
            )
            lesson_started = time.perf_counter()
            lesson_text, lesson_usage = call_with_system(
                token=token, project=project, location=location, model=model,
                prompt=lesson_prompt, system_prompt=LESSON_SYSTEM_PROMPT,
            )
            lesson_latency_ms = round((time.perf_counter() - lesson_started) * 1000)
            lesson = parse_lesson(lesson_text)
            task_case = TaskCase(
                id=task["task_id"], prompt=task["question"], category=task["episode"], expected_outcome="",
                related_to=None, has_stale_information=task["episode"] == "stale_data",
            )
            memory = structured_lesson(task_case, **lesson)
            store.add(memory)

            answer_path = answers_dir / f"{run_id}.txt"
            answer_path.write_text(answer, encoding="utf-8")
            input_tokens = sum(value or 0 for value in (token_count(answer_usage, "promptTokenCount"), token_count(lesson_usage, "promptTokenCount")))
            output_tokens = sum(value or 0 for value in (token_count(answer_usage, "candidatesTokenCount"), token_count(lesson_usage, "candidatesTokenCount")))
            total_tokens = sum(value or 0 for value in (token_count(answer_usage, "totalTokenCount"), token_count(lesson_usage, "totalTokenCount")))
            result = {
                "run_id": run_id,
                "condition": "structured_lesson",
                "selection_strategy": "relevance",
                "top_k": 1,
                "task_id": task["task_id"],
                "source_row": task["source_row"],
                "episode": task["episode"],
                "turn": task["turn"],
                "repeat": 1,
                "completed": None,
                "tool_calls": 0,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "latency_ms": answer_latency_ms + lesson_latency_ms,
                "answer_latency_ms": answer_latency_ms,
                "lesson_generation_latency_ms": lesson_latency_ms,
                "retrieval_overhead_ms": retrieval_overhead_ms,
                "retrieved_memory_ids": [item.memory.id for item in retrieved],
                "retrieval_scores": [item.score for item in retrieved],
                "retrieval_relevant": all(item.memory.metadata.get("category") == task["episode"] for item in retrieved) if retrieved else None,
                "repeated_error": None,
                "transfer_success": None,
                "stale_memory_error": None,
                "lesson_memory_id": memory.id,
                "lesson": json.loads(memory.content),
                "answer_path": f"experiments/runs/structured_answers/{answer_path.name}",
                "provider": "vertex_ai_adc",
                "project": project,
                "location": location,
                "model": model,
                "run_timestamp_utc": datetime.now(timezone.utc).isoformat(),
            }
            with results_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(result, ensure_ascii=False) + "\n")
            print(f"Completed {run_id}: {result['latency_ms']} ms, {total_tokens} tokens")
    finally:
        store.close()


if __name__ == "__main__":
    main()
