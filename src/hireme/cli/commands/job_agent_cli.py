import asyncio
from pathlib import Path
from typing import Annotated, Literal

import structlog
import typer
from pydantic_ai.exceptions import AgentRunError
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from hireme.utils.providers import LLMConfigurationError

logger = structlog.get_logger(__name__)
console = Console()
app = typer.Typer(help="Find and extract job offers")


@app.command("find")
def job_agent(
    job: Annotated[str, typer.Argument(help="Job title or search keywords.")],
    location: Annotated[str, typer.Option(help="Location to search.")],
    max_results_per_source: Annotated[
        int,
        typer.Option(min=1, help="Maximum results fetched from each source."),
    ] = 1,
    mode: Annotated[
        Literal["testing", "scraper", "scrapper"],
        typer.Option(help="Use the sample posting or live job boards."),
    ] = "scraper",
    save_to_db: Annotated[
        bool, typer.Option("--db/--no-db", help="Save results to SQLite.")
    ] = True,
    export_dir: Annotated[
        Path | None, typer.Option(help="Also export raw and structured files.")
    ] = None,
) -> None:
    """Find job postings and extract their structured details."""
    if mode == "scrapper":
        console.print("[yellow]'scrapper' is deprecated; use 'scraper'.[/yellow]")
        mode = "scraper"
    try:
        successes, total = asyncio.run(
            _find_jobs(
                query=job,
                location=location,
                max_results_per_source=max_results_per_source,
                mode=mode,
                save_to_db=save_to_db,
                export_dir=export_dir,
            )
        )
    except LLMConfigurationError as error:
        raise typer.BadParameter(str(error)) from error
    if successes == 0:
        raise typer.Exit(code=1)
    console.print(
        Panel(f"Completed: {successes}/{total} jobs extracted", style="green")
    )


async def _find_jobs(
    query: str,
    location: str,
    max_results_per_source: int,
    mode: Literal["scraper", "testing"],
    save_to_db: bool,
    export_dir: Path | None,
) -> tuple[int, int]:
    from hireme.agents.job_agent import (
        SAMPLE_POSTING,
        ExtractionFailed,
        JobDetails,
        extract_job,
    )
    from hireme.scraper import JobSearchResult, get_job_pages_async, search_jobs_async

    console.print(Panel(f"Job Search - Mode: {mode}", style="bold blue"))
    if mode == "testing":
        search_results = [
            JobSearchResult(
                url="sample://posting",
                title="Senior Python Developer",
                company="FinTech Startup",
                location="Paris",
                source="manual",
            )
        ]
        contents = {"sample://posting": SAMPLE_POSTING}
    else:
        search_results = await search_jobs_async(
            query,
            location=location,
            max_results_per_source=max_results_per_source,
        )
        contents = await get_job_pages_async([result.url for result in search_results])

    postings = [
        (result, content)
        for result in search_results
        if (content := contents.get(result.url))
    ]
    if not postings:
        console.print("[red]No readable job postings found.[/red]")
        return 0, len(search_results)

    semaphore = asyncio.Semaphore(3)

    async def extract_one(
        result: JobSearchResult, content: str
    ) -> tuple[JobSearchResult, str, JobDetails | ExtractionFailed]:
        async with semaphore:
            try:
                extracted = await extract_job(content)
            except AgentRunError as error:
                extracted = ExtractionFailed(reason=str(error))
            return result, content, extracted

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        task = progress.add_task("Extracting job details", total=len(postings))
        extracted_jobs = []
        for future in asyncio.as_completed(
            [extract_one(result, content) for result, content in postings]
        ):
            extracted_jobs.append(await future)
            progress.advance(task)

    db = None
    if save_to_db:
        from hireme.db import get_db

        db = get_db()
    if export_dir is None and not save_to_db:
        from hireme.config import cfg

        export_dir = cfg.job_offers_dir

    successes = 0
    for search_result, content, extracted in extracted_jobs:
        if isinstance(extracted, ExtractionFailed):
            console.print(f"[red]✗ Extraction failed: {extracted.reason}[/red]")
            continue
        successes += 1
        console.print(
            f"[green]✓ Extracted: {extracted.title} @ {extracted.company.name}[/green]"
        )
        if db:
            from hireme.db import JobSource

            sources = {
                "indeed": JobSource.INDEED,
                "wttj": JobSource.WELCOME_TO_THE_JUNGLE,
                "manual": JobSource.MANUAL,
            }
            job_offer = db.add_job_offer(
                title=extracted.title,
                company_name=extracted.company.name,
                url=search_result.url if search_result.source != "manual" else None,
                source=sources.get(search_result.source, JobSource.OTHER),
                location=extracted.location,
                raw_text=content,
            )
            db.mark_job_processed(job_offer.id, extracted.model_dump(mode="json"))
            console.print(f"[dim]  → Saved to database (ID: {job_offer.id})[/dim]")

        if export_dir:
            from hireme.utils.common import (
                safe_filename_component,
                write_job_offer_to_json,
            )

            processed_dir = export_dir / "processed"
            raw_dir = export_dir / "raw"
            raw_dir.mkdir(parents=True, exist_ok=True)
            write_job_offer_to_json(
                search_result.url, extracted.model_dump(mode="json"), processed_dir
            )
            filename = "-".join(
                (
                    safe_filename_component(extracted.title),
                    safe_filename_component(extracted.company.name),
                )
            )
            (raw_dir / f"{filename}.txt").write_text(content, encoding="utf-8")

    logger.info("Job search completed", successes=successes, total=len(postings))
    return successes, len(postings)
