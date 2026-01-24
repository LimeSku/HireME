from pathlib import Path
from typing import Annotated, Literal

import structlog
import typer
from rich.console import Console

from hireme.agents.job_agent import main
from hireme.config import cfg
from hireme.db import JobSource, get_db

logger = structlog.get_logger()
console = Console()

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
    save_to_db: Annotated[
        bool, typer.Option("--db/--no-db", help="Save results to database.")
    ] = True,
    export_dir: Annotated[
        Path | None, typer.Option(help="Directory to save the jobs data (legacy).")
    ] = None,
):
    """Find and extract job postings.

    Searches for jobs matching the query and location, extracts structured
    information, and saves to database (and optionally to files).
    """
    import asyncio

    # Use export_dir if specified, otherwise only save to DB
    if export_dir is None and not save_to_db:
        export_dir = cfg.job_offers_dir

    asyncio.run(
        _find_jobs(
            query=job,
            mode=mode,
            export_dir=export_dir,
            location=location,
            max_results_per_source=max_results_per_source,
            save_to_db=save_to_db,
        )
    )


async def _find_jobs(
    query: str,
    location: str,
    max_results_per_source: int,
    mode: Literal["scrapper", "testing"],
    save_to_db: bool,
    export_dir: Path | None,
):
    """Find jobs and optionally save to database."""
    from rich.panel import Panel
    from rich.progress import track

    from hireme.agents.job_agent import (
        SAMPLE_POSTING,
        JobDetails,
        extract_job,
        get_job_page,
        get_job_urls,
    )

    console.print(Panel(f"Job Search - Mode: {mode}", style="bold blue"))

    job_offers: list[dict[str, str]] = []

    if mode == "testing":
        console.print(Panel("Using sample job posting for extraction.", style="yellow"))
        job_offers = [{"url": "sample_url", "content": SAMPLE_POSTING}]
    else:
        console.print(Panel("Fetching live job postings...", style="yellow"))
        job_urls = get_job_urls(
            query, location=location, max_results_per_source=max_results_per_source
        )
        console.print(f"Found {len(job_urls)} job URLs to process.")

        for i, url in track(
            enumerate(job_urls),
            total=len(job_urls),
            description="Fetching job postings...",
        ):
            job_posting = get_job_page(url)
            if job_posting:
                job_offers.append({"url": url, "content": job_posting})

    # Process and extract job details
    db = get_db() if save_to_db else None
    results_count = 0

    for posting in track(job_offers, description="Extracting job details..."):
        url = posting.get("url", "")
        content = posting["content"]

        result = await extract_job(content)

        if isinstance(result, JobDetails):
            results_count += 1
            console.print(
                f"[green]✓ Extracted: {result.title} @ {result.company.name}[/green]"
            )

            # Save to database
            if db:
                job = db.add_job_offer(
                    title=result.title,
                    company_name=result.company.name,
                    url=url if url != "sample_url" else None,
                    source=JobSource.INDEED,  # TODO: detect source from URL
                    location=result.location,
                    raw_text=content,
                )
                db.mark_job_processed(job.id, result.model_dump())
                console.print(f"[dim]  → Saved to database (ID: {job.id})[/dim]")

            # Legacy: save to files
            if export_dir:
                from hireme.utils.common import write_job_offer_to_json

                processed_dir = export_dir / "processed"
                raw_dir = export_dir / "raw"
                processed_dir.mkdir(parents=True, exist_ok=True)
                raw_dir.mkdir(parents=True, exist_ok=True)

                write_job_offer_to_json(url, result.model_dump(), processed_dir)
                raw_filename = f"job_{result.title}-{result.company.name}.txt"
                (raw_dir / raw_filename).write_text(content)
        else:
            console.print(f"[red]✗ Extraction failed: {result.reason}[/red]")

    console.print(
        Panel(
            f"Completed: {results_count}/{len(job_offers)} jobs extracted",
            style="green" if results_count > 0 else "red",
        )
    )
