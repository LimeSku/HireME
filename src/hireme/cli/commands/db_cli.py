"""CLI for database management operations.

Provides commands to view, search, and manage job offers, resumes, and applications.
"""

# from datetime import datetime
# from pathlib import Path
from typing import Annotated, Optional

import structlog
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from hireme.db import (
    ApplicationStatus,
    # JobSource,
    get_db,
)

logger = structlog.get_logger()
console = Console()

app = typer.Typer(name="db", help="Database management commands", no_args_is_help=True)


# =============================================================================
# Job Commands
# =============================================================================

jobs_app = typer.Typer(name="jobs", help="Manage job offers")
app.add_typer(jobs_app, name="jobs")


@jobs_app.command("list")
def list_jobs(
    processed_only: Annotated[
        bool, typer.Option("--processed", help="Show only processed jobs")
    ] = False,
    include_archived: Annotated[
        bool, typer.Option("--archived", help="Include archived jobs")
    ] = False,
    limit: Annotated[int, typer.Option(help="Limit results")] = 20,
):
    """List all job offers."""
    db = get_db()
    jobs = db.get_all_jobs(
        include_archived=include_archived, only_processed=processed_only
    )[:limit]

    if not jobs:
        console.print("[yellow]No job offers found.[/yellow]")
        return

    table = Table(title=f"Job Offers ({len(jobs)} shown)")
    table.add_column("ID", style="cyan", width=4)
    table.add_column("Title", style="white", max_width=40)
    table.add_column("Company", style="green", max_width=20)
    table.add_column("Location", style="blue", max_width=15)
    table.add_column("Status", style="yellow", width=10)
    table.add_column("Resumes", style="magenta", width=7)
    table.add_column("Date", style="dim", width=10)

    for job in jobs:
        status = "✓ Parsed" if job.is_processed else "Raw"
        resumes = len(job.resumes) if job.resumes else 0
        date = job.discovered_at.strftime("%Y-%m-%d")

        table.add_row(
            str(job.id),
            job.title[:40] if job.title else "N/A",
            job.company_name[:20] if job.company_name else "N/A",
            (job.location or "N/A")[:15],
            status,
            str(resumes),
            date,
        )

    console.print(table)


@jobs_app.command("show")
def show_job(
    job_id: Annotated[int, typer.Argument(help="Job ID to show")],
):
    """Show details of a specific job offer."""
    db = get_db()
    job = db.get_job_by_id(job_id)

    if not job:
        console.print(f"[red]Job with ID {job_id} not found.[/red]")
        raise typer.Exit(code=1)

    # Basic info
    console.print(Panel(f"[bold]{job.title}[/bold]", subtitle=job.company_name))
    console.print(f"[bold]ID:[/bold] {job.id}")
    console.print(f"[bold]Location:[/bold] {job.location or 'N/A'}")
    console.print(f"[bold]Source:[/bold] {job.source}")
    console.print(f"[bold]URL:[/bold] {job.url or 'N/A'}")
    console.print(f"[bold]Status:[/bold] {'Processed' if job.is_processed else 'Raw'}")
    console.print(f"[bold]Discovered:[/bold] {job.discovered_at}")

    if job.processed_at:
        console.print(f"[bold]Processed:[/bold] {job.processed_at}")

    # Resumes
    if job.resumes:
        console.print(f"\n[bold]Generated Resumes:[/bold] {len(job.resumes)}")
        for resume in job.resumes:
            selected = " ⭐" if resume.is_selected else ""
            console.print(f"  - Resume #{resume.id} ({resume.profile_name}){selected}")

    # Application status
    if job.application:
        console.print(f"\n[bold]Application Status:[/bold] {job.application.status}")


@jobs_app.command("search")
def search_jobs(
    query: Annotated[str, typer.Argument(help="Search query")],
):
    """Search job offers by title or company."""
    db = get_db()
    jobs = db.search_jobs(query)

    if not jobs:
        console.print(f"[yellow]No jobs found matching '{query}'.[/yellow]")
        return

    console.print(f"[green]Found {len(jobs)} job(s):[/green]")
    for job in jobs:
        console.print(f"  [{job.id}] {job.title} @ {job.company_name}")


@jobs_app.command("archive")
def archive_job(
    job_id: Annotated[int, typer.Argument(help="Job ID to archive")],
):
    """Archive a job offer."""
    db = get_db()
    if db.archive_job(job_id):
        console.print(f"[green]Job {job_id} archived.[/green]")
    else:
        console.print(f"[red]Job {job_id} not found.[/red]")


