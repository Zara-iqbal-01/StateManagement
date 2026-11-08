"""A Python function-calling harness for questions represented in dataset1.xlsx.

Set OPENAI_API_KEY, then run:
  python tools/dataset_agent.py "Is SBI Bluechip better than Axis Bluechip over a 5 year SIP?"

Use --dry-run to inspect the Python tool result without calling a model.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dataset_research_planner import DEFAULT_DATASET, plan_for_question


TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "plan_dataset_research",
        "description": (
            "Look up a natural-language question in the dataset evidence store. "
            "Return supplied data, what every figure actually measures, and a safe tool plan. "
            "Call this before making a claim about a dataset question."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The user's original natural-language question, unchanged.",
                },
            },
            "required": ["question"],
            "additionalProperties": False,
        },
    },
}

SYSTEM_PROMPT = """You answer financial-research questions using the available Python tools.
Always call plan_dataset_research first. Use its data_measurement as a hard constraint:
never relabel a figure as a different metric, entity, plan, period, or unit. If its plan
requires live research, say that live tools need to be configured rather than inventing data."""


def call_openai(payload: dict[str, Any], api_key: str) -> dict[str, Any]:
    request = Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=90) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI API error {error.code}: {detail}") from error
    except URLError as error:
        raise RuntimeError(f"Could not reach the OpenAI API: {error.reason}") from error


def run_agent(question: str, dataset_path: Path, model: str, api_key: str) -> str:
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    first = call_openai({
        "model": model,
        "messages": messages,
        "tools": [TOOL_DEFINITION],
        "tool_choice": {"type": "function", "function": {"name": "plan_dataset_research"}},
    }, api_key)
    message = first["choices"][0]["message"]
    tool_calls = message.get("tool_calls", [])
    if not tool_calls:
        raise RuntimeError("The model did not call plan_dataset_research.")

    messages.append(message)
    for call in tool_calls:
        if call["function"]["name"] != "plan_dataset_research":
            continue
        arguments = json.loads(call["function"]["arguments"])
        tool_question = arguments.get("question")
        if not isinstance(tool_question, str) or not tool_question.strip():
            raise RuntimeError("The model sent an invalid question to plan_dataset_research.")
        messages.append({
            "role": "tool",
            "tool_call_id": call["id"],
            "content": json.dumps(plan_for_question(tool_question, dataset_path), ensure_ascii=False),
        })

    final = call_openai({"model": model, "messages": messages}, api_key)
    return final["choices"][0]["message"].get("content", "")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a natural-language question through a model and the dataset Python tool.")
    parser.add_argument("question", help="Natural-language financial question.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET, help="Path to dataset1.xlsx.")
    parser.add_argument("--model", default=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"), help="OpenAI model name.")
    parser.add_argument("--dry-run", action="store_true", help="Print the Python tool result without calling a model.")
    args = parser.parse_args()

    if not args.dataset.is_file():
        parser.error(f"Dataset not found: {args.dataset}")
    if args.dry_run:
        print(json.dumps(plan_for_question(args.question, args.dataset), ensure_ascii=False, indent=2))
        return

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        parser.error("Set OPENAI_API_KEY before running the model harness, or use --dry-run.")
    print(run_agent(args.question, args.dataset, args.model, api_key))


if __name__ == "__main__":
    main()
