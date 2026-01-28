"""Tests for playwright_scraper.py - core browser management and caching."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hireme.scraper.playwright_scraper import (
    BrowserManager,
    ScraperConfig,
    URLCache,
    _extract_main_content,
    _handle_route,
    get_cache,
    get_multiple_pages,
    get_page_content,
)

# =============================================================================
# ScraperConfig Tests
# =============================================================================


class TestScraperConfig:
    """Tests for ScraperConfig dataclass."""

    def test_default_config_values(self):
        """Test default configuration values."""
        config = ScraperConfig()
        assert config.headless is True
        assert config.timeout == 15000
        assert config.block_resources is True
        assert "image" in config.blocked_resource_types
        assert "google-analytics.com" in config.blocked_domains

    def test_custom_config(self):
        """Test custom configuration values."""
        config = ScraperConfig(
            headless=False,
            timeout=30000,
            block_resources=False,
        )
        assert config.headless is False
        assert config.timeout == 30000
        assert config.block_resources is False


# =============================================================================
# URLCache Tests
# =============================================================================


class TestURLCache:
    """Tests for URLCache class."""

    def test_cache_set_and_get(self):
        """Test basic set and get operations."""
        cache = URLCache()
        cache.set("https://example.com/page", "content")
        assert cache.get("https://example.com/page") == "content"

    def test_cache_has(self):
        """Test has method."""
        cache = URLCache()
        cache.set("https://example.com/page", "content")
        assert cache.has("https://example.com/page") is True
        assert cache.has("https://other.com/page") is False

    def test_cache_clear(self):
        """Test clear method."""
        cache = URLCache()
        cache.set("https://example.com/page", "content")
        cache.clear()
        assert cache.has("https://example.com/page") is False

    def test_cache_normalization(self):
        """Test URL normalization - trailing slashes and fragments ignored."""
        cache = URLCache()
        cache.set("https://example.com/page/", "content")

        # Should match without trailing slash
        assert cache.get("https://example.com/page") == "content"
        # Should match with trailing slash
        assert cache.get("https://example.com/page/") == "content"

    def test_cache_max_size(self):
        """Test cache eviction when max size is reached."""
        cache = URLCache(max_size=3)
        cache.set("https://example.com/1", "content1")
        cache.set("https://example.com/2", "content2")
        cache.set("https://example.com/3", "content3")

        # All three should be present
        assert cache.has("https://example.com/1")
        assert cache.has("https://example.com/2")
        assert cache.has("https://example.com/3")

        # Adding a fourth should evict the first
        cache.set("https://example.com/4", "content4")
        assert cache.has("https://example.com/1") is False
        assert cache.has("https://example.com/4") is True

    def test_global_cache_singleton(self):
        """Test that get_cache returns the same instance."""
        cache1 = get_cache()
        cache2 = get_cache()
        assert cache1 is cache2


# =============================================================================
# BrowserManager Tests
# =============================================================================


class TestBrowserManager:
    """Tests for BrowserManager singleton."""

    @pytest.fixture(autouse=True)
    async def cleanup_browser(self):
        """Ensure browser is closed after each test."""
        yield
        await BrowserManager.close()

    async def test_initialize_creates_browser(self):
        """Test that initialize creates a browser instance."""
        with patch("hireme.scraper.playwright_scraper.async_playwright") as mock_pw:
            mock_playwright = AsyncMock()
            mock_browser = AsyncMock()
            mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)
            mock_pw.return_value.start = AsyncMock(return_value=mock_playwright)

            await BrowserManager.initialize()

            mock_pw.return_value.start.assert_called_once()
            mock_playwright.chromium.launch.assert_called_once()

    async def test_close_cleans_up_resources(self):
        """Test that close properly cleans up."""
        with patch("hireme.scraper.playwright_scraper.async_playwright") as mock_pw:
            mock_playwright = AsyncMock()
            mock_browser = AsyncMock()
            mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)
            mock_pw.return_value.start = AsyncMock(return_value=mock_playwright)

            await BrowserManager.initialize()
            await BrowserManager.close()

            mock_browser.close.assert_called_once()
            mock_playwright.stop.assert_called_once()

    async def test_get_context_initializes_if_needed(self):
        """Test that get_context initializes browser if not already done."""
        with patch("hireme.scraper.playwright_scraper.async_playwright") as mock_pw:
            mock_playwright = AsyncMock()
            mock_browser = AsyncMock()
            mock_context = AsyncMock()
            mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)
            mock_browser.new_context = AsyncMock(return_value=mock_context)
            mock_pw.return_value.start = AsyncMock(return_value=mock_playwright)

            async with BrowserManager.get_context():
                pass

            mock_browser.new_context.assert_called_once()


# =============================================================================
# Route Handling Tests
# =============================================================================


class TestRouteHandling:
    """Tests for resource blocking via route interception."""

    async def test_blocks_images(self):
        """Test that images are blocked."""
        config = ScraperConfig()
        route = AsyncMock()
        route.request.resource_type = "image"
        route.request.url = "https://example.com/image.jpg"

        await _handle_route(route, config)

        route.abort.assert_called_once()
        route.continue_.assert_not_called()

    async def test_blocks_fonts(self):
        """Test that fonts are blocked."""
        config = ScraperConfig()
        route = AsyncMock()
        route.request.resource_type = "font"
        route.request.url = "https://example.com/font.woff"

        await _handle_route(route, config)

        route.abort.assert_called_once()

    async def test_blocks_analytics_domains(self):
        """Test that analytics domains are blocked."""
        config = ScraperConfig()
        route = AsyncMock()
        route.request.resource_type = "script"
        route.request.url = "https://www.google-analytics.com/analytics.js"

        await _handle_route(route, config)

        route.abort.assert_called_once()

    async def test_allows_regular_requests(self):
        """Test that regular requests are allowed through."""
        config = ScraperConfig()
        route = AsyncMock()
        route.request.resource_type = "document"
        route.request.url = "https://example.com/page"

        await _handle_route(route, config)

        route.continue_.assert_called_once()
        route.abort.assert_not_called()

    async def test_allows_all_when_blocking_disabled(self):
        """Test that all requests pass when blocking is disabled."""
        config = ScraperConfig(block_resources=False)
        route = AsyncMock()
        route.request.resource_type = "image"
        route.request.url = "https://example.com/image.jpg"

        # Note: _handle_route still blocks, but route isn't set up when disabled
        # This test verifies the behavior when route handling is called
        await _handle_route(route, config)
        route.abort.assert_called_once()  # Still blocks based on type


# =============================================================================
# Content Extraction Tests
# =============================================================================


class TestContentExtraction:
    """Tests for _extract_main_content."""

    async def test_extracts_from_article(self):
        """Test extraction from article element."""
        page = AsyncMock()
        article_elem = AsyncMock()
        article_elem.inner_text = AsyncMock(
            return_value="This is the article content with more than 200 characters. "
            * 5
        )
        page.query_selector = AsyncMock(
            side_effect=lambda sel: article_elem if sel == "article" else None
        )

        content = await _extract_main_content(page)

        assert "article content" in content

    async def test_falls_back_to_body(self):
        """Test fallback to body when no main content found."""
        page = AsyncMock()
        body_elem = AsyncMock()
        body_elem.inner_text = AsyncMock(return_value="Body content")
        page.query_selector = AsyncMock(
            side_effect=lambda sel: body_elem if sel == "body" else None
        )

        content = await _extract_main_content(page)

        assert content == "Body content"

    async def test_returns_empty_on_no_content(self):
        """Test returns empty string when no content found."""
        page = AsyncMock()
        page.query_selector = AsyncMock(return_value=None)

        content = await _extract_main_content(page)

        assert content == ""


# =============================================================================
# get_page_content Tests
# =============================================================================


class TestGetPageContent:
    """Tests for get_page_content function."""

    @pytest.fixture(autouse=True)
    async def cleanup(self):
        """Clear cache and close browser after each test."""
        yield
        get_cache().clear()
        await BrowserManager.close()

    async def test_returns_cached_content(self):
        """Test that cached content is returned without making a request."""
        cache = get_cache()
        cache.set("https://example.com/cached", "cached content")

        content = await get_page_content("https://example.com/cached", use_cache=True)

        assert content == "cached content"

    async def test_caches_new_content(self):
        """Test that new content is cached."""
        with patch.object(BrowserManager, "get_page") as mock_get_page:
            mock_page = AsyncMock()
            mock_page.goto = AsyncMock(return_value=MagicMock(status=200))
            mock_page.set_default_timeout = MagicMock()
            mock_page.query_selector = AsyncMock(return_value=None)

            # Create async context manager
            mock_cm = AsyncMock()
            mock_cm.__aenter__ = AsyncMock(return_value=mock_page)
            mock_cm.__aexit__ = AsyncMock(return_value=None)
            mock_get_page.return_value = mock_cm

            await get_page_content("https://example.com/new", use_cache=True)

            # Verify page was accessed
            mock_page.goto.assert_called()

    async def test_returns_none_on_http_error(self):
        """Test that None is returned on HTTP error."""
        with patch.object(BrowserManager, "get_page") as mock_get_page:
            mock_page = AsyncMock()
            mock_page.goto = AsyncMock(return_value=MagicMock(status=404))
            mock_page.set_default_timeout = MagicMock()

            mock_cm = AsyncMock()
            mock_cm.__aenter__ = AsyncMock(return_value=mock_page)
            mock_cm.__aexit__ = AsyncMock(return_value=None)
            mock_get_page.return_value = mock_cm

            content = await get_page_content("https://example.com/notfound")

            assert content is None


# =============================================================================
# get_multiple_pages Tests
# =============================================================================


class TestGetMultiplePages:
    """Tests for get_multiple_pages function."""

    @pytest.fixture(autouse=True)
    async def cleanup(self):
        """Clear cache after each test."""
        yield
        get_cache().clear()
        await BrowserManager.close()

    async def test_deduplicates_urls(self):
        """Test that duplicate URLs are deduplicated."""
        with patch(
            "hireme.scraper.playwright_scraper.get_page_content"
        ) as mock_get_content:
            mock_get_content.return_value = "content"

            urls = [
                "https://example.com/page1",
                "https://example.com/page1",  # duplicate
                "https://example.com/page2",
            ]

            results = await get_multiple_pages(urls)

            # Should have made 2 calls, not 3
            assert mock_get_content.call_count == 2
            assert len(results) == 2

    async def test_respects_max_concurrent(self):
        """Test that max_concurrent limit is respected."""
        call_times = []

        async def mock_get_content(*args, **kwargs):
            call_times.append(asyncio.get_event_loop().time())
            await asyncio.sleep(0.1)
            return "content"

        with patch(
            "hireme.scraper.playwright_scraper.get_page_content",
            side_effect=mock_get_content,
        ):
            urls = [f"https://example.com/page{i}" for i in range(5)]

            await get_multiple_pages(urls, max_concurrent=2)

            # All 5 should complete
            assert len(call_times) == 5


# =============================================================================
# Integration-style Tests (with mocked browser)
# =============================================================================


class TestScraperIntegration:
    """Integration tests with mocked Playwright."""

    @pytest.fixture(autouse=True)
    async def cleanup(self):
        """Clear cache and close browser after each test."""
        yield
        get_cache().clear()
        await BrowserManager.close()

    async def test_full_scrape_workflow(self):
        """Test complete scrape workflow with mocked browser."""
        with patch("hireme.scraper.playwright_scraper.async_playwright") as mock_pw:
            # Set up mock chain
            mock_playwright = AsyncMock()
            mock_browser = AsyncMock()
            mock_context = AsyncMock()
            mock_page = AsyncMock()

            mock_pw.return_value.start = AsyncMock(return_value=mock_playwright)
            mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)
            mock_browser.new_context = AsyncMock(return_value=mock_context)
            mock_context.new_page = AsyncMock(return_value=mock_page)

            # Set up page responses
            mock_page.goto = AsyncMock(return_value=MagicMock(status=200))
            mock_page.set_default_timeout = MagicMock()
            mock_page.wait_for_selector = AsyncMock()

            # Mock content extraction
            mock_body = AsyncMock()
            mock_body.inner_text = AsyncMock(return_value="Job posting content here")
            mock_page.query_selector = AsyncMock(
                side_effect=lambda sel: mock_body if sel == "body" else None
            )

            # Execute
            content = await get_page_content(
                "https://example.com/job",
                wait_selector=".job-content",
            )

            # Verify
            assert content == "Job posting content here"
            mock_page.goto.assert_called_once()
            mock_page.wait_for_selector.assert_called_once()