# =============================================================================
# Resume Commands
# =============================================================================

resumes_app = typer.Typer(name="resumes", help="Manage generated resumes")
app.add_typer(resumes_app, name="resumes")


@resumes_app.command("list")
def list_resumes(
    job_id: Annotated[
        Optional[int], typer.Option("--job", help="Filter by job ID")
    ] = None,
):
    """List generated resumes."""
    db = get_db()

    if job_id:
        resumes = db.get_resumes_for_job(job_id)
        if not resumes:
            console.print(f"[yellow]No resumes found for job {job_id}.[/yellow]")
            return
    else:
        # Get all resumes from all jobs
        with db.get_session() as session:
            from hireme.db.database import GeneratedResume

            resumes = (
                session.query(GeneratedResume)
                .order_by(GeneratedResume.generated_at.desc())
                .limit(50)
                .all()
            )

    table = Table(title="Generated Resumes")
    table.add_column("ID", style="cyan", width=4)
    table.add_column("Job ID", style="dim", width=6)
    table.add_column("Profile", style="green", width=15)
    table.add_column("Model", style="blue", width=15)
    table.add_column("Selected", style="yellow", width=8)
    table.add_column("Rating", style="magenta", width=6)
    table.add_column("Date", style="dim", width=12)

    for resume in resumes:
        selected = "⭐" if resume.is_selected else ""
        rating = f"{'★' * resume.user_rating}" if resume.user_rating else "-"
        date = resume.generated_at.strftime("%Y-%m-%d")

        table.add_row(
            str(resume.id),
            str(resume.job_offer_id),
            resume.profile_name,
            resume.model_used or "N/A",
            selected,
            rating,
            date,
        )

    console.print(table)


@resumes_app.command("select")
def select_resume(
    resume_id: Annotated[int, typer.Argument(help="Resume ID to select")],
):
    """Mark a resume as the selected version for its job."""
    db = get_db()
    if db.select_resume(resume_id):
        console.print(f"[green]Resume {resume_id} selected.[/green]")
    else:
        console.print(f"[red]Resume {resume_id} not found.[/red]")


@resumes_app.command("rate")
def rate_resume(
    resume_id: Annotated[int, typer.Argument(help="Resume ID to rate")],
    rating: Annotated[int, typer.Argument(help="Rating (1-5)")],
    notes: Annotated[Optional[str], typer.Option(help="Additional notes")] = None,
):
    """Rate a generated resume."""
    if rating < 1 or rating > 5:
        console.print("[red]Rating must be between 1 and 5.[/red]")
        raise typer.Exit(code=1)

    db = get_db()
    if db.rate_resume(resume_id, rating, notes):
        console.print(f"[green]Resume {resume_id} rated {'★' * rating}.[/green]")
    else:
        console.print(f"[red]Resume {resume_id} not found.[/red]")


# =============================================================================
# Application Commands
# =============================================================================

apps_app = typer.Typer(name="apps", help="Manage job applications")
app.add_typer(apps_app, name="apps")


@apps_app.command("list")
def list_applications(
    status: Annotated[
        Optional[str],
        typer.Option("--status", help="Filter by status"),
    ] = None,
):
    """List all applications."""
    db = get_db()

    with db.get_session() as session:
        from sqlalchemy.orm import selectinload

        from hireme.db.database import Application, JobOffer

        query = (
            session.query(Application)
            .options(selectinload(Application.job_offer))
            .join(JobOffer)
        )

        if status:
            query = query.filter(Application.status == status)

        applications = query.order_by(Application.updated_at.desc()).all()
        session.expunge_all()

    if not applications:
        console.print("[yellow]No applications found.[/yellow]")
        return

    table = Table(title="Applications")
    table.add_column("ID", style="cyan", width=4)
    table.add_column("Job", style="white", max_width=30)
    table.add_column("Company", style="green", max_width=20)
    table.add_column("Status", style="yellow", width=20)
    table.add_column("Applied", style="blue", width=12)
    table.add_column("Updated", style="dim", width=12)

    for application in applications:
        applied = (
            application.applied_at.strftime("%Y-%m-%d")
            if application.applied_at
            else "-"
        )
        updated = application.updated_at.strftime("%Y-%m-%d")

        table.add_row(
            str(application.id),
            application.job_offer.title[:30] if application.job_offer else "N/A",
            application.job_offer.company_name[:20] if application.job_offer else "N/A",
            application.status,
            applied,
            updated,
        )

    console.print(table)


