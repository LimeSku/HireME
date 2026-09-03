"""Resume generation commands."""

import asyncio
import json
from pathlib import Path
from typing import Annotated

import structlog
import typer
from pydantic_ai.exceptions import AgentRunError
from rich.console import Console
from rich.panel import Panel

from hireme.cli.commands.profile.common import (
    complete_profile_names,
    find_profile_dir_by_name,
    select_profile,
)
from hireme.config import cfg
from hireme.utils.providers import LLMConfigurationError

logger = structlog.get_logger(__name__)
console = Console()
app = typer.Typer(help="Generate grounded, tailored resumes")


@app.command("generate")
def generate(
    job_id: Annotated[
        int | None,
        typer.Option("--job-id", "-j", help="Processed job ID from SQLite."),
    ] = None,
    all_jobs: Annotated[
        bool,
        typer.Option("--all", "-a", help="Process jobs without a resume."),
    ] = False,
    job_dir: Annotated[
        Path | None,
        typer.Option(help="Legacy job-offers directory."),
    ] = None,
    profile_name: Annotated[
        str | None,
        typer.Option(help="Profile name.", autocompletion=complete_profile_names),
    ] = None,
    output_dir: Annotated[
        Path, typer.Option(help="Destination for generated files.")
    ] = Path("output"),
    parse_job: Annotated[
        bool,
        typer.Option(help="Parse raw legacy job files before generation."),
    ] = False,
) -> None:
    """Generate resumes from SQLite or legacy job files."""
    if profile_name is None and cfg.default_profile_dir.is_dir():
        profile_dir = cfg.default_profile_dir
        profile_name = profile_dir.name
    else:
        profile_name = profile_name or select_profile(console)
        profile_dir = find_profile_dir_by_name(profile_name)
    if profile_dir is None:
        raise typer.BadParameter(f"Profile not found: {profile_name}")

    try:
        if job_id is not None or all_jobs:
            asyncio.run(
                _generate_resume_from_db(
                    job_id,
                    all_jobs,
                    profile_dir,
                    profile_name,
                    output_dir,
                )
            )
        else:
            asyncio.run(
                _generate_resume_from_files(
                    job_dir or cfg.job_offers_dir,
                    profile_dir,
                    output_dir,
                    parse_job,
                )
            )
    except (FileNotFoundError, LLMConfigurationError, ValueError) as error:
        raise typer.BadParameter(str(error)) from error
    except RuntimeError as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error


async def _generate_resume_from_db(
    job_id: int | None,
    all_jobs: bool,
    profile_dir: Path,
    profile_name: str,
    output_dir: Path,
) -> None:
    from hireme.agents.job_agent import JobDetails
    from hireme.agents.resume_agent import generate_resume
    from hireme.db import get_db
    from hireme.utils.common import (
        load_user_context_from_directory,
        safe_filename_component,
    )

    db = get_db()
    user_context = load_user_context_from_directory(profile_dir)
    jobs_to_process = []
    if job_id is not None:
        job = db.get_job_by_id(job_id)
        if job is None:
            raise ValueError(f"Job {job_id} not found.")
        if not job.is_processed or not job.processed_data:
            raise ValueError(f"Job {job_id} has not been processed.")
        jobs_to_process.append((job.id, JobDetails.model_validate(job.processed_data)))
    elif all_jobs:
        for job in db.get_all_jobs(only_processed=True):
            already_generated = any(
                resume.profile_name == profile_name for resume in job.resumes
            )
            if job.processed_data and not already_generated:
                jobs_to_process.append(
                    (job.id, JobDetails.model_validate(job.processed_data))
                )
    if not jobs_to_process:
        raise ValueError("No processed jobs without a resume were found.")

    output_dir.mkdir(parents=True, exist_ok=True)
    successes = 0
    for database_job_id, job_details in jobs_to_process:
        destination = output_dir / (
            f"job_{database_job_id}_{safe_filename_component(job_details.company.name)}"
        )
        try:
            result = await generate_resume(user_context, job_details, destination)
        except (AgentRunError, OSError, RuntimeError) as error:
            console.print(
                f"[red]Resume generation failed for job {database_job_id}: {error}[/red]"
            )
            continue

        db.add_generated_resume(
            job_offer_id=database_job_id,
            profile_name=profile_name,
            resume_data=result.resume.model_dump(mode="json"),
            pdf_path=str(result.pdf_path),
            yaml_path=str(result.yaml_path),
            model_used=result.model_used,
            generation_time_seconds=result.duration_seconds,
            tokens_used=result.tokens_used,
        )
        successes += 1
        console.print(f"[green]✓ Resume generated: {result.pdf_path}[/green]")

    if successes == 0:
        raise RuntimeError("All resume generations failed.")
    console.print(Panel(f"Generated {successes}/{len(jobs_to_process)} resumes"))


async def _generate_resume_from_files(
    job_dir: Path,
    profile_dir: Path,
    output_dir: Path,
    parse_job: bool = False,
) -> None:
    from hireme.agents.resume_agent import generate_resume
    from hireme.utils.common import (
        load_user_context_from_directory,
        safe_filename_component,
    )

    kind = "raw" if parse_job else "processed"
    source_dir = job_dir if job_dir.name == kind else job_dir / kind
    if not source_dir.is_dir():
        raise FileNotFoundError(f"Job directory not found: {source_dir}")

    jobs = (
        await process_raw_jobs(console, source_dir)
        if parse_job
        else process_parsed_jobs(source_dir)
    )
    if not jobs:
        raise ValueError(f"No usable job files found in: {source_dir}")
    user_context = load_user_context_from_directory(profile_dir)

    successes = 0
    for index, job in enumerate(jobs, start=1):
        destination = output_dir / (
            f"job_{index}_{safe_filename_component(job.company.name)}"
        )
        try:
            result = await generate_resume(user_context, job, destination)
        except (AgentRunError, OSError, RuntimeError) as error:
            console.print(f"[red]Resume generation failed: {error}[/red]")
            continue
        successes += 1
        console.print(f"[green]✓ Resume generated: {result.pdf_path}[/green]")

    if successes == 0:
        raise RuntimeError("All resume generations failed.")
    console.print(Panel(f"Generated {successes}/{len(jobs)} resumes"))


async def process_raw_jobs(console: Console, job_dir: Path) -> list:
    from hireme.agents.job_agent import JobDetails, extract_job

    jobs: list[JobDetails] = []
    for job_file in sorted(job_dir.glob("*.txt")):
        result = await extract_job(job_file.read_text(encoding="utf-8"))
        if isinstance(result, JobDetails):
            jobs.append(result)
        else:
            console.print(
                f"[red]Extraction failed for {job_file.name}: {result.reason}[/red]"
            )
    return jobs


def process_parsed_jobs(job_dir: Path) -> list:
    from hireme.agents.job_agent import JobDetails

    jobs: list[JobDetails] = []
    for job_file in sorted(job_dir.glob("*.json")):
        data = json.loads(job_file.read_text(encoding="utf-8"))
        payload = data.get("data", data)
        if not isinstance(payload, dict):
            raise ValueError(f"Expected a job mapping in: {job_file}")
        jobs.append(JobDetails.model_validate(payload))
    return jobs
