"""CLI for the Resume Generation Agent.

Generates tailored resumes for job postings using directory-based context loading.
Supports both the new directory-based approach and legacy template-based approach.
"""

import json
from pathlib import Path
from typing import Annotated

import structlog
import typer
from rich.console import Console
from rich.panel import Panel

from hireme.agents.job_agent import JobDetails, extract_job
from hireme.config import cfg
from hireme.utils.models.resume_models import GenerationFailed, TailoredResume

logger = structlog.get_logger()

app = typer.Typer(name="resume_agent", help="Resume Generation Agent CLI")


@app.command("generate")
def generate(
    job_dir: Annotated[
        Path, typer.Option(help="Directory containing job posting files.")
    ] = cfg.job_offers_dir,
    profile_dir: Annotated[
        Path, typer.Option(help="Directory containing profile files.")
    ] = cfg.profile_dir,
    output_dir: Annotated[
        Path, typer.Option(help="Directory to save the generated resume files.")
    ] = Path("output/"),
    parse_job: bool = typer.Option(
        False, help="Parse the job posting to extract structured job details."
    ),
):
    """Generate a tailored resume for a job posting.

    Reads a job posting, extracts job details, and generates a tailored
    resume PDF using the user's profile from a directory of files.

    The profile directory should contain:
    - context.md: Main context note with detailed background
    - profile.yaml: Structured personal info (optional)
    - *.pdf: Resume PDFs or other documents
    - *.md/*.txt: Additional notes and descriptions
    """
    import asyncio

    asyncio.run(
        _generate_resume(
            job_dir=job_dir,
            profile_dir=profile_dir,
            output_dir=output_dir,
            parse_job=parse_job,
        )
    )


async def _generate_resume(
    job_dir: Path,
    profile_dir: Path,
    output_dir: Path,
    parse_job: bool = False,
):
    """Async implementation of resume generation."""

    from hireme.agents.resume_agent import (
        generate_resume,
        load_user_context_from_directory,
    )

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
        return

    if not profile_dir.exists():
        console.print(
            f"[yellow]Warning: Profile directory not found: {profile_dir}. "
            "Using default profile directory.[/yellow]"
        )
        profile_dir = cfg.profile_dir  # Accessing property to create directories
        if not any(profile_dir.rglob("*")):
            console.print(
                f"[yellow]Profile directory is empty: {profile_dir}."
                " Initializing with example files...[/yellow]"
            )
            init(profile_dir=profile_dir)  # populate with example files
        return
    # Load user context from directory
    console.print(Panel(f"Loading user context from: {profile_dir}", style="blue"))
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
) -> list[JobDetails]:
    """Parse job postings to extract structured job details.

    Reads raw job posting text files from the specified directory
    and extracts structured job details into JSON files.
    """
    logger.debug("Loading raw job files from", job_dir=job_dir)
    console.print(Panel("Extracting job details from posting...", style="blue"))
    job_results: list[JobDetails] = []
    for job_file in job_dir.glob("*.txt"):
        console.print(f"[blue]Processing job file: {job_file}[/blue]")
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
) -> list[JobDetails]:
    """Load already parsed job postings from JSON files.

    Reads processed job posting JSON files from the specified directory
    and loads structured job details.
    """
    job_results: list[JobDetails] = []
    console = Console()
    logger.debug("Loading processed job files from", job_dir=job_dir)
    for job_file in job_dir.glob("*.json"):
        console.print(f"[blue]Loading already parsed job file: {job_file}[/blue]")
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


@app.command("init")
def init(
    profile_dir: Annotated[
        Path | None, typer.Option(help="Directory to create the profile files in.")
    ] = None,
):
    """Initialize a new profile directory with example files."""
    from rich.console import Console
    from rich.panel import Panel

    console = Console()

    if profile_dir is None:
        profile_dir = cfg.profile_dir  # Accessing property to create directories

    if profile_dir.exists() and any(profile_dir.iterdir()):
        console.print(
            f"[yellow]Profile directory already exists: {profile_dir}[/yellow]"
        )
        console.print(
            "[yellow]Use --profile-dir to specify a different location.[/yellow]"
        )
        return

    profile_dir.mkdir(parents=True, exist_ok=True)

    # Create example context.md
    example_context = open(cfg.assets_dir / "samples" / "context.md", "r").read()

    (profile_dir / "context.md").write_text(example_context)

    console.print(Panel(f"Profile directory created: {profile_dir}", style="green"))
    console.print("[green]Created files:[/green]")
    console.print(f"  - {profile_dir / 'context.md'}")

    console.print("\n[yellow]Next steps:[/yellow]")
    console.print("1. Edit context.md with your real information")
    console.print("2. Edit profile.yaml with your contact details")
    console.print("3. Add any PDF resumes or additional documents")
    console.print("4. Run: hireme resume generate")
