from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai import ModelRetry

from hireme.agents.job_agent import CompanyInfo, JobDetails, RequiredSkill
from hireme.agents.match_agent import (
    MatchAssessment,
    MatchContext,
    MatchEvidence,
    MatchRunResult,
    _validate_match,
)
from hireme.db import ApplicationStatus, JobSource, WorkflowStatus
from hireme.db.database import DatabaseManager
from hireme.orchestrator import complete_workflow, prepare_workflow, start_workflow
from hireme.utils.models.models import CandidateProfile, FileContent, UserContext
from hireme.utils.models.resume_models import ResumeGenerationResult, TailoredResume


def _candidate() -> UserContext:
    return UserContext(
        profile=CandidateProfile(
            name="Ada Lovelace", email="ada@example.com", location="Paris"
        ),
        files=[
            FileContent(
                filename="context.md",
                file_type="markdown",
                content="Built Python analytical engines.",
            )
        ],
    )


def _job() -> JobDetails:
    return JobDetails(
        title="Python Engineer",
        company=CompanyInfo(name="Example"),
        location="Paris",
        required_skills=[RequiredSkill(name="Python")],
    )


def _assessment() -> MatchAssessment:
    return MatchAssessment(
        score=91,
        recommendation="strong_match",
        summary="Direct Python experience.",
        strengths=["Python"],
        evidence=[
            MatchEvidence(
                job_requirement="Python",
                candidate_fact="Built Python analytical engines.",
            )
        ],
    )


def test_match_evidence_must_quote_candidate_and_job() -> None:
    invalid = _assessment().model_copy(deep=True)
    invalid.evidence[0].candidate_fact = "Invented Kubernetes experience"

    with pytest.raises(ModelRetry, match="candidate fact"):
        _validate_match(
            MagicMock(deps=MatchContext(candidate=_candidate(), job=_job())), invalid
        )


@pytest.mark.asyncio
async def test_workflow_runs_end_to_end_from_durable_checkpoints(
    tmp_path: Path,
) -> None:
    database = DatabaseManager(tmp_path / "hireme.db")
    stored_job = database.add_job_offer(
        title="Python Engineer",
        company_name="Example",
        source=JobSource.MANUAL,
        location="Paris",
    )
    database.mark_job_processed(stored_job.id, _job().model_dump(mode="json"))
    profile_dir = tmp_path / "profile"
    profile_dir.mkdir()
    (profile_dir / "profile.yaml").write_text(
        "profile:\n  name: Ada Lovelace\n  email: ada@example.com\n  location: Paris\n",
        encoding="utf-8",
    )
    (profile_dir / "context.md").write_text(
        "Built Python analytical engines.", encoding="utf-8"
    )
    match_result = MatchRunResult(
        assessment=_assessment(),
        model_used="ollama:test",
        tokens_used=30,
        duration_seconds=0.2,
    )

    with (
        patch("hireme.orchestrator.get_db", return_value=database),
        patch(
            "hireme.orchestrator.find_jobs",
            new_callable=AsyncMock,
            return_value=(1, 1, [stored_job.id], 20),
        ) as find_jobs,
        patch(
            "hireme.orchestrator.assess_match",
            new_callable=AsyncMock,
            return_value=match_result,
        ) as assess_match,
    ):
        workflow = await start_workflow(
            query="Python",
            location="Paris",
            profile_name="ada",
            profile_dir=profile_dir,
            mode="testing",
            max_results_per_source=1,
            output_dir=tmp_path / "output",
        )
        resumed = await prepare_workflow(workflow.id)

    assert workflow.status == WorkflowStatus.AWAITING_APPROVAL.value
    assert resumed.status == WorkflowStatus.AWAITING_APPROVAL.value
    assert workflow.selected_job_id == stored_job.id
    assert workflow.tokens_used == 50
    assert [step.name for step in workflow.steps] == ["search_and_extract", "match"]
    find_jobs.assert_awaited_once()
    assess_match.assert_awaited_once()

    resume = TailoredResume(
        name="Ada Lovelace",
        email="ada@example.com",
        location="Paris",
        education=[],
        experience=[],
        projects=[],
        skills=[],
    )
    generation = ResumeGenerationResult(
        resume=resume,
        yaml_path=tmp_path / "output" / "resume.yaml",
        pdf_path=tmp_path / "output" / "resume.pdf",
        model_used="ollama:test",
        tokens_used=40,
        duration_seconds=0.5,
    )
    with (
        patch("hireme.orchestrator.get_db", return_value=database),
        patch(
            "hireme.orchestrator.generate_resume",
            new_callable=AsyncMock,
            return_value=generation,
        ) as generate_resume,
    ):
        with pytest.raises(ValueError, match="not part of workflow"):
            await complete_workflow(workflow.id, selected_job_id=999)
        completed = await complete_workflow(workflow.id)
        completed_again = await complete_workflow(workflow.id)

    assert completed.status == WorkflowStatus.COMPLETED.value
    assert completed_again.status == WorkflowStatus.COMPLETED.value
    generate_resume.assert_awaited_once()
    assert completed.tokens_used == 90
    assert completed.pdf_path == str(generation.pdf_path)
    persisted_job = database.get_job_by_id(stored_job.id)
    assert persisted_job is not None
    assert persisted_job.application is not None
    assert persisted_job.application.status == ApplicationStatus.RESUME_GENERATED.value
    assert persisted_job.resumes[0].is_selected is True
