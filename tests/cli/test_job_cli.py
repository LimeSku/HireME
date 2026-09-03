from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from hireme.agents.job_agent import CompanyInfo, ExtractionFailed, JobDetails
from hireme.cli.commands.job_agent_cli import _find_jobs, app

runner = CliRunner()


def test_help_describes_the_current_command() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Find job postings" in result.output
    assert "--location" in result.output
    assert "--db" in result.output


def test_find_forwards_validated_options(tmp_path: Path) -> None:
    with patch(
        "hireme.cli.commands.job_agent_cli._find_jobs",
        new_callable=AsyncMock,
        return_value=(1, 1),
    ) as find_jobs:
        result = runner.invoke(
            app,
            [
                "Data Analyst",
                "--location",
                "Lyon",
                "--max-results-per-source",
                "5",
                "--mode",
                "testing",
                "--no-db",
                "--export-dir",
                str(tmp_path),
            ],
        )

    assert result.exit_code == 0
    find_jobs.assert_awaited_once_with(
        query="Data Analyst",
        location="Lyon",
        max_results_per_source=5,
        mode="testing",
        save_to_db=False,
        export_dir=tmp_path,
    )


def test_find_returns_failure_when_nothing_is_extracted() -> None:
    with patch(
        "hireme.cli.commands.job_agent_cli._find_jobs",
        new_callable=AsyncMock,
        return_value=(0, 1),
    ):
        result = runner.invoke(
            app, ["Python", "--location", "Paris", "--mode", "testing"]
        )

    assert result.exit_code == 1


@pytest.mark.asyncio
async def test_testing_mode_persists_the_extracted_job() -> None:
    extracted = JobDetails(
        title="Python Developer",
        company=CompanyInfo(name="TechCorp"),
        location="Paris",
    )
    database = MagicMock()
    database.add_job_offer.return_value = MagicMock(id=7)

    with (
        patch(
            "hireme.agents.job_agent.extract_job",
            new_callable=AsyncMock,
            return_value=extracted,
        ),
        patch("hireme.db.get_db", return_value=database),
    ):
        result = await _find_jobs(
            query="Python",
            location="Paris",
            max_results_per_source=1,
            mode="testing",
            save_to_db=True,
            export_dir=None,
        )

    assert result == (1, 1)
    database.add_job_offer.assert_called_once()
    database.mark_job_processed.assert_called_once_with(
        7, extracted.model_dump(mode="json")
    )


@pytest.mark.asyncio
async def test_testing_mode_does_not_persist_failed_extraction() -> None:
    database = MagicMock()
    with (
        patch(
            "hireme.agents.job_agent.extract_job",
            new_callable=AsyncMock,
            return_value=ExtractionFailed(reason="invalid posting"),
        ),
        patch("hireme.db.get_db", return_value=database),
    ):
        result = await _find_jobs(
            query="Python",
            location="Paris",
            max_results_per_source=1,
            mode="testing",
            save_to_db=True,
            export_dir=None,
        )

    assert result == (0, 1)
    database.add_job_offer.assert_not_called()
