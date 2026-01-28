"""CLI for the Resume Generation Agent.

Generates tailored resumes for job postings using directory-based context loading.
Supports both database-based and file-based job loading.
"""

import json
from pathlib import Path
from typing import Annotated

import structlog
import typer
from rich.console import Console
from rich.panel import Panel

# Lazy imports - moved inside functions to speed up CLI startup
# from hireme.agents.job_agent import JobDetails, extract_job
# from hireme.config import cfg
# from hireme.db import get_db
# from hireme.utils.models.resume_models import GenerationFailed, TailoredResume
from hireme.cli.commands.profile.common import (
    complete_profile_names,
    find_profile_dir_by_name,
)

logger = structlog.get_logger()

app = typer.Typer(name="resume_agent", help="Resume Generation Agent CLI")


@app.command("generate")
def generate(
    job_id: Annotated[
        int | None,
        typer.Option(
            "--job-id", "-j", help="Job ID from database to generate resume for."
        ),
    ] = None,
    all_jobs: Annotated[
        bool,
        typer.Option(
            "--all", "-a", help="Generate resumes for all unprocessed jobs in database."
        ),
    ] = False,
    job_dir: Annotated[
        Path | None,
        typer.Option(help="[Legacy] Directory containing job posting files."),
    ] = None,
    profile_name: Annotated[
        str | None,
        typer.Option(
            help="Name of the profile to use.", autocompletion=complete_profile_names
        ),
    ] = None,
    output_dir: Annotated[
        Path, typer.Option(help="Directory to save the generated resume files.")
    ] = Path("output/"),
    parse_job: bool = typer.Option(
        False, help="[Legacy] Parse raw job posting to extract structured job details."
    ),
):
    """Generate a tailored resume for a job posting.

    Use --job-id to generate from a specific job in the database,
    or --all to generate for all processed jobs without resumes.

    Legacy: Use --job-dir to read from the file-based job_offers directory.
    """
    import asyncio

    from hireme.cli.commands.profile.common import select_profile

    console = Console()
    if profile_name is None:
        profile_name = select_profile(console)

    profile_dir = find_profile_dir_by_name(profile_name) if profile_name else None
    if profile_dir is None:
        logger.error("Profile not found", profile_name=profile_name)
        raise typer.Exit(code=1)

    # Determine mode: database or file-based
    if job_id is not None or all_jobs:
        # Database mode
        asyncio.run(
            _generate_resume_from_db(
                job_id=job_id,
                all_jobs=all_jobs,
                profile_dir=profile_dir,
                profile_name=profile_name or "default",
                output_dir=output_dir,
            )
        )
    else:
        # Legacy file-based mode
        if job_dir is None:
            from hireme.config import cfg

            job_dir = cfg.job_offers_dir
        assert job_dir is not None  # Guaranteed non-None at this point
        asyncio.run(
            _generate_resume_from_files(
                job_dir=job_dir,
                profile_dir=profile_dir,
                output_dir=output_dir,
                parse_job=parse_job,
            )
        )


async def _generate_resume_from_db(
    job_id: int | None,
    all_jobs: bool,
    profile_dir: Path,
    profile_name: str,
    output_dir: Path,
):
    """Generate resumes from jobs stored in database."""
    from hireme.agents.job_agent import JobDetails
    from hireme.agents.resume_agent import generate_resume
    from hireme.db import get_db
    from hireme.utils.common import load_user_context_from_directory
    from hireme.utils.models.resume_models import GenerationFailed

    console = Console()
    db = get_db()

    # Load user context
    if not any(profile_dir.rglob("*")):
        console.print(
            f"[yellow]Profile directory is empty: {profile_dir}."
            " Please populate it with your profile files.[/yellow]"
        )
        raise typer.Exit(code=1)

    console.print(
        Panel(f"Loading user context from {profile_dir.name} profile", style="blue")
    )
    user_context = load_user_context_from_directory(profile_dir)

    # Get jobs from database
    jobs_to_process: list[tuple[int, JobDetails]] = []

    if job_id is not None:
        # Single job by ID
        job = db.get_job_by_id(job_id)
        if job is None:
            console.print(f"[red]Job with ID {job_id} not found.[/red]")
            raise typer.Exit(code=1)
        if not job.is_processed or not job.processed_data:
            console.print(f"[red]Job {job_id} has not been processed yet.[/red]")
            raise typer.Exit(code=1)

        job_details = JobDetails.model_validate(job.processed_data)
        jobs_to_process.append((job.id, job_details))

    elif all_jobs:
        # All processed jobs
        all_db_jobs = db.get_all_jobs(only_processed=True)
        for job in all_db_jobs:
            if job.processed_data:
                job_details = JobDetails.model_validate(job.processed_data)
                jobs_to_process.append((job.id, job_details))

        if not jobs_to_process:
            console.print("[yellow]No processed jobs found in database.[/yellow]")
            raise typer.Exit(code=1)

    console.print(
        Panel(f"Generating resumes for {len(jobs_to_process)} job(s)...", style="blue")
    )

    output_dir.mkdir(parents=True, exist_ok=True)

    for db_job_id, job_details in jobs_to_process:
        try:
            resume_output_dir = (
                output_dir / f"job_{db_job_id}_{job_details.company.name}"
            )
            resume_output_dir.mkdir(parents=True, exist_ok=True)

            console.print(
                f"[blue]Generating resume for: {job_details.title} @ {job_details.company.name}[/blue]"
            )

            tailored_resume, pdf_path = await generate_resume(
                candidate_profile=user_context,
                structured_job=job_details,
                output_dir=resume_output_dir,
            )

            # Check if generation failed
            if isinstance(tailored_resume, GenerationFailed):
                console.print(
                    f"[red]Resume generation failed: {tailored_resume.reason}[/red]"
                )
                continue

            # Save to database
            db.add_generated_resume(
                job_offer_id=db_job_id,
                profile_name=profile_name,
                resume_data=tailored_resume.model_dump(),
                pdf_path=str(pdf_path),
                yaml_path=str(
                    resume_output_dir
                    / f"{tailored_resume.name.replace(' ', '_').lower()}_cv.yaml"
                ),
            )

            console.print("[green]✓ Resume generated and saved to database![/green]")
            console.print(f"[blue]PDF saved to: {pdf_path}[/blue]")

        except Exception as e:
            console.print(
                f"[red]Error generating resume for job {db_job_id}: {e}[/red]"
            )
            logger.error("Error generating PDF", error=e, job_id=db_job_id)


