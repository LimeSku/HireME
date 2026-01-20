# todo: reimplement the cli with the typer library
"""HireME CLI - Job and Resume Agents.
Provides command-line interfaces for job extraction and resume generation.
"""

# from pathlib import Path
from typing import Literal

import logfire
import typer

# from hireme.cli.commands.resume_agent_cli_typer import generate,
import hireme.cli.commands.resume_agent_cli as resume_cli
from hireme.cli.commands.job_agent_cli import run_agent

app = typer.Typer(name="hireme_cli", help="HireME CLI - Job and Resume Agents")
app.add_typer(resume_cli.app, name="resume")


@app.command("job")
def job_agent(
    job: str = typer.Argument(..., help="Job title or keywords to search for."),
    max_results_per_source: int = typer.Option(
        1, help="Maximum number of job results to fetch per source."
    ),
    location: str = typer.Option(..., help="Location to look for jobs in."),
    mode: Literal["testing", "scrapper"] = typer.Option(
        "scrapper",
        help="Mode of operation: 'testing' uses a sample job posting, 'scrapper' fetches from a URL.",
    ),
    export_path: str | None = typer.Option(
        None, help="Optional path to export extracted job data as JSON."
    ),
):
    """CLI for the Job Extraction Agent."""
    run_agent(
        job=job,
        max_results_per_source=max_results_per_source,
        location=location,
        mode=mode,
        export_path=export_path,
    )


def main() -> None:
    """CLI for the HireME application."""
    logfire.configure()
    logfire.instrument_pydantic_ai()
    app()


if __name__ == "__main__":
    """CLI for the HireME application."""
    main()
