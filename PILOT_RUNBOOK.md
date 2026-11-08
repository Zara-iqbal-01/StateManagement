# Dexter Memory Pilot Runbook

This is the concrete, one-day plan for producing **real preliminary metrics**
for the midterm report. It deliberately uses a small, controlled subset of
`dataset1.xlsx`; do not claim that it is the full 100-question evaluation.

## What to test on

Use the `Review` sheet in `C:\Users\MK\Downloads\dataset1.xlsx`. Each row
already supplies a natural-language question and the data given to the model.
Use the data in that row as the only task context: do **not** let Dexter browse
the web for this pilot. That makes the correct reading and the expected answer
auditable from the spreadsheet.

This is the original planning runbook. The implemented pilot uses direct Python Vertex
requests, with no Dexter tools. Use the README for current setup and known limitations.
The listed row numbers are benchmark Item identifiers, so the physical Excel row is one
greater because of the header. Run artifacts now live in `experiments/runs`.

Run these 12 rows, in this order. They form four three-task episodes. In each
episode, the first task creates an experience; the second asks a close variant
and tests reuse; the third tests whether Dexter follows a lesson instead of
blindly copying the previous answer.

| Episode | Rows | What it tests | Expected lesson to retain |
| --- | --- | --- | --- |
| Plan / entity ambiguity | 5, 49, 76 | Same Groww question, including an ambiguous platform-versus-fund wording | Keep `Groww (app)` distinct from `Groww Largecap Fund`; label plan and expense ratio. |
| Metric-label transfer | 29, 33, 94 | Same Motilal Oswal task expressed three ways | Distinguish total return from CAGR; preserve the supplied metric label and riskometer requirement. |
| Reference / calculation reuse | 83, 84, 16 | Nippon India task moves from explicit Direct Growth to ambiguous shorthand, then a fully specified task | Do not silently assume Direct plan for the ambiguous wording; ask or flag the assumption. |
| Stale or conflicting memory | 17, 98, 31 | Same HDFC Flexi Cap facts with a time-sensitive `today` wording | Prefer the supplied row data and label it as the data snapshot; never invent a live NAV. |

Why these are the right first tests:

- They are real benchmark rows, not prompts invented after seeing the results.
- They cover the error modes the spreadsheet is designed to score: wrong
  entity, wrong plan, wrong metric label, and stale/live-data confusion.
- They contain repeated and paraphrased questions, so retrieval can plausibly
  help or hurt.

Do **not** use rows 21/26/39/54/100 (`HDFC` versus `HDFC Bank`) in the first
pilot unless you have a strict answer rubric. They require an investment
recommendation, which makes pass/fail scoring subjective. Add them later as a
separate recommendation category.

## Conditions to run

The full study has four memory modes. For a one-day preliminary report, use
the following priority order:

1. `none`: No persistent memory. This is the required baseline.
2. `structured_lesson`: Store one concise record after each task with context,
   observed failure/correct behavior, corrective action, and validity rule.
3. `raw_trace`: Store the previous task's full prompt, tool trace, and answer.
4. `summary`: Store a short post-task summary.

Run `none` and `structured_lesson` first. If both work, run `raw_trace` and
`summary`. Do not report a missing condition as if it ran.

Use relevance retrieval with `top_k=1` for the first complete pass. Then, only
if time remains, repeat the structured-lesson condition with `top_k=3` and
with recency selection. Keep all of these fixed in every comparable run:

- Gemini model name and API account
- system prompt and task prompt template
- input data from the spreadsheet row
- model temperature (use `0` if supported)
- Dexter tools and maximum iterations
- timeout and token budget

## Step 0: check the harness (10 minutes)

