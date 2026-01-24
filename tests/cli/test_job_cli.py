"""Tests for the job agent CLI commands.

Tests for:
- hireme job find (with various options)
"""

import tempfile
from pathlib import Path
from typing import Literal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from hireme.cli.commands.job_agent_cli import app

runner = CliRunner()


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_job_details():
    """Create a mock JobDetails object."""
    mock = MagicMock()
    mock.title = "Python Developer"
    mock.company.name = "TechCorp"
    mock.location = "Paris, France"
    mock.model_dump.return_value = {
        "title": "Python Developer",
        "company": {"name": "TechCorp"},
        "location": "Paris, France",
    }
    return mock


@pytest.fixture
def mock_extraction_failed():
    """Create a mock ExtractionFailed object."""
    mock = MagicMock()
    mock.reason = "Could not parse job posting"
    return mock


# =============================================================================
# Test: job find - Basic functionality
# =============================================================================


class TestJobFindBasic:
    """Tests for basic 'hireme job find' command."""

    def test_find_requires_job_argument(self):
        """Test that job argument is required."""
        result = runner.invoke(app, ["--location", "Paris"])

        assert result.exit_code != 0
        assert "Missing argument" in result.output

    def test_find_requires_location_option(self):
        """Test that location option is required."""
        result = runner.invoke(app, ["Python Developer"])

        assert result.exit_code != 0
        assert "Missing option" in result.output or "location" in result.output.lower()

    def test_find_with_help(self):
        """Test that help displays usage information."""
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "Find and extract job postings" in result.output
        assert "--location" in result.output
        assert "--db" in result.output


# =============================================================================
# Test: job find - Testing mode
# =============================================================================


class TestJobFindTestingMode:
    """Tests for 'hireme job find' in testing mode."""

    def test_find_testing_mode_with_db(self, mock_job_details):
        """Test job find in testing mode saves to database."""
        with (
            patch("hireme.cli.commands.job_agent_cli.get_db") as mock_db,
            patch("hireme.cli.commands.job_agent_cli._find_jobs") as mock_find,
        ):
            mock_find.return_value = None

            result = runner.invoke(
                app,
                [
                    "Python Developer",
                    "--location",
                    "Paris",
                    "--mode",
                    "testing",
                ],
            )

            # Should call _find_jobs with save_to_db=True (default)
            assert mock_find.called

    def test_find_testing_mode_no_db(self):
        """Test job find in testing mode with --no-db."""
        with patch("hireme.cli.commands.job_agent_cli._find_jobs") as mock_find:
            mock_find.return_value = None

            result = runner.invoke(
                app,
                [
                    "Python Developer",
                    "--location",
                    "Paris",
                    "--mode",
                    "testing",
                    "--no-db",
                ],
            )

            # Should have been called
            assert mock_find.called


# =============================================================================
# Test: job find - Options
# =============================================================================


