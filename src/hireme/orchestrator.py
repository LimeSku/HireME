"""Durable orchestration for the end-to-end HireME workflow."""

from pathlib import Path
from time import monotonic
from typing import Literal

from pydantic_ai.exceptions import AgentRunError

from hireme.agents.job_agent import JobDetails
from hireme.agents.match_agent import assess_match
from hireme.agents.resume_agent import generate_resume
from hireme.cli.commands.job_agent_cli import find_jobs
from hireme.db import (
    ApplicationStatus,
    DatabaseManager,
    WorkflowRun,
    WorkflowStatus,
    get_db,
)
from hireme.utils.common import load_user_context_from_directory


def _get_workflow(db: DatabaseManager, workflow_id: int) -> WorkflowRun:
    workflow = db.get_workflow_run(workflow_id)
    if workflow is None:
        raise ValueError(f"Workflow {workflow_id} not found.")
    return workflow


def _record_failure(
    db: DatabaseManager,
    workflow_id: int,
    stage: str,
    started_at: float,
    error: Exception,
) -> None:
    db.add_workflow_step(
        workflow_id,
        name=stage,
        status="failed",
        duration_seconds=monotonic() - started_at,
        detail=str(error),
    )
    db.update_workflow_run(workflow_id, status=WorkflowStatus.FAILED, error=str(error))


async def start_workflow(
    *,
    query: str,
    location: str,
    profile_name: str,
    profile_dir: Path,
    mode: Literal["scraper", "testing"],
    max_results_per_source: int,
    output_dir: Path,
) -> WorkflowRun:
    db = get_db()
    workflow = db.create_workflow_run(
        profile_name=profile_name,
        profile_path=str(profile_dir.resolve()),
        query=query,
        location=location,
        mode=mode,
        max_results_per_source=max_results_per_source,
        output_dir=str(output_dir.resolve()),
    )
    return await prepare_workflow(workflow.id)


async def prepare_workflow(workflow_id: int) -> WorkflowRun:
    """Advance a workflow through extraction and matching checkpoints."""
    db = get_db()
    workflow = _get_workflow(db, workflow_id)
    if workflow.status == WorkflowStatus.COMPLETED.value:
        return workflow

    if not workflow.job_offer_ids:
        stage = "search_and_extract"
        started_at = monotonic()
        try:
            if workflow.mode == "scraper":
                mode: Literal["scraper", "testing"] = "scraper"
            elif workflow.mode == "testing":
                mode = "testing"
            else:
                raise ValueError(f"Unsupported workflow mode: {workflow.mode}")
            successes, total, job_ids, tokens = await find_jobs(
                query=workflow.query,
                location=workflow.location,
                max_results_per_source=workflow.max_results_per_source,
                mode=mode,
                save_to_db=True,
                export_dir=None,
            )
            if not job_ids:
                raise RuntimeError("No job offer could be extracted.")
            db.update_workflow_run(
                workflow_id,
                status=WorkflowStatus.RUNNING,
                job_offer_ids=job_ids,
                tokens_used=workflow.tokens_used + tokens,
                error="",
            )
            db.add_workflow_step(
                workflow_id,
                name=stage,
                status="completed",
                duration_seconds=monotonic() - started_at,
                detail=f"{successes}/{total} offers extracted",
            )
        except (AgentRunError, OSError, RuntimeError, ValueError) as error:
            _record_failure(db, workflow_id, stage, started_at, error)
            raise
        workflow = _get_workflow(db, workflow_id)

    if not workflow.matches:
        stage = "match"
        started_at = monotonic()
        try:
            candidate = load_user_context_from_directory(Path(workflow.profile_path))
            matches: list[dict] = []
            tokens = 0
            for job_id in workflow.job_offer_ids:
                stored_job = db.get_job_by_id(job_id)
                if stored_job is None or not stored_job.processed_data:
                    raise ValueError(f"Processed job {job_id} not found.")
                job = JobDetails.model_validate(stored_job.processed_data)
                result = await assess_match(candidate, job)
                tokens += result.tokens_used
                matches.append(
                    {
                        "job_id": job_id,
                        "title": stored_job.title,
                        "company": stored_job.company_name,
                        "model_used": result.model_used,
                        "duration_seconds": result.duration_seconds,
                        **result.assessment.model_dump(mode="json"),
                    }
                )
            matches.sort(key=lambda match: match["score"], reverse=True)
            selected_job_id = int(matches[0]["job_id"])
            db.update_workflow_run(
                workflow_id,
                status=WorkflowStatus.AWAITING_APPROVAL,
                matches=matches,
                selected_job_id=selected_job_id,
                tokens_used=workflow.tokens_used + tokens,
                error="",
            )
            db.add_workflow_step(
                workflow_id,
                name=stage,
                status="completed",
                duration_seconds=monotonic() - started_at,
                detail=f"{len(matches)} offers ranked",
            )
        except (AgentRunError, OSError, RuntimeError, ValueError) as error:
            _record_failure(db, workflow_id, stage, started_at, error)
            raise

    return _get_workflow(db, workflow_id)


async def complete_workflow(
    workflow_id: int, selected_job_id: int | None = None
) -> WorkflowRun:
    """Generate and persist the approved resume for a prepared workflow."""
    db = get_db()
    workflow = _get_workflow(db, workflow_id)
    if workflow.status == WorkflowStatus.COMPLETED.value:
        return workflow
    if selected_job_id is not None:
        match_ids = {int(match["job_id"]) for match in workflow.matches}
        if selected_job_id not in match_ids:
            raise ValueError(
                f"Job {selected_job_id} is not part of workflow {workflow_id}."
            )
        db.update_workflow_run(workflow_id, selected_job_id=selected_job_id)
        workflow = _get_workflow(db, workflow_id)
    if workflow.selected_job_id is None:
        raise ValueError(f"Workflow {workflow_id} has no selected job to approve.")

    stage = "generate_resume"
    started_at = monotonic()
    try:
        stored_job = db.get_job_by_id(workflow.selected_job_id)
        if stored_job is None or not stored_job.processed_data:
            raise ValueError(f"Processed job {workflow.selected_job_id} not found.")
        job = JobDetails.model_validate(stored_job.processed_data)
        candidate = load_user_context_from_directory(Path(workflow.profile_path))
        destination = (
            Path(workflow.output_dir)
            / f"run_{workflow.id}_job_{workflow.selected_job_id}"
        )
        result = await generate_resume(candidate, job, destination)
        resume = db.add_generated_resume(
            job_offer_id=workflow.selected_job_id,
            profile_name=workflow.profile_name,
            resume_data=result.resume.model_dump(mode="json"),
            yaml_path=str(result.yaml_path),
            pdf_path=str(result.pdf_path),
            model_used=result.model_used,
            generation_time_seconds=result.duration_seconds,
            tokens_used=result.tokens_used,
        )
        db.select_resume(resume.id)
        db.create_application(workflow.selected_job_id)
        db.update_application_status(
            workflow.selected_job_id, ApplicationStatus.RESUME_GENERATED
        )
        db.update_workflow_run(
            workflow_id,
            status=WorkflowStatus.COMPLETED,
            pdf_path=str(result.pdf_path),
            tokens_used=workflow.tokens_used + result.tokens_used,
            error="",
        )
        db.add_workflow_step(
            workflow_id,
            name=stage,
            status="completed",
            duration_seconds=monotonic() - started_at,
            detail=str(result.pdf_path),
        )
    except (AgentRunError, OSError, RuntimeError, ValueError) as error:
        _record_failure(db, workflow_id, stage, started_at, error)
        raise
    return _get_workflow(db, workflow_id)
