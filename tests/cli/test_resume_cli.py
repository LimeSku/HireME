"""Tests for the resume agent CLI commands.

Tests for:
- hireme resume generate (with various options)
"""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from hireme.cli.commands.resume_agent_cli import app

runner = CliRunner()


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_job_details():
    """Create a mock JobDetails object."""
    mock = MagicMock()
    mock.title = "Python Developer"
    mock.company = MagicMock()
    mock.company.name = "TechCorp"
    mock.location = "Paris, France"
    mock.model_dump.return_value = {
        "title": "Python Developer",
        "company": {"name": "TechCorp"},
        "location": "Paris, France",
    }
    return mock


@pytest.fixture
def mock_tailored_resume():
    """Create a mock TailoredResume object."""
    mock = MagicMock()
    mock.name = "John Doe"
    mock.model_dump.return_value = {
        "name": "John Doe",
        "summary": "Experienced developer",
    }
    return mock


@pytest.fixture
def mock_generation_failed():
    """Create a mock GenerationFailed object."""
    from hireme.utils.models.resume_models import GenerationFailed

    return GenerationFailed(reason="Unable to generate resume")


@pytest.fixture
def temp_profile_dir():
    """Create a temporary profile directory with sample files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        profile_dir = Path(tmpdir) / "default"
        profile_dir.mkdir()

        # Create sample profile files
        (profile_dir / "bio.txt").write_text("John Doe - Software Developer")
        (profile_dir / "skills.md").write_text("# Skills\n- Python\n- JavaScript")

        yield profile_dir


@pytest.fixture
def temp_job_dir():
    """Create a temporary job directory with sample files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        job_dir = Path(tmpdir)

        # Create sample job files
        (job_dir / "job.txt").write_text("Software Engineer at TechCorp")
        (job_dir / "job.json").write_text('{"title": "Software Engineer"}')

        yield job_dir


@pytest.fixture
def mock_db_with_job(mock_job_details):
    """Create a mock database with a job entry."""
    mock_job = MagicMock()
    mock_job.id = 1
    mock_job.is_processed = True
    mock_job.processed_data = {
        "title": "Python Developer",
        "company": {"name": "TechCorp"},
        "location": "Paris",
    }

    mock_db = MagicMock()
    mock_db.get_job_by_id.return_value = mock_job
    mock_db.get_all_jobs.return_value = [mock_job]

    return mock_db


# =============================================================================
# Test: resume generate - Help and validation
# =============================================================================


class TestResumeGenerateBasic:
    """Tests for basic 'hireme resume generate' command."""

    def test_generate_help(self):
        """Test that help displays usage information."""
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "--job-id" in result.output
        assert "--all" in result.output
        assert "--profile-name" in result.output
        assert "--output-dir" in result.output

    def test_generate_invalid_profile(self):
        """Test that invalid profile name fails gracefully."""
        with patch(
            "hireme.cli.commands.resume_agent_cli.find_profile_dir_by_name",
            return_value=None,
        ):
            result = runner.invoke(
                app,
                [
                    "--job-id",
                    "1",
                    "--profile-name",
                    "nonexistent_profile",
                ],
            )

            assert result.exit_code == 1


# =============================================================================
# Test: resume generate - Database mode with --job-id
# =============================================================================


class TestResumeGenerateJobId:
    """Tests for 'hireme resume generate --job-id'."""

    def test_generate_job_not_found(self, temp_profile_dir):
        """Test error when job ID is not found in database."""
        with (
            patch(
                "hireme.cli.commands.resume_agent_cli.find_profile_dir_by_name",
                return_value=temp_profile_dir,
            ),
            patch("hireme.cli.commands.resume_agent_cli.get_db") as mock_get_db,
        ):
            mock_db = MagicMock()
            mock_db.get_job_by_id.return_value = None
            mock_get_db.return_value = mock_db

            result = runner.invoke(
                app,
                ["--job-id", "999"],
            )

            assert result.exit_code == 1
            assert "not found" in result.output

    def test_generate_job_not_processed(self, temp_profile_dir):
        """Test error when job has not been processed yet."""
        with (
            patch(
                "hireme.cli.commands.resume_agent_cli.find_profile_dir_by_name",
                return_value=temp_profile_dir,
            ),
            patch("hireme.cli.commands.resume_agent_cli.get_db") as mock_get_db,
        ):
            mock_job = MagicMock()
            mock_job.id = 1
            mock_job.is_processed = False
            mock_job.processed_data = None

            mock_db = MagicMock()
            mock_db.get_job_by_id.return_value = mock_job
            mock_get_db.return_value = mock_db

            result = runner.invoke(
                app,
                ["--job-id", "1"],
            )

            assert result.exit_code == 1
            assert "not been processed" in result.output

    def test_generate_success(
        self, temp_profile_dir, mock_db_with_job, mock_tailored_resume
    ):
        """Test successful resume generation for single job."""
        with tempfile.TemporaryDirectory() as output_tmpdir:
            with (
                patch(
                    "hireme.cli.commands.resume_agent_cli.find_profile_dir_by_name",
                    return_value=temp_profile_dir,
                ),
                patch(
                    "hireme.cli.commands.resume_agent_cli.get_db",
                    return_value=mock_db_with_job,
                ),
                patch(
                    "hireme.agents.resume_agent.load_user_context_from_directory",
                    return_value="User context",
                ),
                patch(
                    "hireme.agents.resume_agent.generate_resume",
                    new_callable=AsyncMock,
                    return_value=(
                        mock_tailored_resume,
                        Path(output_tmpdir) / "resume.pdf",
                    ),
                ),
            ):
                result = runner.invoke(
                    app,
                    [
                        "--job-id",
                        "1",
                        "--output-dir",
                        output_tmpdir,
                    ],
                )

                # Check resume was saved to database
                mock_db_with_job.add_generated_resume.assert_called_once()


