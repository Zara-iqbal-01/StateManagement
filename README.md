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

The core package does not depend on a model provider. Optional Python runners in `experiments`
call Gemini directly through Vertex AI with Application Default Credentials. This repository
runs independently of the Dexter checkout. The current pilot uses supplied spreadsheet data
and no agent tools; integrating memory into Dexter's full tool loop remains future work.

## Run the spreadsheet pilot

The private source spreadsheet and generated answers are not included. Obtain `dataset1.xlsx`
from the team and keep its `Review` sheet unchanged. Install the optional notebook dependencies:

```powershell
python -m pip install -r experiments/requirements.txt
$env:DATASET_PATH = "C:\path\to\dataset1.xlsx"
python -m jupyterlab
```

Open notebooks from this repository or its `experiments` directory. Run `00`, `01`, and `02`
first to check the harness, extract the twelve tasks, and prepare logging. Notebook `02` writes
a planning template, not evidence of settings used by the live runners. Edit it before a new
controlled study and verify each runner's prompts and settings.

For Vertex, install Google Cloud CLI, sign in with an account allowed to use your billing
project, and configure ADC. In PowerShell, `gcloud.cmd` avoids the script execution policy:

```powershell
gcloud.cmd auth application-default login
gcloud.cmd auth application-default set-quota-project YOUR_PROJECT_ID
$env:VERTEX_AI_PROJECT_ID = "YOUR_PROJECT_ID"
$env:VERTEX_AI_LOCATION = "global"
$env:VERTEX_MODEL = "gemini-3.5-flash-lite"
```

The recorded pilot used that model. Use a model available to your project and keep it fixed
across every condition. `GCLOUD_PATH` can point to the CLI if it is not on PATH.

Run `04_run_vertex_no_memory_baseline.ipynb`, then `05_run_structured_lessons.ipynb`,
`06_run_raw_traces.ipynb`, and `07_run_summaries.ipynb`. Notebook `03` is an optional Gemini
Developer API baseline using `GOOGLE_API_KEY`; it is separate from the Vertex comparison.
The four Vertex conditions make 72 paid generation requests in total. Notebook `08` adds up
to 48 paid judge requests. No key is required for Vertex; credentials remain in the local ADC
store. Notebook files contain no saved outputs or credentials.

Equivalent commands after creating the manifest, from the repository root:

```powershell
python experiments/run_vertex_no_memory_baseline.py experiments/runs/tasks.jsonl experiments/runs/vertex_results.jsonl
python experiments/run_vertex_structured_lessons.py experiments/runs/tasks.jsonl experiments/runs/structured_lesson_results.jsonl experiments/runs/structured_lessons.sqlite3
python experiments/run_vertex_memory_condition.py raw_trace experiments/runs/tasks.jsonl experiments/runs/raw_trace_results.jsonl experiments/runs/raw_traces.sqlite3
python experiments/run_vertex_memory_condition.py summary experiments/runs/tasks.jsonl experiments/runs/summary_results.jsonl experiments/runs/summaries.sqlite3
```

Runners skip saved run identifiers when restarted. Keep each condition's results and SQLite
store together. For a new independent repeat, archive the entire `experiments/runs` directory
outside the repository and rebuild the manifest in a fresh directory. Do not reuse a completed
memory store with empty results. The current runners fix repeat one, relevance selection and
one retrieved memory; the core library supports additional settings, but the pilot notebooks
do not expose a full sweep. Generated answers, labels and stores remain ignored by Git.

## Interpret the preliminary analysis

Notebook `08_score_and_analyze.ipynb` saves means and changes from baseline. One complete
repeat per condition does not support a standard deviation across repeats. Inspect saved
answers and judge reasons before making any quality claim.

Known limitations of the initial pilot:

* The conditions use different memory instructions. Temperature and output budgets were not
  explicitly fixed by the runners. This is a pipeline pilot, not a clean causal ablation.
* The same model generates answers and provisional labels. The initial judge omits the actual
  supplied data and retrieved memory from its prompt and has produced inconsistent labels.
  Completion, repeated error and stale memory labels require rubric correction and manual audit.
* `retrieval_relevant` checks episode membership. It is a proxy, not judged retrieval precision.
  Successful related tasks do not by themselves demonstrate that memory caused transfer.
* Lessons and summaries are generated from the model's own answer without verified corrective
  feedback. They may preserve earlier mistakes.
* `latency_ms` sums answer and memory-generation calls. Retrieval is measured separately;
  local persistence and all orchestration overhead are not included in an end to end timer.
* Memory-run token totals treat missing usage fields as zero. Check the provider usage metadata
  before reporting totals. The analysis also suppresses numeric deltas when a baseline is zero.
* The HDFC episode lacks a dated old and new fact pair, so it cannot establish resistance to
  stale memories. None of these runs exercises Dexter tools.

The report should distinguish measured token and request timing data from unvalidated quality
labels. Correct the evaluation protocol and repeat the runs before ranking memory mechanisms.
