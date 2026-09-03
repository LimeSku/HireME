import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from hireme.cli.commands.resume_agent_cli import (
    _generate_resume_from_db,
    app,
    process_parsed_jobs,
)

runner = CliRunner()


def test_help_describes_resume_inputs() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "--job-id" in result.output
    assert "--all" in result.output
    assert "--profile-name" in result.output


def test_generate_rejects_an_unknown_profile() -> None:
    with patch(
        "hireme.cli.commands.resume_agent_cli.find_profile_dir_by_name",
        return_value=None,
    ):
        result = runner.invoke(
            app, ["--job-id", "1", "--profile-name", "does-not-exist"]
        )

    assert result.exit_code == 2
    assert "Profile not found" in result.output


def test_generate_dispatches_database_mode(tmp_path: Path) -> None:
    profile_dir = tmp_path / "candidate"
    profile_dir.mkdir()
    with (
        patch(
            "hireme.cli.commands.resume_agent_cli.find_profile_dir_by_name",
            return_value=profile_dir,
        ),
        patch(
            "hireme.cli.commands.resume_agent_cli._generate_resume_from_db",
            new_callable=AsyncMock,
        ) as generate_from_db,
    ):
        result = runner.invoke(
            app,
            [
                "--job-id",
                "42",
                "--profile-name",
                "candidate",
                "--output-dir",
                str(tmp_path / "output"),
            ],
        )

    assert result.exit_code == 0
    generate_from_db.assert_awaited_once_with(
        42, False, profile_dir, "candidate", tmp_path / "output"
    )


@pytest.mark.asyncio
async def test_database_generation_persists_artifact_metadata(tmp_path: Path) -> None:
    job = MagicMock(
        id=7,
        is_processed=True,
        processed_data={
            "title": "Python Developer",
            "company": {"name": "TechCorp"},
            "location": "Paris",
        },
    )
    job.resumes = []
    database = MagicMock()
    database.get_job_by_id.return_value = job
    generation = MagicMock(
        pdf_path=tmp_path / "resume.pdf",
        yaml_path=tmp_path / "resume.yaml",
        model_used="ollama:qwen3:8b",
        duration_seconds=1.5,
        tokens_used=120,
    )
    generation.resume.model_dump.return_value = {"name": "Ada Lovelace"}

    with (
        patch("hireme.db.get_db", return_value=database),
        patch(
            "hireme.utils.common.load_user_context_from_directory",
            return_value=MagicMock(),
        ),
        patch(
            "hireme.agents.resume_agent.generate_resume",
            new_callable=AsyncMock,
            return_value=generation,
        ),
    ):
        await _generate_resume_from_db(
            job_id=7,
            all_jobs=False,
            profile_dir=tmp_path,
            profile_name="candidate",
            output_dir=tmp_path / "output",
        )

    database.add_generated_resume.assert_called_once_with(
        job_offer_id=7,
        profile_name="candidate",
        resume_data={"name": "Ada Lovelace"},
        pdf_path=str(generation.pdf_path),
        yaml_path=str(generation.yaml_path),
        model_used="ollama:qwen3:8b",
        generation_time_seconds=1.5,
        tokens_used=120,
    )


def test_process_parsed_jobs_accepts_export_wrapper(tmp_path: Path) -> None:
    payload = {
        "title": "Data Engineer",
        "company": {"name": "Example"},
        "location": "Remote",
    }
    (tmp_path / "job.json").write_text(
        json.dumps({"url": "https://example.com/job", "data": payload}),
        encoding="utf-8",
    )

    jobs = process_parsed_jobs(tmp_path)

    assert len(jobs) == 1
    assert jobs[0].title == "Data Engineer"
