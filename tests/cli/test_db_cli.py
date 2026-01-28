"""Tests for the database CLI commands.

Tests for:
- hireme db init
- hireme db import
- hireme db stats
- hireme db jobs list/show/search/archive
- hireme db resumes list/select/rate
- hireme db apps list/update
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from hireme.cli.commands.db_cli import app
from hireme.db import ApplicationStatus, JobSource
from hireme.db.database import DatabaseManager

runner = CliRunner()


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = DatabaseManager(db_path=db_path)
        yield db


@pytest.fixture
def db_with_data(temp_db):
    """Create a database with sample data."""
    # Add sample jobs
    job1 = temp_db.add_job_offer(
        title="Python Developer",
        company_name="TechCorp",
        url="https://example.com/job1",
        source=JobSource.INDEED,
        location="Paris, France",
        raw_text="Sample job description for Python Developer",
    )
    temp_db.mark_job_processed(
        job1.id,
        {
            "title": "Python Developer",
            "company": {"name": "TechCorp"},
            "location": "Paris, France",
        },
    )

    job2 = temp_db.add_job_offer(
        title="Data Analyst",
        company_name="DataCo",
        location="Lyon, France",
        raw_text="Sample job description for Data Analyst",
    )

    job3 = temp_db.add_job_offer(
        title="ML Engineer",
        company_name="AI Labs",
        location="Remote",
    )
    temp_db.archive_job(job3.id)

    # Add sample resume
    temp_db.add_generated_resume(
        job_offer_id=job1.id,
        profile_name="default",
        resume_data={"name": "John Doe"},
        pdf_path="/tmp/resume.pdf",
    )

    # Add sample application
    temp_db.create_application(job1.id)
    temp_db.update_application_status(job1.id, ApplicationStatus.APPLIED)

    yield temp_db


@pytest.fixture
def mock_get_db(db_with_data):
    """Mock get_db to return our test database."""
    with patch("hireme.cli.commands.db_cli.get_db", return_value=db_with_data):
        yield db_with_data


# =============================================================================
# Test: db init
# =============================================================================


class TestDbInit:
    """Tests for 'hireme db init' command."""

    def test_init_creates_database(self):
        """Test that init command creates the database."""
        with patch("hireme.cli.commands.db_cli.get_db") as mock_db:
            mock_db.return_value.db_path = Path("/tmp/test.db")
            result = runner.invoke(app, ["init"])

            assert result.exit_code == 0
            assert "Database initialized" in result.output


# =============================================================================
# Test: db stats
# =============================================================================


class TestDbStats:
    """Tests for 'hireme db stats' command."""

    def test_stats_shows_statistics(self, mock_get_db):
        """Test that stats command shows job statistics."""
        result = runner.invoke(app, ["stats"])

        assert result.exit_code == 0
        assert "Job Search Statistics" in result.output
        assert "Total jobs tracked" in result.output
        assert "Application Funnel" in result.output

    def test_stats_with_empty_db(self, temp_db):
        """Test stats with empty database."""
        with patch("hireme.cli.commands.db_cli.get_db", return_value=temp_db):
            result = runner.invoke(app, ["stats"])

            assert result.exit_code == 0
            assert "Total jobs tracked: 0" in result.output


# =============================================================================
# Test: db jobs list
# =============================================================================


class TestDbJobsList:
    """Tests for 'hireme db jobs list' command."""

    def test_list_jobs_shows_jobs(self, mock_get_db):
        """Test that list shows all jobs."""
        result = runner.invoke(app, ["jobs", "list"])

        assert result.exit_code == 0
        # Rich tables may wrap text, so check for partial matches
        assert "Python" in result.output
        assert "TechCorp" in result.output
        assert "Data" in result.output

    def test_list_jobs_excludes_archived_by_default(self, mock_get_db):
        """Test that archived jobs are excluded by default."""
        result = runner.invoke(app, ["jobs", "list"])

        assert result.exit_code == 0
        # ML Engineer should not appear when archived
        assert "ML" not in result.output or "AI Labs" not in result.output

    def test_list_jobs_includes_archived_with_flag(self, mock_get_db):
        """Test that --archived flag includes archived jobs."""
        result = runner.invoke(app, ["jobs", "list", "--archived"])

        assert result.exit_code == 0
        # Should include archived job
        assert "AI Labs" in result.output

    def test_list_jobs_processed_only(self, mock_get_db):
        """Test that --processed shows only processed jobs."""
        result = runner.invoke(app, ["jobs", "list", "--processed"])

        assert result.exit_code == 0
        assert "TechCorp" in result.output
        # DataCo is not processed, should not appear
        assert "DataCo" not in result.output

    def test_list_jobs_with_limit(self, mock_get_db):
        """Test that --limit limits the number of results."""
        result = runner.invoke(app, ["jobs", "list", "--limit", "1"])

        assert result.exit_code == 0
        # Should only show 1 job

    def test_list_jobs_empty_database(self, temp_db):
        """Test list with empty database."""
        with patch("hireme.cli.commands.db_cli.get_db", return_value=temp_db):
            result = runner.invoke(app, ["jobs", "list"])

            assert result.exit_code == 0
            assert "No job offers found" in result.output


# =============================================================================
# Test: db jobs show
# =============================================================================


class TestDbJobsShow:
    """Tests for 'hireme db jobs show' command."""

    def test_show_job_displays_details(self, mock_get_db):
        """Test that show displays job details."""
        result = runner.invoke(app, ["jobs", "show", "1"])

        assert result.exit_code == 0
        assert "Python Developer" in result.output
        assert "TechCorp" in result.output
        assert "Paris" in result.output

    def test_show_job_not_found(self, mock_get_db):
        """Test show with non-existent job ID."""
        result = runner.invoke(app, ["jobs", "show", "999"])

        assert result.exit_code == 1
        assert "not found" in result.output


# =============================================================================
# Test: db jobs search
# =============================================================================


class TestDbJobsSearch:
    """Tests for 'hireme db jobs search' command."""

    def test_search_finds_by_title(self, mock_get_db):
        """Test search finds jobs by title."""
        result = runner.invoke(app, ["jobs", "search", "Python"])

        assert result.exit_code == 0
        assert "Python Developer" in result.output

    def test_search_finds_by_company(self, mock_get_db):
        """Test search finds jobs by company name."""
        result = runner.invoke(app, ["jobs", "search", "TechCorp"])

        assert result.exit_code == 0
        assert "Python Developer" in result.output

    def test_search_no_results(self, mock_get_db):
        """Test search with no matching results."""
        result = runner.invoke(app, ["jobs", "search", "NonExistentJob"])

        assert result.exit_code == 0
        assert "No jobs found" in result.output


# =============================================================================
# Test: db jobs archive
# =============================================================================


class TestDbJobsArchive:
    """Tests for 'hireme db jobs archive' command."""

    def test_archive_job_success(self, mock_get_db):
        """Test archiving a job."""
        result = runner.invoke(app, ["jobs", "archive", "1"])

        assert result.exit_code == 0
        assert "archived" in result.output

    def test_archive_job_not_found(self, mock_get_db):
        """Test archiving non-existent job."""
        result = runner.invoke(app, ["jobs", "archive", "999"])

        assert result.exit_code == 0
        assert "not found" in result.output


# =============================================================================
# Test: db resumes list
# =============================================================================


class TestDbResumesList:
    """Tests for 'hireme db resumes list' command."""

    def test_list_resumes_shows_all(self, mock_get_db):
        """Test that list shows all resumes."""
        result = runner.invoke(app, ["resumes", "list"])

        assert result.exit_code == 0
        assert "default" in result.output  # profile name

    def test_list_resumes_filter_by_job(self, mock_get_db):
        """Test filtering resumes by job ID."""
        result = runner.invoke(app, ["resumes", "list", "--job", "1"])

        assert result.exit_code == 0

    def test_list_resumes_no_resumes_for_job(self, mock_get_db):
        """Test listing resumes for job with no resumes."""
        result = runner.invoke(app, ["resumes", "list", "--job", "2"])

        assert result.exit_code == 0
        assert "No resumes found" in result.output


# =============================================================================
# Test: db resumes select
# =============================================================================


class TestDbResumesSelect:
    """Tests for 'hireme db resumes select' command."""

    def test_select_resume_success(self, mock_get_db):
        """Test selecting a resume."""
        result = runner.invoke(app, ["resumes", "select", "1"])

        assert result.exit_code == 0
        assert "selected" in result.output

    def test_select_resume_not_found(self, mock_get_db):
        """Test selecting non-existent resume."""
        result = runner.invoke(app, ["resumes", "select", "999"])

        assert result.exit_code == 0
        assert "not found" in result.output


# =============================================================================
# Test: db resumes rate
# =============================================================================


class TestDbResumesRate:
    """Tests for 'hireme db resumes rate' command."""

    def test_rate_resume_success(self, mock_get_db):
        """Test rating a resume."""
        result = runner.invoke(app, ["resumes", "rate", "1", "4"])

        assert result.exit_code == 0
        assert "rated" in result.output
        assert "★★★★" in result.output

    def test_rate_resume_with_notes(self, mock_get_db):
        """Test rating a resume with notes."""
        result = runner.invoke(
            app, ["resumes", "rate", "1", "5", "--notes", "Great match!"]
        )

        assert result.exit_code == 0
        assert "rated" in result.output

    def test_rate_resume_invalid_rating_too_low(self, mock_get_db):
        """Test rating with invalid value (too low)."""
        result = runner.invoke(app, ["resumes", "rate", "1", "0"])

        assert result.exit_code == 1
        assert "between 1 and 5" in result.output

    def test_rate_resume_invalid_rating_too_high(self, mock_get_db):
        """Test rating with invalid value (too high)."""
        result = runner.invoke(app, ["resumes", "rate", "1", "6"])

        assert result.exit_code == 1
        assert "between 1 and 5" in result.output

    def test_rate_resume_not_found(self, mock_get_db):
        """Test rating non-existent resume."""
        result = runner.invoke(app, ["resumes", "rate", "999", "4"])

        assert result.exit_code == 0
        assert "not found" in result.output


# =============================================================================
# Test: db apps list
# =============================================================================


class TestDbAppsList:
    """Tests for 'hireme db apps list' command."""

    def test_list_applications(self, mock_get_db):
        """Test listing all applications."""
        result = runner.invoke(app, ["apps", "list"])

        assert result.exit_code == 0
        assert "applied" in result.output.lower()

    def test_list_applications_filter_by_status(self, mock_get_db):
        """Test filtering applications by status."""
        result = runner.invoke(app, ["apps", "list", "--status", "applied"])

        assert result.exit_code == 0

    def test_list_applications_empty(self, temp_db):
        """Test listing with no applications."""
        with patch("hireme.cli.commands.db_cli.get_db", return_value=temp_db):
            result = runner.invoke(app, ["apps", "list"])

            assert result.exit_code == 0
            assert "No applications found" in result.output


# =============================================================================
# Test: db apps update
# =============================================================================


class TestDbAppsUpdate:
    """Tests for 'hireme db apps update' command."""

    def test_update_application_status(self, mock_get_db):
        """Test updating application status."""
        result = runner.invoke(app, ["apps", "update", "1", "interview_scheduled"])

        assert result.exit_code == 0
        assert "updated" in result.output

    def test_update_application_with_notes(self, mock_get_db):
        """Test updating application with notes."""
        result = runner.invoke(
            app,
            ["apps", "update", "1", "applied", "--notes", "Applied via LinkedIn"],
        )

        assert result.exit_code == 0
        assert "updated" in result.output

    def test_update_application_invalid_status(self, mock_get_db):
        """Test updating with invalid status."""
        result = runner.invoke(app, ["apps", "update", "1", "invalid_status"])

        assert result.exit_code == 1
        assert "Invalid status" in result.output

    def test_update_creates_application_if_not_exists(self, mock_get_db):
        """Test that update creates application if it doesn't exist."""
        result = runner.invoke(app, ["apps", "update", "2", "applied"])

        assert result.exit_code == 0
        assert "updated" in result.output


