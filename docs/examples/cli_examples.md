# CLI examples

## Extract the packaged sample

```bash
hireme job find "Python Developer" --location Paris --mode testing
```

The command runs the configured LLM, validates the structured `JobDetails`
output and stores the raw and processed offer in `.hireme/hireme.db`.

## Search live sources

```bash
hireme job find "Data Engineer" --location Lille --max-results-per-source 3
hireme db jobs list --processed
```

Partial source or extraction failures are reported in the final summary. The
command exits non-zero when no offer could be processed.

## Generate a grounded resume

```bash
hireme profile new default --example
hireme resume generate --job-id 1 --output-dir output
```

The result directory contains the RenderCV YAML, Typst source and expected PDF.
Candidate identity, organizations, roles, dates and numeric claims are checked
against the selected profile before rendering.
