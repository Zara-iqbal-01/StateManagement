r"""Plan research for natural-language questions stored in the Review sheet.

Examples:
  python tools/dataset_research_planner.py "Is SBI Bluechip better than Axis Bluechip over a 5 year SIP?"
  python tools/dataset_research_planner.py --dataset C:\path\to\dataset1.xlsx
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
import os
from pathlib import Path
from typing import Iterable

import openpyxl


DEFAULT_DATASET = Path(os.environ.get("DATASET_PATH", Path.home() / "Downloads" / "dataset1.xlsx"))
STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how", "i", "in",
    "is", "it", "my", "of", "on", "or", "the", "this", "to", "was", "what", "which", "with", "you",
}


@dataclass(frozen=True)
class DatasetRecord:
    item: int
    question: str
    intended_question: str
    supplied_data: str
    data_measurement: str


@dataclass(frozen=True)
class PlanStep:
    tool: str
    purpose: str
    query: str | None = None


def text(value: object) -> str:
    return "" if value is None else str(value)


def load_records(dataset_path: Path) -> list[DatasetRecord]:
    workbook = openpyxl.load_workbook(dataset_path, read_only=True, data_only=True)
    try:
        sheet = workbook["Review"]
        records: list[DatasetRecord] = []
        for item, question, intended, supplied, measurement, *_ in sheet.iter_rows(min_row=2, values_only=True):
            if item is None:
                continue
            records.append(DatasetRecord(
                item=int(item),
                question=text(question),
                intended_question=text(intended),
                supplied_data=text(supplied),
                data_measurement=text(measurement),
            ))
        return records
    finally:
        workbook.close()


def keywords(value: str) -> set[str]:
    return {
        word for word in re.findall(r"[a-z0-9]+", value.lower())
        if len(word) > 1 and word not in STOP_WORDS
    }


def similarity(left: str, right: str) -> float:
    left_words, right_words = keywords(left), keywords(right)
    if not left_words and not right_words:
        return 0.0
    return 2 * len(left_words & right_words) / (len(left_words) + len(right_words))


def find_record(question: str, records: Iterable[DatasetRecord]) -> DatasetRecord | None:
    normalized_question = " ".join(keywords(question))
    candidates = list(records)
    for record in candidates:
        if normalized_question in {" ".join(keywords(record.question)), " ".join(keywords(record.intended_question))}:
            return record

    best_record: DatasetRecord | None = None
    best_score = 0.0
    for record in candidates:
        score = max(similarity(question, record.question), similarity(question, record.intended_question))
        if score > best_score:
            best_record, best_score = record, score

    return best_record if best_score >= 0.7 else None


def needs_live_research(record: DatasetRecord) -> bool:
    supplied = record.supplied_data.strip().lower()
    return supplied == "(no data given)" or "fetched through tools" in supplied


def build_plan(question: str, record: DatasetRecord | None) -> list[PlanStep]:
    if record is None:
        return [
            PlanStep("web_search", "Find a primary or issuer source because there is no matching dataset evidence.", question),
            PlanStep("browser", "Read the primary source and verify the exact plan, metric, date, and unit."),
        ]

    plan = [PlanStep("dataset_evidence", "Use the supplied evidence and its measurement note before making any claim.")]
    if needs_live_research(record):
        plan.extend([
            PlanStep("web_search", "Find a primary or issuer source for the missing live data.", record.intended_question),
            PlanStep("browser", "Read the primary source and verify the exact plan, metric, date, and unit."),
        ])
    return plan


def plan_for_question(question: str, dataset_path: Path = DEFAULT_DATASET) -> dict[str, object]:
    """Return the evidence and tool plan used by the agent harness."""
    record = find_record(question, load_records(dataset_path))
    return {
        "matched": record is not None,
        "record": asdict(record) if record else None,
        "research_plan": [asdict(step) for step in build_plan(question, record)],
        "response_guidance": (
            "Use only figures supported by supplied_data. Label each figure exactly as data_measurement describes it."
            if record and not needs_live_research(record)
            else "Use primary live sources and state any unresolved ambiguity."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Plan safe research using the Excel Review-sheet evidence.")
    parser.add_argument("question", nargs="?", help="Natural-language question. Leave blank for interactive input.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET, help="Path to the .xlsx dataset.")
    args = parser.parse_args()

    question = args.question or input("Question: ").strip()
    if not question:
        parser.error("A question is required.")
    if not args.dataset.is_file():
        parser.error(f"Dataset not found: {args.dataset}")

    print(json.dumps(plan_for_question(question, args.dataset), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
