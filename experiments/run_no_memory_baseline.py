"""Run the fixed no-memory pilot directly against the Gemini REST API.

The API key is read only from GOOGLE_API_KEY in the process environment.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


SYSTEM_PROMPT = """You are evaluating a financial-data assistant in a controlled benchmark.
Use only the data supplied in the user message. Do not browse, call tools, use external knowledge, or claim that a value is live/current unless the supplied data itself says so.
Answer the user directly. Preserve entity, plan, period, metric, and units exactly as supported by the supplied data.
If the question is under-specified or cannot be answered from the supplied data, state the ambiguity or limitation rather than silently assuming facts."""


def extract_text(response: dict) -> str:
    candidates = response.get("candidates", [])
    if not candidates:
        raise RuntimeError(f"Gemini returned no candidate: {response}")
    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(part.get("text", "") for part in parts)
    if not text:
        raise RuntimeError(f"Gemini response contains no text: {response}")
    return text


def call_gemini(*, key: str, model: str, prompt: str) -> tuple[str, dict]:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{quote(model, safe='')}:generateContent?key={quote(key, safe='')}"
    body = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
    }
    request = Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=90) as response:
            return extract_text(json.loads(response.read().decode("utf-8"))), json.loads(response.headers.get("X-Usage-Metadata", "{}"))
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini HTTP {error.code}: {detail}") from error
    except URLError as error:
        raise RuntimeError(f"Gemini network error: {error}") from error


def call_gemini_with_usage(*, key: str, model: str, prompt: str) -> tuple[str, dict]:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{quote(model, safe='')}:generateContent?key={quote(key, safe='')}"
    body = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
    }
    request = Request(url, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=90) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini HTTP {error.code}: {detail}") from error
    except URLError as error:
        raise RuntimeError(f"Gemini network error: {error}") from error
    return extract_text(payload), payload.get("usageMetadata", {})


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: python run_no_memory_baseline.py <tasks.jsonl> <results.jsonl>")
    key = os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise SystemExit("GOOGLE_API_KEY is required in the process environment.")

    manifest_path = Path(sys.argv[1]).resolve()
    results_path = Path(sys.argv[2]).resolve()
    answers_dir = results_path.parent / "answers"
    model = os.environ.get("BASELINE_MODEL", "gemini-3.8-flash")
    tasks = [json.loads(line) for line in manifest_path.read_text(encoding="utf-8").splitlines() if line]
    existing_ids = set()
    if results_path.exists():
        existing_ids = {json.loads(line)["run_id"] for line in results_path.read_text(encoding="utf-8").splitlines() if line}
    answers_dir.mkdir(parents=True, exist_ok=True)

    for task in tasks:
        run_id = f"none-direct-k0-{task['task_id']}-r1"
        if run_id in existing_ids:
            print(f"Skipping existing {run_id}")
            continue
        prompt = f"Question:\n{task['question']}\n\nData supplied for this task only:\n{task['provided_data']}"
        started = time.perf_counter()
        answer, usage = call_gemini_with_usage(key=key, model=model, prompt=prompt)
        latency_ms = round((time.perf_counter() - started) * 1000)
        answer_path = answers_dir / f"{run_id}.txt"
        answer_path.write_text(answer, encoding="utf-8")
        result = {
            "run_id": run_id,
            "condition": "none",
            "selection_strategy": "none",
            "top_k": 0,
            "task_id": task["task_id"],
            "source_row": task["source_row"],
            "repeat": 1,
            "completed": None,
            "tool_calls": 0,
            "input_tokens": usage.get("promptTokenCount"),
            "output_tokens": usage.get("candidatesTokenCount"),
            "total_tokens": usage.get("totalTokenCount"),
            "latency_ms": latency_ms,
            "retrieval_overhead_ms": 0,
            "retrieved_memory_ids": [],
            "retrieval_relevant": None,
            "repeated_error": None,
            "transfer_success": None,
            "stale_memory_error": None,
            "answer_path": f"experiments/runs/answers/{answer_path.name}",
            "model": model,
            "run_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }
        with results_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(result, ensure_ascii=False) + "\n")
        print(f"Completed {run_id}: {latency_ms} ms, {result['total_tokens']} tokens")


if __name__ == "__main__":
    main()
