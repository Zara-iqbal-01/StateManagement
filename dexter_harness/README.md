# Dexter harness snapshot

This folder preserves the local Dexter source prepared during the memory study, including
the Vertex AI provider adapter. It runs independently of the original Desktop checkout.
The source is TypeScript because Dexter itself is written in TypeScript. The memory
experiment package and its live pilot runners remain Python in the parent repository.

The completed twelve task pilot called Vertex directly through the Python runners under
`../experiments`. It did not run Dexter's full tool loop. Adding this source snapshot does
not change that experimental claim, and the Python ablation store is not yet connected to
Dexter's agent loop. Dexter also has its own upstream memory implementation under
`src/memory`, which is distinct from the Python ablation conditions.

## Start the harness

Install Bun and Google Cloud CLI, then run these commands from this folder:

```powershell
bun install --frozen-lockfile
gcloud.cmd auth application-default login
gcloud.cmd auth application-default set-quota-project YOUR_PROJECT_ID
$env:VERTEX_AI_PROJECT_ID = "YOUR_PROJECT_ID"
$env:VERTEX_AI_LOCATION = "global"
bun run start
```

In the CLI, use `/model`, choose **Vertex AI**, then **Gemini 3.5 Flash-Lite**.
The internal model identifier is `vertex:gemini-3.5-flash-lite`. The selected model
must be available to your Google Cloud project. ADC supplies authentication; no Gemini
API key is needed for this provider. Other providers still use their usual API keys.

`bun install` runs the upstream Playwright browser installation hook. Financial data
and search tools need their corresponding optional credentials in `env.example`.
To configure them locally, copy `env.example` to `.env`, remove unused placeholder
entries, and fill only the providers you intend to use. Keep `.env` out of Git.

## Check the source

```powershell
bun run typecheck
bun test
```

The copied folder was checked with a frozen lockfile dependency installation, type
checking, six model tests, and Vertex adapter construction without a model request.
The original local checkout also passed type checking. Its Windows test run recorded
310 passing tests and seven shell runner failures because those tests require `/bin/sh`;
use a compatible Unix
environment for those tests. This snapshot does not fix those upstream failures.
No live Dexter model request is needed for type checking.

## Earlier Python dataset planner

`tools/dataset_research_planner.py` and `tools/dataset_agent.py` preserve the earlier
custom Python planning prototype. Install `openpyxl` from the parent experiment
requirements, then inspect a tool plan without a model request:

```powershell
python tools/dataset_agent.py "What does the Groww figure mean?" --dataset "C:\path\to\dataset1.xlsx" --dry-run
```

The optional live Python agent uses `OPENAI_API_KEY`, not Vertex. These scripts are
standalone prototypes and are not registered in the Dexter tool registry. The planner
uses evaluator metadata from the spreadsheet, including intended reading and figure
meaning. Do not expose it to the evaluated agent in a benchmark that withholds those
fields. It was not part of the recorded Vertex memory pilot.

## Source and attribution

Upstream project: https://github.com/virattt/dexter

Base commit: `534f6be455523c5926eba72bdaf4f914555be5c9`.

This is a source snapshot of that checkout with local Vertex changes in `package.json`,
`bun.lock`, `env.example`, `src/model/llm.ts`, `src/providers.ts`, and `src/utils/model.ts`.
The two Python prototypes are local additions. Their dataset default is made portable
in this snapshot. `README.upstream.md` preserves the upstream documentation and its MIT
license statement. Upstream authors retain credit for Dexter; this folder is not a
claim that the team authored its agent framework.

Installed dependencies, nested Git history, credentials, local sessions, and generated
experiment results are intentionally excluded. The canonical installation uses Bun's
lockfile; the original npm lockfile is not included.