async def _generate_resume_from_files(
    job_dir: Path,
    profile_dir: Path,
    output_dir: Path,
    parse_job: bool = False,
):
    """Async implementation of resume generation."""
    from hireme.agents.job_agent import JobDetails
    from hireme.agents.resume_agent import generate_resume
    from hireme.config import cfg
    from hireme.utils.common import load_user_context_from_directory
    from hireme.utils.models.resume_models import GenerationFailed, TailoredResume

    console = Console()
    # Determine job file path
    if not job_dir.exists():
        console.print(
            f"[yellow]Warning: Job directory not found: {job_dir}. "
            "Using default job offers directory.[/yellow]"
        )
        job_dir = cfg.job_offers_dir  # Accessing property to create directories

    if not any(job_dir.rglob("*.txt")) and not any(job_dir.rglob("*.json")):
        console.print(f"[red]Error: No job posting files found in: {job_dir}[/red]")
        raise typer.Exit(code=1)

    if not any(profile_dir.rglob("*")):
        console.print(
            f"[yellow]Profile directory is empty: {profile_dir}."
            " Please populate it with your profile files.[/yellow]"
        )
        raise typer.Exit(code=1)

    # Load user context from directory
    console.print(
        Panel(f"Loading user context from {profile_dir.name} profile", style="blue")
    )
    user_context = load_user_context_from_directory(profile_dir)

    # Extract job details
    job_results: list[JobDetails] = []
    if parse_job:
        job_dir = job_dir / "raw"
        logger.debug("Loading raw job files from", job_dir=job_dir)
        job_results = await process_raw_jobs(console, job_dir)
    else:
        job_dir = job_dir / "processed"
        logger.debug("Loading processed job files from", job_dir=job_dir)
        job_results = process_parsed_jobs(job_dir)

    # check/create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate resume
    console.print(
        Panel(f"Generating {len(job_results)} tailored resumes...", style="blue")
    )

    tailored_resumes: list[TailoredResume | GenerationFailed] = []
    for i, job_result in enumerate(job_results):
        try:
            resume_output_dir = output_dir / f"job_{i + 1}_{job_result.company.name}"
            resume_output_dir.mkdir(parents=True, exist_ok=True)

            tailored_resume, pdf_path = await generate_resume(
                candidate_profile=user_context,
                structured_job=job_result,
                output_dir=resume_output_dir,
            )
            tailored_resumes.append(tailored_resume)
            console.print("[green]✓ Resume generated successfully![/green]")
            console.print(f"[blue]PDF saved to: {pdf_path}[/blue]")

        except Exception as e:
            console.print(f"[red]Error generating PDF: {e}[/red]")
            logger.error("Error generating PDF", error=e)


async def process_raw_jobs(
    console: Console,
    job_dir: Annotated[
        Path, typer.Option(help="Directory containing job posting files.")
    ],
) -> list:
    """Parse job postings to extract structured job details.

    Reads raw job posting text files from the specified directory
    and extracts structured job details into JSON files.
    """
    from hireme.agents.job_agent import JobDetails, extract_job

    logger.debug("Loading raw job files from", job_dir=job_dir)
    # console.print(Panel("Extracting job details from posting...", style="blue"))
    job_results: list[JobDetails] = []
    for job_file in job_dir.glob("*.txt"):
        # console.print(f"[blue]Processing job file: {job_file}[/blue]")
        job_text = job_file.read_text()
        job_result = await extract_job(job_text)
        if not isinstance(job_result, JobDetails):
            console.print(f"[red]Job extraction failed: {job_result.reason}[/red]")
            continue
        job_results.append(job_result)

    return job_results


def process_parsed_jobs(
    job_dir: Annotated[
        Path, typer.Option(help="Directory containing job posting files.")
    ],
) -> list:
    """Load already parsed job postings from JSON files.

    Reads processed job posting JSON files from the specified directory
    and loads structured job details.
    """
    from hireme.agents.job_agent import JobDetails

    job_results: list[JobDetails] = []
    console = Console()
    logger.debug("Loading processed job files from", job_dir=job_dir)
    for job_file in job_dir.glob("*.json"):
        # console.print(f"[blue]Loading already parsed job file: {job_file}[/blue]")
        job_json_list = None
        with job_file.open() as f:
            job_json_list = json.load(f)
        if not isinstance(job_json_list, dict):
            console.print(f"[red]TODO: Implement list parsing: {job_file}[/red]")
            continue
        job_text = job_json_list
        job_details = JobDetails.model_validate(job_text.get("data", "{}"))
        job_results.append(job_details)
        console.print(
            f"[green]Loaded job: {job_details.title} at {job_details.company.name}[/green]"
        )
    return job_results
