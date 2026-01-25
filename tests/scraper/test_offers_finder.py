"""Tests for offers_finder.py - job search functionality."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hireme.scraper.offers_finder import (
    DEFAULT_SOURCES,
    SOURCES,
    SOURCES_ASYNC,
    JobSearchResult,
    _extract_job_card,
    get_job_urls,
    get_job_urls_async,
    search_indeed_async,
    search_jobs,
    search_jobs_async,
    search_wttj_async,
)
from hireme.scraper.playwright_scraper import BrowserManager, get_cache

# =============================================================================
# JobSearchResult Tests
# =============================================================================


class TestJobSearchResult:
    """Tests for JobSearchResult dataclass."""

    def test_required_fields(self):
        """Test that only url is required."""
        result = JobSearchResult(url="https://example.com/job")
        assert result.url == "https://example.com/job"
        assert result.title is None
        assert result.company is None
        assert result.location is None
        assert result.source == ""

    def test_all_fields(self):
        """Test with all fields populated."""
        result = JobSearchResult(
            url="https://example.com/job",
            title="Software Engineer",
            company="TechCorp",
            location="Paris",
            source="indeed",
        )
        assert result.url == "https://example.com/job"
        assert result.title == "Software Engineer"
        assert result.company == "TechCorp"
        assert result.location == "Paris"
        assert result.source == "indeed"


# =============================================================================
# Source Registry Tests
# =============================================================================


class TestSourceRegistry:
    """Tests for source registries."""

    def test_default_sources_exist(self):
        """Test that default sources are defined."""
        assert "indeed" in DEFAULT_SOURCES
        assert "wttj" in DEFAULT_SOURCES

    def test_sync_sources_registered(self):
        """Test that sync sources are registered."""
        assert "indeed" in SOURCES
        assert "wttj" in SOURCES
        assert "linkedin" in SOURCES
        assert "glassdoor" in SOURCES

    def test_async_sources_registered(self):
        """Test that async sources are registered."""
        assert "indeed" in SOURCES_ASYNC
        assert "wttj" in SOURCES_ASYNC
        assert "linkedin" in SOURCES_ASYNC
        assert "glassdoor" in SOURCES_ASYNC

    def test_sync_and_async_have_same_sources(self):
        """Test that sync and async have the same sources."""
        assert set(SOURCES.keys()) == set(SOURCES_ASYNC.keys())


# =============================================================================
# Job Card Extraction Tests
# =============================================================================


class TestExtractJobCard:
    """Tests for _extract_job_card function."""

    async def test_extracts_all_fields(self):
        """Test extraction of all job card fields."""
        # Create mock page with job cards
        page = AsyncMock()

        # Create mock card elements
        mock_link = AsyncMock()
        mock_link.get_attribute = AsyncMock(return_value="https://example.com/job/1")

        mock_title = AsyncMock()
        mock_title.inner_text = AsyncMock(return_value="Software Engineer")

        mock_company = AsyncMock()
        mock_company.inner_text = AsyncMock(return_value="TechCorp")

        mock_location = AsyncMock()
        mock_location.inner_text = AsyncMock(return_value="Paris, France")

        mock_card = AsyncMock()
        mock_card.query_selector = AsyncMock(
            side_effect=lambda sel: {
                "a": mock_link,
                ".title": mock_title,
                ".company": mock_company,
                ".location": mock_location,
            }.get(sel)
        )

        page.query_selector_all = AsyncMock(return_value=[mock_card])

        results = await _extract_job_card(
            page=page,
            card_selector=".job-card",
            link_selector="a",
            title_selector=".title",
            company_selector=".company",
            location_selector=".location",
            source="test",
            max_results=10,
        )

        assert len(results) == 1
        assert results[0].url == "https://example.com/job/1"
        assert results[0].title == "Software Engineer"
        assert results[0].company == "TechCorp"
        assert results[0].location == "Paris, France"
        assert results[0].source == "test"

    async def test_skips_cards_without_url(self):
        """Test that cards without URLs are skipped."""
        page = AsyncMock()

        mock_card = AsyncMock()
        mock_card.query_selector = AsyncMock(return_value=None)  # No link found

        page.query_selector_all = AsyncMock(return_value=[mock_card])

        results = await _extract_job_card(
            page=page,
            card_selector=".job-card",
            link_selector="a",
            title_selector=".title",
            company_selector=".company",
            location_selector=".location",
            source="test",
            max_results=10,
        )

        assert len(results) == 0

    async def test_respects_max_results(self):
        """Test that max_results limit is respected."""
        page = AsyncMock()

        # Create 5 mock cards
        mock_cards = []
        for i in range(5):
            mock_link = AsyncMock()
            mock_link.get_attribute = AsyncMock(
                return_value=f"https://example.com/job/{i}"
            )
            mock_card = AsyncMock()
            mock_card.query_selector = AsyncMock(return_value=mock_link)
            mock_cards.append(mock_card)

        page.query_selector_all = AsyncMock(return_value=mock_cards)

        results = await _extract_job_card(
            page=page,
            card_selector=".job-card",
            link_selector="a",
            title_selector=".title",
            company_selector=".company",
            location_selector=".location",
            source="test",
            max_results=3,
        )

        assert len(results) == 3

    async def test_handles_missing_optional_fields(self):
        """Test that missing optional fields result in None."""
        page = AsyncMock()

        mock_link = AsyncMock()
        mock_link.get_attribute = AsyncMock(return_value="https://example.com/job/1")

        mock_card = AsyncMock()
        mock_card.query_selector = AsyncMock(
            side_effect=lambda sel: mock_link if sel == "a" else None
        )

        page.query_selector_all = AsyncMock(return_value=[mock_card])

        results = await _extract_job_card(
            page=page,
            card_selector=".job-card",
            link_selector="a",
            title_selector=".title",
            company_selector=".company",
            location_selector=".location",
            source="test",
            max_results=10,
        )

        assert len(results) == 1
        assert results[0].url == "https://example.com/job/1"
        assert results[0].title is None
        assert results[0].company is None
        assert results[0].location is None


# =============================================================================
# Search Function Tests
# =============================================================================


class TestSearchIndeedAsync:
    """Tests for search_indeed_async function."""

    @pytest.fixture(autouse=True)
    async def cleanup(self):
        """Close browser after each test."""
        yield
        await BrowserManager.close()

    async def test_builds_correct_url(self):
        """Test that correct Indeed URL is built."""
        with patch.object(BrowserManager, "get_page") as mock_get_page:
            mock_page = AsyncMock()
            mock_page.goto = AsyncMock()
            mock_page.wait_for_selector = AsyncMock()
            mock_page.query_selector_all = AsyncMock(return_value=[])

            mock_cm = AsyncMock()
            mock_cm.__aenter__ = AsyncMock(return_value=mock_page)
            mock_cm.__aexit__ = AsyncMock(return_value=None)
            mock_get_page.return_value = mock_cm

            await search_indeed_async("data analyst", "Paris", max_results=5)

            # Check that goto was called with Indeed URL
            call_args = mock_page.goto.call_args
            url = call_args[0][0]
            assert "fr.indeed.com" in url
            assert "data+analyst" in url or "data%20analyst" in url

    async def test_returns_empty_list_on_timeout(self):
        """Test that empty list is returned on timeout."""
        from playwright.async_api import TimeoutError as PlaywrightTimeout

        with patch.object(BrowserManager, "get_page") as mock_get_page:
            mock_page = AsyncMock()
            mock_page.goto = AsyncMock()
            mock_page.wait_for_selector = AsyncMock(
                side_effect=PlaywrightTimeout("Timeout")
            )

            mock_cm = AsyncMock()
            mock_cm.__aenter__ = AsyncMock(return_value=mock_page)
            mock_cm.__aexit__ = AsyncMock(return_value=None)
            mock_get_page.return_value = mock_cm

            results = await search_indeed_async("query")

            assert results == []


class TestSearchWttjAsync:
    """Tests for search_wttj_async function."""

    @pytest.fixture(autouse=True)
    async def cleanup(self):
        """Close browser after each test."""
        yield
        await BrowserManager.close()

    async def test_builds_correct_url(self):
        """Test that correct WTTJ URL is built."""
        with patch.object(BrowserManager, "get_page") as mock_get_page:
            mock_page = AsyncMock()
            mock_page.goto = AsyncMock()
            mock_page.wait_for_selector = AsyncMock()
            mock_page.query_selector_all = AsyncMock(return_value=[])

            mock_cm = AsyncMock()
            mock_cm.__aenter__ = AsyncMock(return_value=mock_page)
            mock_cm.__aexit__ = AsyncMock(return_value=None)
            mock_get_page.return_value = mock_cm

            await search_wttj_async("développeur python", max_results=5)

            call_args = mock_page.goto.call_args
            url = call_args[0][0]
            assert "welcometothejungle.com" in url
            assert "FR" in url  # France filter


# =============================================================================
# Main Search Function Tests
# =============================================================================


class TestSearchJobsAsync:
    """Tests for search_jobs_async function."""

    @pytest.fixture(autouse=True)
    async def cleanup(self):
        """Close browser after each test."""
        yield
        await BrowserManager.close()

    async def test_uses_default_sources(self):
        """Test that default sources are used when not specified."""
        mock_indeed = AsyncMock(return_value=[])
        mock_wttj = AsyncMock(return_value=[])

        with patch.object(BrowserManager, "initialize", new_callable=AsyncMock):
            with patch.object(BrowserManager, "close", new_callable=AsyncMock):
                with patch.dict(
                    "hireme.scraper.offers_finder.SOURCES_ASYNC",
                    {"indeed": mock_indeed, "wttj": mock_wttj},
                ):
                    await search_jobs_async("query")

                    mock_indeed.assert_called_once()
                    mock_wttj.assert_called_once()

    async def test_combines_results_from_sources(self):
        """Test that results from all sources are combined."""
        mock_indeed = AsyncMock(
            return_value=[
                JobSearchResult(url="https://indeed.com/job1", source="indeed")
            ]
        )
        mock_wttj = AsyncMock(
            return_value=[JobSearchResult(url="https://wttj.com/job1", source="wttj")]
        )

        with patch.object(BrowserManager, "initialize", new_callable=AsyncMock):
            with patch.object(BrowserManager, "close", new_callable=AsyncMock):
                with patch.dict(
                    "hireme.scraper.offers_finder.SOURCES_ASYNC",
                    {"indeed": mock_indeed, "wttj": mock_wttj},
                ):
                    results = await search_jobs_async("query")

                    assert len(results) == 2

    async def test_handles_source_errors(self):
        """Test that errors from individual sources don't break everything."""
        mock_indeed = AsyncMock(side_effect=Exception("Indeed error"))
        mock_wttj = AsyncMock(
            return_value=[JobSearchResult(url="https://wttj.com/job1", source="wttj")]
        )

        with patch.object(BrowserManager, "initialize", new_callable=AsyncMock):
            with patch.object(BrowserManager, "close", new_callable=AsyncMock):
                with patch.dict(
                    "hireme.scraper.offers_finder.SOURCES_ASYNC",
                    {"indeed": mock_indeed, "wttj": mock_wttj},
                ):
                    results = await search_jobs_async("query")

                    # Should still get WTTJ results
                    assert len(results) == 1
                    assert results[0].source == "wttj"

    async def test_ignores_unknown_sources(self):
        """Test that unknown sources are ignored."""
        with patch.object(BrowserManager, "initialize") as mock_init:
            with patch.object(BrowserManager, "close") as mock_close:
                mock_init.return_value = None
                mock_close.return_value = None

                # Try to use an unknown source
                results = await search_jobs_async("query", sources=["unknown_source"])

                assert results == []


