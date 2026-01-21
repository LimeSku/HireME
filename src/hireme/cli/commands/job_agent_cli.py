from pathlib import Path
from typing import Annotated, Literal

import typer

from hireme.agents.job_agent import main
from hireme.config import cfg

app = typer.Typer(name="hireme_cli", help="Job offers agent CLI ")


@app.command("find")
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
    # export_path: str | None = typer.Option(
    #     None, help="Optional path to export extracted job data as JSON."
    # ),
    export_dir: Annotated[
        Path, typer.Option(help="Directory to save the jobs data.")
    ] = Path(cfg.job_offers_dir),
):
    # def run_agent(
    #     job: str,
    #     max_results_per_source: int,
    #     location: str,
    #     mode: Literal["testing", "scrapper"],
    #     export_dir: Path | None,
    # ):
    """CLI for the Job Extraction Agent."""
    import asyncio

    asyncio.run(
        main(
            query=job,
            mode=mode,
            export_dir=export_dir,
            location=location,
            max_results_per_source=max_results_per_source,
        )
    )