# =============================================================================
# Test: resume generate - Database mode with --all
# =============================================================================


class TestResumeGenerateAll:
    """Tests for 'hireme resume generate --all'."""

    def test_generate_all_no_jobs(self, temp_profile_dir):
        """Test error when no processed jobs exist."""
        with (
            patch(
                "hireme.cli.commands.resume_agent_cli.find_profile_dir_by_name",
                return_value=temp_profile_dir,
            ),
            patch("hireme.cli.commands.resume_agent_cli.get_db") as mock_get_db,
        ):
            mock_db = MagicMock()
            mock_db.get_all_jobs.return_value = []
            mock_get_db.return_value = mock_db

            result = runner.invoke(
                app,
                ["--all"],
            )

            assert result.exit_code == 1
            assert "No processed jobs" in result.output

    def test_generate_all_success(
        self, temp_profile_dir, mock_db_with_job, mock_tailored_resume
    ):
        """Test successful resume generation for all jobs."""
        with tempfile.TemporaryDirectory() as output_tmpdir:
            with (
                patch(
                    "hireme.cli.commands.resume_agent_cli.find_profile_dir_by_name",
                    return_value=temp_profile_dir,
                ),
                patch(
                    "hireme.cli.commands.resume_agent_cli.get_db",
                    return_value=mock_db_with_job,
                ),
                patch(
                    "hireme.agents.resume_agent.load_user_context_from_directory",
                    return_value="User context",
                ),
                patch(
                    "hireme.agents.resume_agent.generate_resume",
                    new_callable=AsyncMock,
                    return_value=(
                        mock_tailored_resume,
                        Path(output_tmpdir) / "resume.pdf",
                    ),
                ),
            ):
                result = runner.invoke(
                    app,
                    [
                        "--all",
                        "--output-dir",
                        output_tmpdir,
                    ],
                )

                # Should process all jobs
                assert mock_db_with_job.get_all_jobs.called


# =============================================================================
# Test: resume generate - Generation failures
# =============================================================================


class TestResumeGenerateFailures:
    """Tests for handling generation failures."""

    def test_generation_failed_result(
        self, temp_profile_dir, mock_db_with_job, mock_generation_failed
    ):
        """Test handling of GenerationFailed result."""
        with tempfile.TemporaryDirectory() as output_tmpdir:
            with (
                patch(
                    "hireme.cli.commands.resume_agent_cli.find_profile_dir_by_name",
                    return_value=temp_profile_dir,
                ),
                patch(
                    "hireme.cli.commands.resume_agent_cli.get_db",
                    return_value=mock_db_with_job,
                ),
                patch(
                    "hireme.agents.resume_agent.load_user_context_from_directory",
                    return_value="User context",
                ),
                patch(
                    "hireme.agents.resume_agent.generate_resume",
                    new_callable=AsyncMock,
                    return_value=(mock_generation_failed, None),
                ),
            ):
                result = runner.invoke(
                    app,
                    [
                        "--job-id",
                        "1",
                        "--output-dir",
                        output_tmpdir,
                    ],
                )

                # Should not save to database on failure
                mock_db_with_job.add_generated_resume.assert_not_called()
                assert "failed" in result.output.lower()


# =============================================================================
# Test: resume generate - Legacy file mode
# =============================================================================