# =============================================================================
# URL Deduplication Tests
# =============================================================================


class TestGetJobUrlsAsync:
    """Tests for get_job_urls_async function."""

    @pytest.fixture(autouse=True)
    async def cleanup(self):
        """Close browser after each test."""
        yield
        await BrowserManager.close()

    async def test_deduplicates_urls(self):
        """Test that duplicate URLs are removed."""
        with patch("hireme.scraper.offers_finder.search_jobs_async") as mock_search:
            mock_search.return_value = [
                JobSearchResult(url="https://example.com/job1"),
                JobSearchResult(url="https://example.com/job1"),  # duplicate
                JobSearchResult(url="https://example.com/job2"),
            ]

            urls = await get_job_urls_async("query")

            assert len(urls) == 2
            assert "https://example.com/job1" in urls
            assert "https://example.com/job2" in urls

    async def test_preserves_order(self):
        """Test that URL order is preserved (first occurrence)."""
        with patch("hireme.scraper.offers_finder.search_jobs_async") as mock_search:
            mock_search.return_value = [
                JobSearchResult(url="https://example.com/job1"),
                JobSearchResult(url="https://example.com/job2"),
                JobSearchResult(url="https://example.com/job3"),
            ]

            urls = await get_job_urls_async("query")

            assert urls[0] == "https://example.com/job1"
            assert urls[1] == "https://example.com/job2"
            assert urls[2] == "https://example.com/job3"