From the `StateManagement` directory:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
python -m state_management demo --strategy relevance --top-k 1
```

The unit-test command should pass before any Gemini call. The deterministic
demo proves that memory storage, retrieval, and metric aggregation work; it is
not an agent-performance result.

## Step 1: make the task manifest (20 minutes)

Create `runs/tasks.jsonl`, one JSON object per row. Each record must contain:

```json
{
  "task_id": "groww-01",
  "source_row": 5,
  "episode": "plan_entity",
  "turn": 1,
  "question": "<copy column B exactly>",
  "provided_data": "<copy column D exactly>",
  "intended_reading": "<copy column C exactly>",
  "figure_meaning": "<copy column E exactly>",
  "success_rule": "Answer the intended question; label every number according to column E; flag or ask when the intended reading is under-specified."
}
```

Do not put column F (the existing model answer) into Dexter's prompt. Reserve
it for later qualitative comparison only.

## Step 2: create a run record for every Dexter call (30 minutes)

For each task and condition, append one row to `runs/results.jsonl`. Save the
raw answer in a separate text file and put its path in the record. Required
fields:

```json
{
  "run_id": "structured_lesson-relevance-k1-groww-01-r1",
  "condition": "structured_lesson",
  "selection_strategy": "relevance",
  "top_k": 1,
  "task_id": "groww-01",
  "repeat": 1,
  "completed": true,
  "tool_calls": 0,
  "input_tokens": 0,
  "output_tokens": 0,
  "latency_ms": 0,
  "retrieval_overhead_ms": 0,
  "retrieved_memory_ids": [],
  "retrieval_relevant": null,
  "repeated_error": false,
  "transfer_success": null,
  "stale_memory_error": false,
  "answer_path": "runs/answers/...txt"
}
```

Replace the zero placeholders with the actual values observed from Dexter or
the Gemini response. If a metric is unavailable, record `null`, not `0`.

## Step 3: run the baseline (45–60 minutes)

For `none`, clear/disable persistent memory before every task. Run the 12
tasks in the listed episode order. Save every answer and run record.

Score each output immediately against the row's `intended_reading` and
`figure_meaning`:

- `completed=true` only when it answers the intended reading and labels values
  correctly.
- `repeated_error=false` for all baseline tasks because no old experience was
  available. Use this field only after memory exists.
- Mark ambiguous questions as successful if Dexter explicitly flags the
  ambiguity or asks for clarification rather than silently choosing a plan.

## Step 4: run structured lessons (60–90 minutes)

Run the same 12 tasks in the same order. After each answer, create and store a
lesson such as:

```text
Task context: User asks about Groww and large-cap investing.
Failure/correct behavior: The platform and the mutual fund are different entities.
Corrective action: State which one is being discussed; label Direct/Regular plan.
Validity: Apply only when the prompt or data contains both platform and scheme terms.
```

Retrieve only before tasks 2 and 3 of each episode. Record the IDs retrieved,
retrieval time, whether the retrieved lesson is relevant, and whether Dexter
avoided the earlier failure.

## Step 5: optional raw and summary runs (60–90 minutes)

Repeat Step 4 using raw traces, then summaries. Do this only after baseline
and structured lessons are complete. This produces a defensible partial table
even if the day ends early.

## Step 6: analyze (45 minutes)

Aggregate separately for each condition. Report actual means across the 12
tasks (and standard deviations only if each condition has at least two full
repeats):

- task completion rate
- tool calls per task
- input, output, and total tokens per task
- end-to-end latency in seconds
- repeated-error frequency for turns 2–3 of each episode
- retrieval precision: relevant retrieved memories / all retrieved memories
- knowledge-transfer success for turns 2–3
- stale-memory error rate for the HDFC episode
- retrieval overhead in milliseconds

For each memory condition, calculate absolute difference from `none`:

```text
absolute change = condition mean - no-memory mean
relative change (%) = 100 * absolute change / no-memory mean
```

For completion and error rates, state the numerator and denominator alongside
the percentage, for example `9/12 (75.0%)`. Do not calculate a relative change
when the baseline is zero; say `not defined`.

## Step 7: write the midterm result (30 minutes)

Use this honest framing:

> We ran a preliminary pipeline pilot on 12 benchmark-derived mutual-fund
> tasks organized into four short repeated/transfer episodes. All conditions
> used the same Gemini model and input data, with tools disabled. Memory
> instructions differed between conditions, and generation settings were not
> explicitly fixed. The pilot is intended to validate the memory-evaluation
> pipeline and identify failure modes; it is not a final large-scale benchmark.

Only fill in numbers produced in the saved Vertex condition files under
`experiments/runs`, not the separate Developer API `results.jsonl`. If raw trace and summary
conditions have not run, say they are scheduled for the expanded evaluation.

## Definition of done today

- Unit tests pass.
- Baseline and structured-lesson runs exist for all 12 tasks.
- Every result has a saved answer, timing, token counts if available, and a
  human success label.
- A single table compares baseline and structured lessons.
- The report explicitly calls the analysis preliminary and lists the small
  sample as a limitation.