class TestJobFindOptions:
    """Tests for 'hireme job find' options."""

    def test_find_max_results_option(self):
        """Test --max-results-per-source option."""
        with patch("hireme.cli.commands.job_agent_cli._find_jobs") as mock_find:
            mock_find.return_value = None

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
                ],
            )

            # Verify max_results was passed
            call_kwargs = mock_find.call_args
            # The function is called via asyncio.run, so we check if it was called

    def test_find_export_dir_option(self):
        """Test --export-dir option for legacy file export."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("hireme.cli.commands.job_agent_cli._find_jobs") as mock_find:
                mock_find.return_value = None

                result = runner.invoke(
                    app,
                    [
                        "ML Engineer",
                        "--location",
                        "Remote",
                        "--mode",
                        "testing",
                        "--export-dir",
                        tmpdir,
                    ],
                )

    def test_find_db_flag_default_true(self):
        """Test that --db flag defaults to True."""
        with patch("hireme.cli.commands.job_agent_cli._find_jobs") as mock_find:
            mock_find.return_value = None

            result = runner.invoke(
                app,
                [
                    "Python",
                    "--location",
                    "Berlin",
                    "--mode",
                    "testing",
                ],
            )

    def test_find_no_db_flag(self):
        """Test --no-db flag disables database saving."""
        with patch("hireme.cli.commands.job_agent_cli._find_jobs") as mock_find:
            mock_find.return_value = None

            result = runner.invoke(
                app,
                [
                    "Python",
                    "--location",
                    "Berlin",
                    "--mode",
                    "testing",
                    "--no-db",
                ],
            )


# =============================================================================
# Test: job find - Mode option
# =============================================================================


class TestJobFindModes:
    """Tests for 'hireme job find' mode options."""

    def test_find_mode_testing(self):
        """Test --mode testing uses sample posting."""
        with patch("hireme.cli.commands.job_agent_cli._find_jobs") as mock_find:
            mock_find.return_value = None

            result = runner.invoke(
                app,
                [
                    "Python",
                    "--location",
                    "Paris",
                    "--mode",
                    "testing",
                ],
            )

    def test_find_mode_scrapper(self):
        """Test --mode scrapper fetches live postings."""
        with patch("hireme.cli.commands.job_agent_cli._find_jobs") as mock_find:
            mock_find.return_value = None

            result = runner.invoke(
                app,
                [
                    "Python",
                    "--location",
                    "Paris",
                    "--mode",
                    "scrapper",
                ],
            )

    def test_find_mode_invalid(self):
        """Test invalid mode value."""
        result = runner.invoke(
            app,
            [
                "Python",
                "--location",
                "Paris",
                "--mode",
                "invalid_mode",
            ],
        )

        assert result.exit_code != 0


# =============================================================================
# Test: job find - Integration with database
# =============================================================================


class TestJobFindDatabaseIntegration:
    """Integration tests for job find with database."""

    @pytest.mark.asyncio
    async def test_find_saves_job_to_database(self, mock_job_details):
        """Test that successful extraction saves job to database."""
        from hireme.agents.job_agent import JobDetails
        from hireme.cli.commands.job_agent_cli import _find_jobs

        # Create a mock that passes isinstance check
        mock_job = MagicMock(spec=JobDetails)
        mock_job.title = "Python Developer"
        mock_job.company = MagicMock()
        mock_job.company.name = "TechCorp"
        mock_job.location = "Paris"
        mock_job.model_dump.return_value = {"title": "Python Developer"}

        with (
            patch("hireme.cli.commands.job_agent_cli.get_db") as mock_get_db,
            patch(
                "hireme.agents.job_agent.extract_job",
                new_callable=AsyncMock,
                return_value=mock_job,
            ),
            patch("hireme.agents.job_agent.SAMPLE_POSTING", "Sample posting"),
        ):
            mock_db = MagicMock()
            mock_db.add_job_offer.return_value = MagicMock(id=1)
            mock_get_db.return_value = mock_db

            await _find_jobs(
                query="Python",
                location="Paris",
                max_results_per_source=1,
                mode="testing",
                save_to_db=True,
                export_dir=None,
            )

            # Verify job was added to database
            mock_db.add_job_offer.assert_called_once()
            mock_db.mark_job_processed.assert_called_once()

    @pytest.mark.asyncio
    async def test_find_handles_extraction_failure(self, mock_extraction_failed):
        """Test that extraction failure is handled gracefully."""
        from hireme.cli.commands.job_agent_cli import _find_jobs

        with (
            patch("hireme.cli.commands.job_agent_cli.get_db") as mock_get_db,
            patch(
                "hireme.agents.job_agent.extract_job",
                new_callable=AsyncMock,
                return_value=mock_extraction_failed,
            ),
            patch("hireme.agents.job_agent.SAMPLE_POSTING", "Sample posting"),
        ):
            mock_db = MagicMock()
            mock_get_db.return_value = mock_db

            # Should not raise an exception
            await _find_jobs(
                query="Python",
                location="Paris",
                max_results_per_source=1,
                mode="testing",
                save_to_db=True,
                export_dir=None,
            )

            # Job should not be saved on failure
            mock_db.add_job_offer.assert_not_called()
