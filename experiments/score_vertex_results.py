"""Create auditable preliminary labels for the four Vertex experiment conditions."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

EXPERIMENT_ROOT = Path(__file__).resolve().parent
STATE_MANAGEMENT_ROOT = EXPERIMENT_ROOT.parent
sys.path.insert(0, str(STATE_MANAGEMENT_ROOT / "src"))

from run_vertex_structured_lessons import call_with_system
from run_vertex_no_memory_baseline import adc_access_token


JUDGE_SYSTEM_PROMPT = """You are a strict evaluator of financial-data assistant answers.
Judge only from the benchmark metadata and the supplied answer. Do not use outside facts.
An answer is complete if it addresses the intended reading and labels each quantity according to what the supplied data actually measures.
For an under-specified plan, investment mode, entity, or live-data request, explicitly flagging ambiguity or asking for clarification is acceptable; silently choosing is not.
Return only JSON with exactly: completed (boolean), repeated_error (boolean), stale_memory_error (boolean), reason (string).
`repeated_error` applies only if the current answer repeats the same error pattern seen in the earlier answer from this episode; otherwise false.
`stale_memory_error` applies only if prior memory leads the answer to ignore the current supplied data or misrepresent a supplied snapshot as live/current; otherwise false."""


def parse_json(text: str) -> dict:
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = candidate.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    parsed = json.loads(candidate)
    required = {"completed", "repeated_error", "stale_memory_error", "reason"}
    if set(parsed) != required or not all(isinstance(parsed[key], bool) for key in required - {"reason"}):
        raise ValueError(f"Unexpected judge JSON: {parsed}")
    if not isinstance(parsed["reason"], str):
        raise ValueError(f"Judge reason is not text: {parsed}")
    return parsed


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit("Usage: python score_vertex_results.py <tasks.jsonl> <runs_dir> <labels.jsonl>")
    manifest_path, runs_dir, labels_path = (Path(value).resolve() for value in sys.argv[1:])
    project = os.environ.get("VERTEX_AI_PROJECT_ID", "dsi-tifin-harness")
    location = os.environ.get("VERTEX_AI_LOCATION", "global")
    model = os.environ.get("VERTEX_MODEL", "gemini-3.5-flash-lite")
    tasks = {task["task_id"]: task for task in (json.loads(line) for line in manifest_path.read_text(encoding="utf-8").splitlines() if line)}
    run_files = [
        runs_dir / "vertex_results.jsonl",
        runs_dir / "raw_trace_results.jsonl",
        runs_dir / "summary_results.jsonl",
        runs_dir / "structured_lesson_results.jsonl",
    ]
    records = [json.loads(line) for file in run_files for line in file.read_text(encoding="utf-8").splitlines() if line]
    existing = {json.loads(line)["run_id"] for line in labels_path.read_text(encoding="utf-8").splitlines() if line} if labels_path.exists() else set()
    token = adc_access_token()
    prior_answers: dict[tuple[str, str], list[str]] = {}

    for record in sorted(records, key=lambda item: (item["condition"], item.get("episode", ""), item.get("turn", 1))):
        task = tasks[record["task_id"]]
        answer = (STATE_MANAGEMENT_ROOT / record["answer_path"]).read_text(encoding="utf-8")
        key = (record["condition"], task["episode"])
        earlier = prior_answers.setdefault(key, [])
        if record["run_id"] in existing:
            earlier.append(answer)
            continue
        prior_text = "\n\nEarlier answer(s) in this episode:\n" + "\n---\n".join(earlier) if earlier else ""
        prompt = (
            f"Question asked:\n{task['question']}\n\n"
            f"Intended reading:\n{task['intended_reading']}\n\n"
            f"What the supplied figures actually measure:\n{task['figure_meaning']}\n\n"
            f"Current answer:\n{answer}\n"
            f"Current task has retrieval: {bool(record.get('retrieved_memory_ids'))}.\n"
            f"This is a stale-data episode: {task['episode'] == 'stale_data'}."
            f"{prior_text}"
        )
        text, usage = call_with_system(
            token=token, project=project, location=location, model=model,
            prompt=prompt, system_prompt=JUDGE_SYSTEM_PROMPT,
        )
        judgement = parse_json(text)
        label = {
            "run_id": record["run_id"], "condition": record["condition"], "task_id": record["task_id"],
            "episode": task["episode"], "turn": task["turn"], "judge_model": model,
            "completed": judgement["completed"], "repeated_error": judgement["repeated_error"] if task["turn"] in (2, 3) else False,
            "stale_memory_error": judgement["stale_memory_error"] if task["episode"] == "stale_data" else False,
            "reason": judgement["reason"], "judge_total_tokens": usage.get("totalTokenCount"),
        }
        with labels_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(label, ensure_ascii=False) + "\n")
        earlier.append(answer)
        print(f"Scored {record['run_id']}: completed={label['completed']}")


if __name__ == "__main__":
    main()
