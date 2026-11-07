# State Management

A small, dependency-free Python harness for controlled ablations of agent memory.

It models the four conditions in the accompanying study:

1. No persistent memory.
2. Raw task traces.
3. Summarized experiences.
4. Structured lessons containing task context, failure, corrective action, and validity conditions.

It also supports relevance- and recency-based selection with configurable top-k retrieval.

## Run locally

Requires Python 3.10 or later. No API key or third-party package is required.

```powershell
git clone https://github.com/Zara-iqbal-01/StateManagement.git
cd StateManagement
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
python -m state_management demo --strategy relevance --top-k 3
```

The demo is deterministic and validates the retrieval/metric pipeline. It is not an LLM benchmark.
The project has no runtime dependencies, so no installation step is required.

## Core building blocks

- `MemoryStore`: SQLite-backed local persistence.
- `raw_trace`, `summary`, `structured_lesson`: comparable memory representations.
- `retrieve`: relevance or recency selection with a top-k limit.
- `aggregate`: completion, efficiency, cost, latency, transfer, retrieval-quality, stale-memory, and overhead metrics.
- `baseline_changes`: absolute and relative differences from the no-memory baseline.

## Connect an agent

After each agent task, construct an `AgentResult` with the task outcome, token counts, latency,
tool calls, retrieved IDs, and error flags. Pass all task results for one condition to `aggregate`.
For retrieval precision, provide one `(retrieved_count, relevant_count)` tuple per task after human
or rubric labeling. Run the same task set and budget across memory conditions, top-k values, and
selection strategies.

The project intentionally does not ship a model provider adapter. Keeping the adapter outside the
harness makes model, prompt, and tool budgets explicit experimental controls instead of hidden
variables.