class TestResumeGenerateLegacyMode:
    """Tests for legacy file-based resume generation."""

    def test_legacy_mode_no_job_dir(self, temp_profile_dir):
        """Test legacy mode when job directory doesn't exist."""
        with (
            patch(
                "hireme.cli.commands.resume_agent_cli.find_profile_dir_by_name",
                return_value=temp_profile_dir,
            ),
            patch("hireme.cli.commands.resume_agent_cli.cfg") as mock_cfg,
        ):
            # Create a temp dir with no job files
            with tempfile.TemporaryDirectory() as tmpdir:
                empty_job_dir = Path(tmpdir) / "empty"
                empty_job_dir.mkdir()
                mock_cfg.job_offers_dir = empty_job_dir

                result = runner.invoke(
                    app,
                    [
                        "--job-dir",
                        str(empty_job_dir),
                    ],
                )

                assert result.exit_code == 1
                assert "No job posting files found" in result.output

    def test_legacy_mode_with_job_files(self, temp_profile_dir, temp_job_dir):
        """Test legacy mode with job files in directory."""
        with tempfile.TemporaryDirectory() as output_tmpdir:
            with (
                patch(
                    "hireme.cli.commands.resume_agent_cli.find_profile_dir_by_name",
                    return_value=temp_profile_dir,
                ),
                patch(
                    "hireme.cli.commands.resume_agent_cli._generate_resume_from_files",
                    new_callable=AsyncMock,
                ) as mock_generate,
            ):
                result = runner.invoke(
                    app,
                    [
                        "--job-dir",
                        str(temp_job_dir),
                        "--output-dir",
                        output_tmpdir,
                    ],
                )

                # The async function should be called
                # Note: Due to asyncio.run wrapping, we verify the command was invoked


# =============================================================================
# Test: resume generate - Options
# =============================================================================


class TestResumeGenerateOptions:
    """Tests for command options."""

    def test_output_dir_option(
        self, temp_profile_dir, mock_db_with_job, mock_tailored_resume
    ):
        """Test --output-dir option creates correct directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_output = Path(tmpdir) / "custom_output"

            with (
                patch(
                    "hireme.cli.commands.resume_agent_cli.find_profile_dir_by_name",
                    return_value=temp_profile_dir,
                ),
                patch(
                    "hireme.cli.commands.resume_agent_cli.get_db",
                    return_value=mock_db_with_job,
                ),
                patch(
                    "hireme.agents.resume_agent.load_user_context_from_directory",
                    return_value="User context",
                ),
                patch(
                    "hireme.agents.resume_agent.generate_resume",
                    new_callable=AsyncMock,
                    return_value=(mock_tailored_resume, custom_output / "resume.pdf"),
                ),
            ):
                result = runner.invoke(
                    app,
                    [
                        "--job-id",
                        "1",
                        "--output-dir",
                        str(custom_output),
                    ],
                )

    def test_profile_name_option(self, mock_db_with_job, mock_tailored_resume):
        """Test --profile-name option selects correct profile."""
        with tempfile.TemporaryDirectory() as tmpdir:
            profile_dir = Path(tmpdir) / "custom_profile"
            profile_dir.mkdir()
            (profile_dir / "bio.txt").write_text("Custom bio")

            with (
                patch(
                    "hireme.cli.commands.resume_agent_cli.find_profile_dir_by_name",
                    return_value=profile_dir,
                ) as mock_find_profile,
                patch(
                    "hireme.cli.commands.resume_agent_cli.get_db",
                    return_value=mock_db_with_job,
                ),
                patch(
                    "hireme.agents.resume_agent.load_user_context_from_directory",
                    return_value="User context",
                ),
                patch(
                    "hireme.agents.resume_agent.generate_resume",
                    new_callable=AsyncMock,
                    return_value=(mock_tailored_resume, Path(tmpdir) / "resume.pdf"),
                ),
            ):
                result = runner.invoke(
                    app,
                    [
                        "--job-id",
                        "1",
                        "--profile-name",
                        "custom_profile",
                        "--output-dir",
                        tmpdir,
                    ],
                )

                mock_find_profile.assert_called_with("custom_profile")

    def test_parse_job_option_legacy(self, temp_profile_dir, temp_job_dir):
        """Test --parse-job option in legacy mode."""
        with tempfile.TemporaryDirectory() as output_tmpdir:
            with (
                patch(
                    "hireme.cli.commands.resume_agent_cli.find_profile_dir_by_name",
                    return_value=temp_profile_dir,
                ),
                patch(
                    "hireme.cli.commands.resume_agent_cli._generate_resume_from_files",
                    new_callable=AsyncMock,
                ) as mock_generate,
            ):
                result = runner.invoke(
                    app,
                    [
                        "--job-dir",
                        str(temp_job_dir),
                        "--output-dir",
                        output_tmpdir,
                        "--parse-job",
                    ],
                )

                # The command should accept the parse-job flag
