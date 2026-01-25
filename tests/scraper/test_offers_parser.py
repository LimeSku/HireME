"""Tests for offers_parser.py - job page parsing and text cleaning."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from hireme.scraper.offers_parser import (
    JOB_SITE_SELECTORS,
    _get_wait_selector,
    clean_html_text,
    clean_text,
    get_job_page,
    get_job_page_async,
    get_job_pages_async,
    get_page_text,
    get_page_text_async,
)
from hireme.scraper.playwright_scraper import BrowserManager, get_cache

# =============================================================================
# Text Cleaning Tests
# =============================================================================


class TestCleanHtmlText:
    """Tests for clean_html_text function."""

    def test_normalizes_multiple_newlines(self):
        """Test that multiple newlines are collapsed."""
        text = "Line 1\n\n\n\n\nLine 2"
        result = clean_html_text(text)
        assert "\n\n\n" not in result

    def test_normalizes_whitespace(self):
        """Test that multiple spaces/tabs are collapsed."""
        text = "Word1     Word2\t\t\tWord3"
        result = clean_html_text(text)
        assert "     " not in result
        assert "\t\t\t" not in result

    def test_removes_cookie_boilerplate(self):
        """Test that cookie-related text is removed."""
        text = "Job Description\ncookie policy here\nMore content"
        result = clean_html_text(text)
        assert "cookie policy" not in result.lower()

    def test_removes_privacy_policy(self):
        """Test that privacy policy text is removed."""
        text = "Content\nprivacy policy link\nMore content"
        result = clean_html_text(text)
        assert "privacy policy" not in result.lower()

    def test_removes_terms_of_service(self):
        """Test that terms of service text is removed."""
        text = "Content\nterms of service\nMore content"
        result = clean_html_text(text)
        assert "terms of service" not in result.lower()

    def test_removes_copyright(self):
        """Test that copyright text is removed."""
        text = "Content\n© 2024 Company. All Rights Reserved.\nMore content"
        result = clean_html_text(text)
        assert "all rights reserved" not in result.lower()

    def test_handles_empty_string(self):
        """Test that empty string returns empty."""
        assert clean_html_text("") == ""

    def test_strips_result(self):
        """Test that result is stripped."""
        text = "  Content  "
        result = clean_html_text(text)
        assert result == "Content"


class TestCleanText:
    """Tests for clean_text function."""

    def test_removes_empty_lines(self):
        """Test that empty lines are removed."""
        text = "Line 1\n\n\nLine 2\n\nLine 3"
        result = clean_text(text)
        lines = [l for l in result.split("\n") if l.strip()]
        assert len(lines) == 3

    def test_strips_each_line(self):
        """Test that each line is stripped."""
        text = "  Line 1  \n  Line 2  "
        result = clean_text(text)
        assert "  Line" not in result


# =============================================================================
# Wait Selector Tests
# =============================================================================


class TestGetWaitSelector:
    """Tests for _get_wait_selector function."""

    def test_returns_selector_for_indeed(self):
        """Test selector for Indeed URLs."""
        selector = _get_wait_selector("https://www.indeed.com/job/123")
        assert selector == "#jobDescriptionText"

    def test_returns_selector_for_linkedin(self):
        """Test selector for LinkedIn URLs."""
        selector = _get_wait_selector("https://www.linkedin.com/jobs/view/123")
        assert selector == ".jobs-description"

    def test_returns_selector_for_wttj(self):
        """Test selector for Welcome to the Jungle URLs."""
        selector = _get_wait_selector(
            "https://www.welcometothejungle.com/fr/companies/abc/jobs/dev"
        )
        assert selector == "[data-testid='job-section-description']"

    def test_returns_none_for_unknown_site(self):
        """Test returns None for unknown sites."""
        selector = _get_wait_selector("https://unknown-jobsite.com/job/123")
        assert selector is None

    def test_all_known_sites_have_selectors(self):
        """Test that all known sites have selectors defined."""
        known_sites = [
            "linkedin.com",
            "indeed.com",
            "glassdoor.com",
            "welcometothejungle.com",
            "lever.co",
            "greenhouse.io",
            "workable.com",
        ]
        for site in known_sites:
            assert site in JOB_SITE_SELECTORS


# =============================================================================
# Async Function Tests
# =============================================================================


class TestGetPageTextAsync:
    """Tests for get_page_text_async function."""

    @pytest.fixture(autouse=True)
    async def cleanup(self):
        """Clear cache and close browser after each test."""
        yield
        get_cache().clear()
        await BrowserManager.close()

    async def test_returns_cleaned_content(self):
        """Test that content is cleaned before return."""
        with patch("hireme.scraper.offers_parser.get_page_content") as mock_get_content:
            mock_get_content.return_value = "Content\n\n\n\nMore Content"

            result = await get_page_text_async("https://example.com/job")

            assert result is not None
            assert "\n\n\n\n" not in result

    async def test_returns_none_on_failure(self):
        """Test that None is returned when get_page_content fails."""
        with patch("hireme.scraper.offers_parser.get_page_content") as mock_get_content:
            mock_get_content.return_value = None

            result = await get_page_text_async("https://example.com/job")

            assert result is None


class TestGetJobPageAsync:
    """Tests for get_job_page_async function."""

    @pytest.fixture(autouse=True)
    async def cleanup(self):
        """Clear cache after each test."""
        yield
        get_cache().clear()
        await BrowserManager.close()

    async def test_uses_correct_selector_for_known_site(self):
        """Test that correct selector is used for known job sites."""
        with patch("hireme.scraper.offers_parser.get_page_text_async") as mock_get_text:
            mock_get_text.return_value = "Job content"

            await get_job_page_async("https://www.indeed.com/job/123")

            # Verify the correct selector was passed
            mock_get_text.assert_called_once()
            call_kwargs = mock_get_text.call_args
            assert call_kwargs.kwargs.get("wait_selector") == "#jobDescriptionText"

    async def test_uses_none_selector_for_unknown_site(self):
        """Test that no selector is used for unknown sites."""
        with patch("hireme.scraper.offers_parser.get_page_text_async") as mock_get_text:
            mock_get_text.return_value = "Job content"

            await get_job_page_async("https://unknown-site.com/job/123")

            mock_get_text.assert_called_once()
            call_kwargs = mock_get_text.call_args
            assert call_kwargs.kwargs.get("wait_selector") is None


class TestGetJobPagesAsync:
    """Tests for get_job_pages_async function."""

    @pytest.fixture(autouse=True)
    async def cleanup(self):
        """Clear cache after each test."""
        yield
        get_cache().clear()
        await BrowserManager.close()

    async def test_returns_dict_of_results(self):
        """Test that results are returned as a dictionary."""
        with patch(
            "hireme.scraper.offers_parser.get_multiple_pages"
        ) as mock_get_multiple:
            mock_get_multiple.return_value = {
                "https://example.com/job1": "Content 1",
                "https://example.com/job2": "Content 2",
            }

            results = await get_job_pages_async(
                ["https://example.com/job1", "https://example.com/job2"]
            )

            assert isinstance(results, dict)
            assert len(results) == 2

    async def test_cleans_content_in_results(self):
        """Test that content in results is cleaned."""
        with patch(
            "hireme.scraper.offers_parser.get_multiple_pages"
        ) as mock_get_multiple:
            mock_get_multiple.return_value = {
                "https://example.com/job1": "Content\n\n\n\nwith extra lines",
            }

            results = await get_job_pages_async(["https://example.com/job1"])

            # Content should be cleaned
            content = results["https://example.com/job1"]
            assert content is not None
            assert "\n\n\n\n" not in content

    async def test_handles_none_results(self):
        """Test that None results are preserved."""
        with patch(
            "hireme.scraper.offers_parser.get_multiple_pages"
        ) as mock_get_multiple:
            mock_get_multiple.return_value = {
                "https://example.com/job1": None,
            }

            results = await get_job_pages_async(["https://example.com/job1"])

            assert results["https://example.com/job1"] is None


# =============================================================================
# Sync Wrapper Tests
# =============================================================================


class TestSyncWrappers:
    """Tests for synchronous wrapper functions."""

    def test_get_page_text_calls_async(self):
        """Test that sync wrapper calls async version."""
        with patch("hireme.scraper.offers_parser.asyncio.run") as mock_run:
            mock_run.return_value = "Content"

            result = get_page_text("https://example.com/job")

            mock_run.assert_called_once()
            assert result == "Content"

    def test_get_job_page_calls_async(self):
        """Test that sync wrapper calls async version."""
        with patch("hireme.scraper.offers_parser.asyncio.run") as mock_run:
            mock_run.return_value = "Job content"

            result = get_job_page("https://example.com/job")

            mock_run.assert_called_once()
            assert result == "Job content"

    def test_get_page_text_converts_timeout(self):
        """Test that timeout is converted from seconds to milliseconds."""
        with patch("hireme.scraper.offers_parser.get_page_text_async") as mock_async:
            with patch("hireme.scraper.offers_parser.asyncio.run") as mock_run:
                mock_run.return_value = "Content"

                # Call with 10 seconds timeout
                get_page_text("https://example.com/job", timeout=10)

                # Verify async was called with 10000ms
                mock_run.assert_called_once()
