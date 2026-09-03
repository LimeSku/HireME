"""Commands for orchestrated end-to-end workflows."""

import asyncio
from pathlib import Path
from typing import Annotated, Literal

import typer
from pydantic_ai.exceptions import AgentRunError
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from hireme.cli.commands.profile.common import (
    complete_profile_names,
    find_profile_dir_by_name,
    select_profile,
)
from hireme.config import cfg
from hireme.db import WorkflowRun, WorkflowStatus, get_db
from hireme.orchestrator import complete_workflow, prepare_workflow, start_workflow
from hireme.utils.providers import LLMConfigurationError

console = Console()
app = typer.Typer(
    help="Run and inspect the agentic application workflow", no_args_is_help=True
)


def _resolve_profile(profile_name: str | None) -> tuple[str, Path]:
    if profile_name is None and cfg.default_profile_dir.is_dir():
        return cfg.default_profile_dir.name, cfg.default_profile_dir
    name = profile_name or select_profile(console)
    profile_dir = find_profile_dir_by_name(name)
    if profile_dir is None:
        raise ValueError(f"Profile not found: {name}")
    return name, profile_dir


def _show_matches(workflow: WorkflowRun) -> None:
    table = Table(title=f"Workflow #{workflow.id} shortlist")
    table.add_column("Job", style="cyan")
    table.add_column("Company", style="green")
    table.add_column("Score", justify="right")
    table.add_column("Recommendation")
    table.add_column("Summary", max_width=60)
    for match in workflow.matches:
        selected = " ★" if match["job_id"] == workflow.selected_job_id else ""
        table.add_row(
            f"{match['job_id']}{selected}",
            str(match["company"]),
            str(match["score"]),
            str(match["recommendation"]),
            str(match["summary"]),
        )
    console.print(table)


def _show_timeline(workflow: WorkflowRun) -> None:
    table = Table(title="Agent timeline")
    table.add_column("Stage")
    table.add_column("Status")
    table.add_column("Duration", justify="right")
    table.add_column("Detail")
    for step in workflow.steps:
        table.add_row(
            step.name,
            step.status,
            f"{step.duration_seconds:.2f}s",
            step.detail or "-",
        )
    console.print(table)


def _show_top_match_evidence(workflow: WorkflowRun) -> None:
    match = next(
        (
            item
            for item in workflow.matches
            if item["job_id"] == workflow.selected_job_id
        ),
        None,
    )
    if match is None:
        return
    table = Table(title="Top match evidence")
    table.add_column("Job requirement")
    table.add_column("Candidate fact")
    for evidence in match["evidence"]:
        table.add_row(
            str(evidence["job_requirement"]),
            str(evidence["candidate_fact"] or "No supporting fact"),
        )
    console.print(table)


def _approved_job_id(
    workflow: WorkflowRun,
    approve: bool,
    selected_job_id: int | None = None,
) -> int | None:
    default_job_id = selected_job_id or workflow.selected_job_id
    if approve:
        return default_job_id
    if not typer.confirm("Generate a resume for one of these matches?"):
        return None
    return typer.prompt("Job ID to approve", default=default_job_id, type=int)


def _handle_workflow_error(error: Exception) -> None:
    console.print(f"[red]{error}[/red]")
    console.print(
        "[dim]The failed checkpoint is available with 'hireme run list'.[/dim]"
    )
    raise typer.Exit(code=1) from error


