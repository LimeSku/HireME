# HireME

HireME is a CLI that finds job postings, extracts typed job data with an LLM,
and produces grounded, tailored PDF resumes with RenderCV.

## Install

Python 3.13+, [`uv`](https://docs.astral.sh/uv/) and Chromium are required.

```bash
make install
cp .env.example .env
```

`make install` installs the locked dependencies and the Playwright Chromium
browser. For development, use `make dev`.

## Configure a model

AI commands require an explicit provider and model. HireME has no implicit
cloud provider or model.

```dotenv
# Local Ollama
HIREME_LLM_PROVIDER=ollama
HIREME_LLM_MODEL=qwen2.5:7b-instruct
OLLAMA_BASE_URL=http://localhost:11434/v1
```

For Mistral, set `HIREME_LLM_PROVIDER=mistral`, `HIREME_LLM_MODEL` and
`MISTRAL_API_KEY`. For OpenAI, use `HIREME_LLM_PROVIDER=openai`,
`HIREME_LLM_MODEL` and `OPENAI_API_KEY`.

Logfire tracing is disabled by default. Enable it with
`HIREME_LOGFIRE_ENABLED=true` and `LOGFIRE_TOKEN`. Prompt and candidate content
is excluded unless `HIREME_LOGFIRE_INCLUDE_CONTENT=true`; candidate profiles
contain personal data, so enable content tracing only with explicit consent.

## Use

Create and edit a profile:

```bash
hireme profile new default --example
hireme profile show
```

Find live offers, extract them and save them to SQLite:

```bash
hireme job find "Python Developer" --location "Paris" --max-results-per-source 5
```

Exercise extraction with the packaged sample instead of live job boards:

```bash
hireme job find "Python Developer" --location "Paris" --mode testing
```

Generate one resume from a processed database job:

```bash
hireme resume generate --job-id 1 --output-dir output
```

Legacy file import remains available by passing the job-offers root:

```bash
hireme resume generate --job-dir .hireme/job_offers --output-dir output
```

Database inspection commands are available under `hireme db --help`.

## Runtime data

Runtime state lives under `HIREME_HOME` (default: `.hireme` in the current
working directory):

```text
.hireme/
├── hireme.db
├── job_offers/{raw,processed}/
└── profiles/<name>/{profile.yaml,context.md,...}
```

Packaged prompts and RenderCV templates do not depend on the working directory.

## Development

```bash
make check       # formatting, lint, types and tests
make format      # apply Ruff formatting
make test        # pytest only
```
