"""Shared test fixtures for scraper tests."""

from unittest.mock import AsyncMock, MagicMock

import pytest

# Configure pytest-asyncio
pytest_plugins = ("pytest_asyncio",)


@pytest.fixture
def mock_page():
    """Create a mock Playwright page."""
    page = AsyncMock()
    page.goto = AsyncMock(return_value=MagicMock(status=200))
    page.wait_for_selector = AsyncMock()
    page.query_selector = AsyncMock()
    page.query_selector_all = AsyncMock(return_value=[])
    page.set_default_timeout = MagicMock()
    return page


@pytest.fixture
def mock_context():
    """Create a mock browser context."""
    context = AsyncMock()
    context.new_page = AsyncMock()
    context.route = AsyncMock()
    context.close = AsyncMock()
    return context


@pytest.fixture
def mock_browser():
    """Create a mock browser."""
    browser = AsyncMock()
    browser.new_context = AsyncMock()
    browser.close = AsyncMock()
    return browser


@pytest.fixture
def sample_html_content():
    """Sample HTML content for testing."""
    return """
    <html>
    <head><title>Test Job Posting</title></head>
    <body>
        <article>
            <h1>Software Engineer</h1>
            <div class="company">TechCorp</div>
            <div class="location">Paris, France</div>
            <div class="job-description">
                We are looking for a talented software engineer to join our team.
                Requirements:
                - Python experience
                - Django framework
                - PostgreSQL
            </div>
        </article>
    </body>
    </html>
    """


@pytest.fixture
def sample_job_cards():
    """Sample job card elements for testing."""

    async def create_mock_card(url, title, company, location):
        card = AsyncMock()
        link = AsyncMock()
        link.get_attribute = AsyncMock(return_value=url)
        card.query_selector = AsyncMock(
            side_effect=lambda sel: {
                "a[data-jk], h2 a": link,
                "h2 span[title], .jobTitle": AsyncMock(
                    inner_text=AsyncMock(return_value=title)
                ),
                "[data-testid='company-name'], .companyName": AsyncMock(
                    inner_text=AsyncMock(return_value=company)
                ),
                "[data-testid='text-location'], .companyLocation": AsyncMock(
                    inner_text=AsyncMock(return_value=location)
                ),
            }.get(sel)
        )
        return card

    return create_mock_card