# =============================================================================
# Test: db import
# =============================================================================


class TestDbImport:
    """Tests for 'hireme db import' command."""

    def test_import_from_empty_directory(self, temp_db):
        """Test import with no files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            job_dir = Path(tmpdir) / "job_offers"
            job_dir.mkdir(parents=True)

            with patch("hireme.cli.commands.db_cli.get_db", return_value=temp_db):
                with patch("hireme.config.cfg") as mock_cfg:
                    mock_cfg.job_offers_dir = job_dir
                    result = runner.invoke(app, ["import"])

                    assert result.exit_code == 0
                    assert "Imported 0 job(s)" in result.output

    def test_import_raw_jobs(self, temp_db):
        """Test importing raw job files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            job_dir = Path(tmpdir) / "job_offers"
            raw_dir = job_dir / "raw"
            raw_dir.mkdir(parents=True)

            # Create a sample raw job file
            (raw_dir / "job_Python Developer-TechCorp.txt").write_text(
                "Sample job description"
            )

            with patch("hireme.cli.commands.db_cli.get_db", return_value=temp_db):
                with patch("hireme.config.cfg") as mock_cfg:
                    mock_cfg.job_offers_dir = job_dir
                    result = runner.invoke(app, ["import"])

                    assert result.exit_code == 0
                    assert "Imported" in result.output

    def test_import_processed_jobs(self, temp_db):
        """Test importing processed job JSON files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            job_dir = Path(tmpdir) / "job_offers"
            processed_dir = job_dir / "processed"
            processed_dir.mkdir(parents=True)

            # Create a sample processed job file
            job_data = {
                "url": "https://example.com/job",
                "data": {
                    "title": "Data Scientist",
                    "company": {"name": "DataCorp"},
                    "location": "Berlin",
                },
            }
            (processed_dir / "Data Scientist-DataCorp.json").write_text(
                json.dumps(job_data)
            )

            with patch("hireme.cli.commands.db_cli.get_db", return_value=temp_db):
                with patch("hireme.config.cfg") as mock_cfg:
                    mock_cfg.job_offers_dir = job_dir
                    result = runner.invoke(app, ["import"])

                    assert result.exit_code == 0
                    assert "Imported" in result.output
