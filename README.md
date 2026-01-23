# HireMe

An AI-powered job application assistant that scrapes job postings, extracts structured data, and generates tailored resumes.

## Features

- **Job Scraping**: Searches multiple job boards (Indeed, etc.) and extracts structured job details
- **AI Extraction**: Uses LLMs to parse job postings into structured data (skills, requirements, salary, etc.)
- **Resume Generation**: Generates tailored resumes based on your profile and job requirements using RenderCV

**See [output examples](./docs/examples/cli_examples.md) !**
## Installation

```bash
# Install with uv
uv sync

# Or using pip
pip install -e .
```

## Configuration

Create a `.hireme` directory with your profile (done automatically at first run):

```
.hireme/
├── job_offers/
│   ├── processed/
│   │   └── results.json    # Extracted job data
│   └── raw/
│       └── company_job.txt # Raw job postings
└── profile/
    └── context.md          # Your background and experience
```

Set up your environment variables in `.env`:

```bash
OLLAMA_BASE_URL=http://localhost:11434  # Optional, defaults to localhost
OLLAMA_FALLBACK_MODEL="qwen2.5:7b-instruct"
```

## Usage

### CLI

```bash
# Search and extract job postings
hireme job "Python Developer" --location "Paris" --max-results-per-source 5

# Generate a tailored resume
hireme resume generate --job-dir .hireme/job_offers/raw --output-dir output/
```

### Web UI
**WIP for the moment**

<!-- make run-web
# or
uv run streamlit run src/hireme/web_ui.py -->


## Development

```bash
make dev        # Install dev dependencies
make lint       # Run linter
make format     # Format code
make test       # Run tests
make clean      # Clean cache files
```

## Requirements

- Python 3.13+
- Ollama (for local LLM inference) or OpenAI api key.

## Roadmap
- ADD TESTS!!!
- Improve job extraction flow and exports
- Enhance configuration and make it more robust
- Add more job sources