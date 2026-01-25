"""Playwright-based browser automation for job scraping.

Provides optimized browser management with:
- Shared browser instance (reused across scrapes)
- Isolated browser contexts (clean state per operation)
- Resource blocking (skip images, fonts, analytics)
- Built-in request caching
- Native async support
"""

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import AsyncGenerator
from urllib.parse import urlparse

import structlog
from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    Route,
    async_playwright,
)

logger = structlog.get_logger(logger_name=__name__)


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class ScraperConfig:
    """Configuration for the Playwright scraper."""

    headless: bool = True
    timeout: int = 15000  # ms
    block_resources: bool = True
    blocked_resource_types: tuple[str, ...] = (
        "image",
        "media",
        "font",
        "stylesheet",
    )
    blocked_domains: tuple[str, ...] = (
        "google-analytics.com",
        "googletagmanager.com",
        "facebook.com",
        "doubleclick.net",
        "ads.",
        "tracking.",
        "analytics.",
    )
    user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )


DEFAULT_CONFIG = ScraperConfig()


# =============================================================================
# URL Cache for deduplication
# =============================================================================


@dataclass
class URLCache:
    """Simple in-memory cache for scraped content."""

    _cache: dict[str, str] = field(default_factory=dict)
    max_size: int = 100

    def get(self, url: str) -> str | None:
        """Get cached content for URL."""
        return self._cache.get(self._normalize_url(url))

    def set(self, url: str, content: str) -> None:
        """Cache content for URL."""
        if len(self._cache) >= self.max_size:
            # Remove oldest entry (simple FIFO)
            oldest = next(iter(self._cache))
            del self._cache[oldest]
        self._cache[self._normalize_url(url)] = content

    def has(self, url: str) -> bool:
        """Check if URL is cached."""
        return self._normalize_url(url) in self._cache

    def clear(self) -> None:
        """Clear the cache."""
        self._cache.clear()

    @staticmethod
    def _normalize_url(url: str) -> str:
        """Normalize URL for cache key."""
        parsed = urlparse(url)
        # Remove trailing slashes and fragments
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"


# Global cache instance
_url_cache = URLCache()


def get_cache() -> URLCache:
    """Get the global URL cache."""
    return _url_cache


# =============================================================================
# Browser Manager (Singleton pattern)
# =============================================================================


class BrowserManager:
    """Manages a shared browser instance for efficient resource usage.

    Usage:
        async with BrowserManager.get_context() as context:
            page = await context.new_page()
            await page.goto(url)
    """

    _instance: "BrowserManager | None" = None
    _playwright: Playwright | None = None
    _browser: Browser | None = None
    _lock: asyncio.Lock = asyncio.Lock()
    _config: ScraperConfig = DEFAULT_CONFIG

    def __new__(cls) -> "BrowserManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    async def initialize(cls, config: ScraperConfig | None = None) -> None:
        """Initialize the browser manager with configuration."""
        async with cls._lock:
            if config:
                cls._config = config
            if cls._browser is None:
                cls._playwright = await async_playwright().start()
                cls._browser = await cls._playwright.chromium.launch(
                    headless=cls._config.headless,
                    args=[
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-blink-features=AutomationControlled",
                    ],
                )
                logger.info("Browser initialized", headless=cls._config.headless)

    @classmethod
    async def close(cls) -> None:
        """Close the browser and cleanup resources."""
        async with cls._lock:
            if cls._browser:
                await cls._browser.close()
                cls._browser = None
            if cls._playwright:
                await cls._playwright.stop()
                cls._playwright = None
            cls._instance = None
            logger.info("Browser closed")

    @classmethod
    @asynccontextmanager
    async def get_context(
        cls, config: ScraperConfig | None = None
    ) -> AsyncGenerator[BrowserContext, None]:
        """Get an isolated browser context.

        Each context has its own cookies, cache, and storage.
        Automatically cleaned up when done.
        """
        cfg = config or cls._config

        # Ensure browser is initialized
        if cls._browser is None:
            await cls.initialize(config)

        assert cls._browser is not None

        context = await cls._browser.new_context(
            user_agent=cfg.user_agent,
            viewport={"width": 1920, "height": 1080},
            java_script_enabled=True,
        )

        # Set up resource blocking if enabled
        if cfg.block_resources:
            await context.route("**/*", lambda route: _handle_route(route, cfg))

        try:
            yield context
        finally:
            await context.close()

    @classmethod
    @asynccontextmanager
    async def get_page(
        cls, config: ScraperConfig | None = None
    ) -> AsyncGenerator[Page, None]:
        """Convenience method to get a page directly."""
        async with cls.get_context(config) as context:
            page = await context.new_page()
            yield page