@apps_app.command("update")
def update_application(
    job_id: Annotated[int, typer.Argument(help="Job ID")],
    status: Annotated[str, typer.Argument(help="New status")],
    notes: Annotated[Optional[str], typer.Option(help="Notes")] = None,
):
    """Update application status."""
    try:
        app_status = ApplicationStatus(status)
    except ValueError:
        valid = ", ".join([s.value for s in ApplicationStatus])
        console.print(f"[red]Invalid status. Valid options: {valid}[/red]")
        raise typer.Exit(code=1)

    db = get_db()

    # Create application if it doesn't exist
    db.create_application(job_id)
    result = db.update_application_status(job_id, app_status, notes)

    if result:
        console.print(
            f"[green]Application for job {job_id} updated to '{status}'.[/green]"
        )
    else:
        console.print("[red]Could not update application.[/red]")


# =============================================================================
# Stats Command
# =============================================================================


@app.command("stats")
def show_stats():
    """Show job search statistics."""
    db = get_db()
    stats = db.get_application_stats()

    console.print(Panel("[bold]Job Search Statistics[/bold]", style="blue"))

    # Jobs overview
    console.print("\n[bold]Jobs:[/bold]")
    console.print(f"  Total jobs tracked: {stats['total_jobs']}")
    console.print(f"  Processed (parsed): {stats['processed_jobs']}")
    console.print(f"  Total resumes generated: {stats['total_resumes']}")

    # Application funnel
    console.print("\n[bold]Application Funnel:[/bold]")
    funnel = [
        ("Not Applied", stats.get("not_applied", 0), "dim"),
        ("Resume Generated", stats.get("resume_generated", 0), "yellow"),
        ("Applied", stats.get("applied", 0), "green"),
        ("Interview Scheduled", stats.get("interview_scheduled", 0), "blue"),
        ("Interviewed", stats.get("interviewed", 0), "cyan"),
        ("Offer Received", stats.get("offer_received", 0), "magenta"),
        ("Accepted", stats.get("accepted", 0), "green bold"),
        ("Rejected", stats.get("rejected", 0), "red"),
        ("Withdrawn", stats.get("withdrawn", 0), "dim"),
    ]

    for label, count, style in funnel:
        bar = "█" * min(count, 20)
        console.print(f"  [{style}]{label:20}[/] {count:3} {bar}")


@app.command("init")
def init_db():
    """Initialize or reset the database."""
    db = get_db()
    console.print(f"[green]Database initialized at: {db.db_path}[/green]")


@app.command("import")
def import_existing():
    """Import existing job files from .hireme directory into database."""
    import json

    from hireme.config import cfg

    db = get_db()
    raw_dir = cfg.job_offers_dir / "raw"
    processed_dir = cfg.job_offers_dir / "processed"

    imported = 0

    # Import raw jobs
    if raw_dir.exists():
        for f in raw_dir.glob("*.txt"):
            content = f.read_text()
            # Try to extract title and company from filename
            # Format: job_Title-Company.txt
            name = f.stem
            if name.startswith("job_"):
                name = name[4:]
            parts = name.rsplit("-", 1)
            title = parts[0] if parts else name
            company = parts[1] if len(parts) > 1 else "Unknown"

            db.add_job_offer(
                title=title,
                company_name=company,
                raw_text=content,
                raw_file_path=str(f),
            )
            imported += 1

    # Import processed jobs
    if processed_dir.exists():
        for f in processed_dir.glob("*.json"):
            try:
                with f.open() as fp:
                    data = json.load(fp)

                job_data = data.get("data", data)
                title = job_data.get("title", f.stem)
                company = job_data.get("company", {}).get("name", "Unknown")

                job = db.add_job_offer(
                    title=title,
                    company_name=company,
                    url=data.get("url"),
                )

                # Mark as processed
                db.mark_job_processed(job.id, job_data, str(f))
                imported += 1

            except Exception as e:
                console.print(f"[yellow]Error importing {f.name}: {e}[/yellow]")

    console.print(f"[green]Imported {imported} job(s) into database.[/green]")


if __name__ == "__main__":
    app()
