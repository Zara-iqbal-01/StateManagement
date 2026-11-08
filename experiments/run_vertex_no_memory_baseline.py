"""Run the fixed no-memory pilot through Vertex AI using local ADC.

No API key is read or written. The runner obtains a short-lived access token
from the locally configured Application Default Credentials.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def gcloud_command() -> str:
    """Find the CLI without depending on the original author's home directory."""
    configured = os.environ.get("GCLOUD_PATH")
    if configured:
        return configured
    command = shutil.which("gcloud.cmd") or shutil.which("gcloud")
    if command:
        return command
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidate = Path(local_app_data) / "Google/Cloud SDK/google-cloud-sdk/bin/gcloud.cmd"
        if candidate.is_file():
            return str(candidate)
    raise RuntimeError("Install Google Cloud CLI and add it to PATH, or set GCLOUD_PATH to its executable.")


SYSTEM_PROMPT = """You are evaluating a financial-data assistant in a controlled benchmark.
Use only the data supplied in the user message. Do not browse, call tools, use external knowledge, or claim that a value is live/current unless the supplied data itself says so.
Answer the user directly. Preserve entity, plan, period, metric, and units exactly as supported by the supplied data.
If the question is under-specified or cannot be answered from the supplied data, state the ambiguity or limitation rather than silently assuming facts."""


def adc_access_token() -> str:
    result = subprocess.run(
        [gcloud_command(), "auth", "application-default", "print-access-token"],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(f"Could not obtain an ADC access token: {result.stderr.strip()}")
    token = result.stdout.strip()
    if not token:
        raise RuntimeError("ADC returned an empty access token.")
    return token


def extract_text(payload: dict) -> str:
    candidates = payload.get("candidates", [])
    if not candidates:
        raise RuntimeError(f"Vertex returned no candidate: {payload}")
    text = "".join(part.get("text", "") for part in candidates[0].get("content", {}).get("parts", []))
    if not text:
        raise RuntimeError(f"Vertex response contains no text: {payload}")
    return text


def call_vertex(*, token: str, project: str, location: str, model: str, prompt: str) -> tuple[str, dict]:
    url = (
        f"https://aiplatform.googleapis.com/v1/projects/{project}/locations/{location}"
        f"/publishers/google/models/{model}:generateContent"
    )
    body = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
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
    return extract_text(payload), payload.get("usageMetadata", {})


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: python run_vertex_no_memory_baseline.py <tasks.jsonl> <results.jsonl>")
    manifest_path = Path(sys.argv[1]).resolve()
    results_path = Path(sys.argv[2]).resolve()
    answers_dir = results_path.parent / "vertex_answers"
    project = os.environ.get("VERTEX_AI_PROJECT_ID", "dsi-tifin-harness")
    location = os.environ.get("VERTEX_AI_LOCATION", "global")
    model = os.environ.get("VERTEX_MODEL", "gemini-3.5-flash-lite")
    tasks = [json.loads(line) for line in manifest_path.read_text(encoding="utf-8").splitlines() if line]
    existing_ids = set()
    if results_path.exists():
        existing_ids = {json.loads(line)["run_id"] for line in results_path.read_text(encoding="utf-8").splitlines() if line}
    answers_dir.mkdir(parents=True, exist_ok=True)
    token = adc_access_token()

    for task in tasks:
        run_id = f"vertex-none-direct-k0-{task['task_id']}-r1"
        if run_id in existing_ids:
            print(f"Skipping existing {run_id}")
            continue
        prompt = f"Question:\n{task['question']}\n\nData supplied for this task only:\n{task['provided_data']}"
        started = time.perf_counter()
        answer, usage = call_vertex(token=token, project=project, location=location, model=model, prompt=prompt)
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
            "answer_path": f"experiments/runs/vertex_answers/{answer_path.name}",
            "provider": "vertex_ai_adc",
            "project": project,
            "location": location,
            "model": model,
            "run_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }
        with results_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(result, ensure_ascii=False) + "\n")
        print(f"Completed {run_id}: {latency_ms} ms, {result['total_tokens']} tokens")


if __name__ == "__main__":
    main()