async def _handle_route(route: Route, config: ScraperConfig) -> None:
    """Handle route interception for resource blocking."""
    request = route.request

    # Block by resource type
    if request.resource_type in config.blocked_resource_types:
        await route.abort()
        return

    # Block by domain
    url = request.url
    for blocked in config.blocked_domains:
        if blocked in url:
            await route.abort()
            return

    await route.continue_()


# =============================================================================
# High-level scraping functions
# =============================================================================


async def get_page_content(
    url: str,
    wait_selector: str | None = None,
    timeout: int = 15000,
    use_cache: bool = True,
    config: ScraperConfig | None = None,
) -> str | None:
    """Fetch and extract text content from a page.

    Args:
        url: URL to scrape
        wait_selector: CSS selector to wait for before extracting
        timeout: Timeout in milliseconds
        use_cache: Whether to use/update the URL cache
        config: Optional scraper configuration

    Returns:
        Extracted text content or None if failed
    """
    # Check cache first
    cache = get_cache()
    if use_cache and cache.has(url):
        logger.debug("Cache hit", url=url)
        return cache.get(url)

    try:
        async with BrowserManager.get_page(config) as page:
            page.set_default_timeout(timeout)

            # Navigate to URL
            response = await page.goto(url, wait_until="domcontentloaded")

            if not response or response.status >= 400:
                logger.error(
                    "Failed to load page",
                    url=url,
                    status=response.status if response else None,
                )
                return None

            # Wait for specific element if provided
            if wait_selector:
                try:
                    await page.wait_for_selector(wait_selector, timeout=timeout)
                except Exception:
                    logger.warning(
                        "Selector not found, continuing", selector=wait_selector
                    )

            # Extract text from main content areas
            content = await _extract_main_content(page)

            # Cache the result
            if use_cache and content:
                cache.set(url, content)

            return content

    except Exception as e:
        logger.error("Failed to scrape page", url=url, error=str(e))
        return None


async def _extract_main_content(page: Page) -> str:
    """Extract main content from page, trying common selectors."""
    content_selectors = [
        "article",
        "[role='main']",
        ".job-description",
        ".job-details",
        ".job-posting",
        "#job-content",
        "main",
    ]

    for selector in content_selectors:
        try:
            element = await page.query_selector(selector)
            if element:
                text = await element.inner_text()
                if len(text) > 200:
                    return text
        except Exception:
            continue

    # Fallback to body
    body = await page.query_selector("body")
    if body:
        return await body.inner_text()

    return ""


async def get_multiple_pages(
    urls: list[str],
    wait_selector: str | None = None,
    timeout: int = 15000,
    max_concurrent: int = 3,
    use_cache: bool = True,
) -> dict[str, str | None]:
    """Fetch multiple pages concurrently with rate limiting.

    Args:
        urls: List of URLs to scrape
        wait_selector: CSS selector to wait for
        timeout: Timeout per page in milliseconds
        max_concurrent: Maximum concurrent requests
        use_cache: Whether to use URL cache

    Returns:
        Dictionary mapping URLs to their content
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    results: dict[str, str | None] = {}

    async def fetch_one(url: str) -> None:
        async with semaphore:
            results[url] = await get_page_content(
                url, wait_selector, timeout, use_cache
            )

    # Deduplicate URLs
    unique_urls = list(set(urls))
    logger.info(
        "Fetching pages",
        total=len(urls),
        unique=len(unique_urls),
        cached=sum(1 for u in unique_urls if get_cache().has(u)),
    )

    await asyncio.gather(*[fetch_one(url) for url in unique_urls])

    return results


# =============================================================================
# Sync wrappers for backwards compatibility
# =============================================================================


def get_page_content_sync(
    url: str,
    wait_selector: str | None = None,
    timeout: int = 15000,
    use_cache: bool = True,
) -> str | None:
    """Synchronous wrapper for get_page_content."""
    return asyncio.run(get_page_content(url, wait_selector, timeout, use_cache))


def get_multiple_pages_sync(
    urls: list[str],
    wait_selector: str | None = None,
    timeout: int = 15000,
    max_concurrent: int = 3,
    use_cache: bool = True,
) -> dict[str, str | None]:
    """Synchronous wrapper for get_multiple_pages."""
    return asyncio.run(
        get_multiple_pages(urls, wait_selector, timeout, max_concurrent, use_cache)
    )


# =============================================================================
# Cleanup helper
# =============================================================================


async def cleanup() -> None:
    """Clean up browser resources. Call when done scraping."""
    await BrowserManager.close()
    get_cache().clear()