@app.command("start")
def start(
    query: Annotated[str, typer.Argument(help="Job title or search keywords.")],
    location: Annotated[str, typer.Option(help="Location to search.")],
    profile_name: Annotated[
        str | None,
        typer.Option(help="Profile name.", autocompletion=complete_profile_names),
    ] = None,
    mode: Annotated[
        Literal["testing", "scraper"],
        typer.Option(help="Use the sample posting or live job boards."),
    ] = "scraper",
    max_results_per_source: Annotated[
        int, typer.Option(min=1, help="Maximum results fetched from each source.")
    ] = 1,
    output_dir: Annotated[
        Path, typer.Option(help="Destination for generated artifacts.")
    ] = Path("output"),
    approve: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Approve the top match without prompting."),
    ] = False,
) -> None:
    """Search, extract, rank and optionally generate the best resume."""
    try:
        name, profile_dir = _resolve_profile(profile_name)
        workflow = asyncio.run(
            start_workflow(
                query=query,
                location=location,
                profile_name=name,
                profile_dir=profile_dir,
                mode=mode,
                max_results_per_source=max_results_per_source,
                output_dir=output_dir,
            )
        )
        _show_matches(workflow)
        _show_top_match_evidence(workflow)
        selected_job_id = _approved_job_id(workflow, approve)
        if selected_job_id is not None:
            workflow = asyncio.run(
                complete_workflow(workflow.id, selected_job_id=selected_job_id)
            )
            console.print(Panel(f"[green]Completed: {workflow.pdf_path}[/green]"))
        else:
            console.print(
                f"[yellow]Awaiting approval. Resume with: hireme run resume {workflow.id}[/yellow]"
            )
    except (
        AgentRunError,
        LLMConfigurationError,
        OSError,
        RuntimeError,
        ValueError,
    ) as error:
        _handle_workflow_error(error)


@app.command("resume")
def resume_run(
    workflow_id: Annotated[int, typer.Argument(help="Workflow run ID.")],
    selected_job_id: Annotated[
        int | None,
        typer.Option("--job-id", help="Choose a ranked job instead of the top match."),
    ] = None,
    approve: Annotated[
        bool, typer.Option("--yes", "-y", help="Approve without prompting.")
    ] = False,
) -> None:
    """Resume a failed or approval-pending workflow from its checkpoint."""
    try:
        workflow = get_db().get_workflow_run(workflow_id)
        if workflow is None:
            raise ValueError(f"Workflow {workflow_id} not found.")
        if workflow.status == WorkflowStatus.FAILED.value and not workflow.matches:
            workflow = asyncio.run(prepare_workflow(workflow_id))
        if workflow.status == WorkflowStatus.COMPLETED.value:
            console.print(f"[green]Already completed: {workflow.pdf_path}[/green]")
            return
        _show_matches(workflow)
        _show_top_match_evidence(workflow)
        approved_job_id = _approved_job_id(workflow, approve, selected_job_id)
        if approved_job_id is None:
            console.print("[yellow]Workflow remains awaiting approval.[/yellow]")
            return
        workflow = asyncio.run(
            complete_workflow(workflow_id, selected_job_id=approved_job_id)
        )
        console.print(Panel(f"[green]Completed: {workflow.pdf_path}[/green]"))
    except (
        AgentRunError,
        LLMConfigurationError,
        OSError,
        RuntimeError,
        ValueError,
    ) as error:
        _handle_workflow_error(error)


@app.command("list")
def list_runs(
    limit: Annotated[int, typer.Option(min=1, help="Maximum runs to display.")] = 20,
) -> None:
    """List recent workflow runs."""
    workflows = get_db().list_workflow_runs(limit)
    if not workflows:
        console.print("[yellow]No workflow runs found.[/yellow]")
        return
    table = Table(title="Agentic workflow runs")
    table.add_column("ID", style="cyan")
    table.add_column("Status")
    table.add_column("Query")
    table.add_column("Profile")
    table.add_column("Selected job")
    table.add_column("Tokens", justify="right")
    for workflow in workflows:
        table.add_row(
            str(workflow.id),
            workflow.status,
            workflow.query,
            workflow.profile_name,
            str(workflow.selected_job_id or "-"),
            str(workflow.tokens_used),
        )
    console.print(table)


@app.command("show")
def show_run(
    workflow_id: Annotated[int, typer.Argument(help="Workflow run ID.")],
) -> None:
    """Show a workflow shortlist and execution timeline."""
    workflow = get_db().get_workflow_run(workflow_id)
    if workflow is None:
        raise typer.BadParameter(f"Workflow {workflow_id} not found.")
    console.print(
        Panel(
            f"Status: {workflow.status}\nQuery: {workflow.query}\n"
            f"Profile: {workflow.profile_name}\nTokens: {workflow.tokens_used}\n"
            f"Artifact: {workflow.pdf_path or '-'}"
        )
    )
    if workflow.matches:
        _show_matches(workflow)
        _show_top_match_evidence(workflow)
    _show_timeline(workflow)