# =============================================================================
# Sync Wrapper Tests
# =============================================================================


class TestSyncWrappers:
    """Tests for synchronous wrapper functions."""

    def test_search_jobs_calls_async(self):
        """Test that sync search_jobs calls async version."""
        with patch("hireme.scraper.offers_finder.asyncio.run") as mock_run:
            mock_run.return_value = []

            result = search_jobs("query")

            mock_run.assert_called_once()
            assert result == []

    def test_get_job_urls_calls_async(self):
        """Test that sync get_job_urls calls async version."""
        with patch("hireme.scraper.offers_finder.asyncio.run") as mock_run:
            mock_run.return_value = ["https://example.com/job1"]

            result = get_job_urls("query")

            mock_run.assert_called_once()
            assert result == ["https://example.com/job1"]


# =============================================================================
# Placeholder Source Tests
# =============================================================================


class TestPlaceholderSources:
    """Tests for placeholder source implementations."""

    async def test_linkedin_returns_empty(self):
        """Test that LinkedIn placeholder returns empty list."""
        from hireme.scraper.offers_finder import search_linkedin_async

        results = await search_linkedin_async("query")
        assert results == []

    async def test_glassdoor_returns_empty(self):
        """Test that Glassdoor placeholder returns empty list."""
        from hireme.scraper.offers_finder import search_glassdoor_async

        results = await search_glassdoor_async("query")
        assert results == []
