"""Shared test fixtures for CLI tests."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Configure pytest-asyncio
pytest_plugins = ("pytest_asyncio",)


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_console():
    """Create a mock Rich console."""
    return MagicMock()


@pytest.fixture
def sample_job_data():
    """Create sample job data dictionary."""
    return {
        "title": "Python Developer",
        "company": {"name": "TechCorp", "industry": "Technology"},
        "location": "Paris, France",
        "description": "We are looking for a Python developer...",
        "requirements": ["Python", "Django", "PostgreSQL"],
    }


@pytest.fixture
def sample_resume_data():
    """Create sample resume data dictionary."""
    return {
        "name": "John Doe",
        "summary": "Experienced Python developer",
        "experience": [
            {
                "title": "Senior Developer",
                "company": "Previous Corp",
                "duration": "2020-2023",
            }
        ],
        "skills": ["Python", "JavaScript", "SQL"],
    }
