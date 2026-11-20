"""Build a harness task manifest (tasks.jsonl) from the English FinMCP-Bench multi-turn data.

Usage (from the StateManagement folder):
    python experiments/build_finmcp_manifest.py --max-episodes 4     # 12-task pilot
    python experiments/build_finmcp_manifest.py                      # all full episodes
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "finmcp"


def tool_context(full_rec: dict, max_chars: int) -> str:
    """Turn the gold tool calls + results into the 'data supplied' block."""
    msgs = full_rec["messages_en"]
    calls = {}
    for m in msgs:
        for tc in m.get("tool_calls") or []:
            calls[tc["id"]] = tc["function"]
    parts = []
    for m in msgs:
        if m["role"] != "tool":
            continue
        fn = calls.get(m.get("tool_call_id"), {})
        result = m.get("content") or ""
        if len(result) > max_chars:
            result = result[:max_chars] + f"\n...[truncated {len(result) - max_chars} chars]"
        parts.append(
            f"[Tool result {len(parts) + 1}] {m.get('name') or fn.get('name')}\n"
            f"Arguments: {fn.get('arguments', '')}\n{result}"
        )
    return "\n\n".join(parts) if parts else "(no tool data)"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "experiments" / "runs" / "finmcp" / "tasks.jsonl"))
    ap.add_argument("--episode-size", type=int, default=3)
    ap.add_argument("--max-episodes", type=int, default=0, help="0 = all full episodes")
    ap.add_argument("--max-tool-chars", type=int, default=6000, help="truncate each tool result")
    args = ap.parse_args()

    simple = json.load(open(DATA / "finmcp_multiturn_en_simplified.json", encoding="utf-8"))
    full = {r["id"]: r for r in json.load(open(DATA / "finmcp_multiturn_en_full.json", encoding="utf-8"))}

    by_scenario = defaultdict(list)
    for r in sorted(simple, key=lambda r: r["id"]):
        by_scenario[r["scenario"]].append(r)

    # Episodes = consecutive groups of N conversations from the same scenario.
    episodes, dropped = [], 0
    size = args.episode_size
    for scen, recs in by_scenario.items():
        chunks = [recs[i:i + size] for i in range(0, len(recs), size)]
        # a single leftover conversation joins the previous episode instead of standing alone
        if len(chunks) > 1 and len(chunks[-1]) == 1:
            chunks[-2].extend(chunks.pop())
        for k, chunk in enumerate(chunks):
            episodes.append((k, scen, chunk))
    # Interleave scenarios so a small --max-episodes still covers different scenarios.
    episodes.sort(key=lambda e: (e[0], e[1]))
    if args.max_episodes:
        episodes = episodes[: args.max_episodes]

    manifest = []
    for k, scen, recs in episodes:
        ep_name = f"{scen}-{k + 1:02d}"
        for turn, r in enumerate(recs, start=1):
            question = "\n\n".join(f"User (turn {t + 1}): {u}" for t, u in enumerate(r["user_turns"]))
            manifest.append({
                "task_id": f"finmcp-{r['id']}",
                "source_row": r["id"],
                "dataset": "finmcp",
                "episode": ep_name,
                "turn": turn,
                "scenario": scen,
                "difficulty": r["difficulty"],
                "question": question,
                "provided_data": tool_context(full[r["id"]], args.max_tool_chars),
                "intended_reading": r["user_goal"],
                "figure_meaning": "",
                "persona": r["persona"],
                "gold_tool_calls": r["gold_tool_calls"],
                "expected_answer": r["final_answer"],
                "lesson_target": "",
                "success_rule": "Answer the user's goal using only the supplied tool results; "
                                "label every number correctly; flag anything the data does not support.",
            })

    assert len({t["task_id"] for t in manifest}) == len(manifest), "duplicate task ids"
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for t in manifest:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")

    print(f"Wrote {len(manifest)} tasks in {len(episodes)} episodes -> {out}")
    print(f"Conversations not in a full episode (dropped): {dropped}")
    for t in manifest[:6]:
        print(f"  {t['task_id']} | {t['episode']} | turn {t['turn']} | {t['difficulty']}")


if __name__ == "__main__":
    main()