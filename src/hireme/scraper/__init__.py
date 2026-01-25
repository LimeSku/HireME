"""Custom scraping module with two main components:
- offers_finder: To find job posting URLs based on search criteria.
- offers_parser: To extract and clean job posting content from URLs.

Migrated from Selenium to Playwright for:
- Native async support
- Shared browser instance (reduced overhead)
- Built-in resource blocking
- URL caching to avoid duplicate requests
"""

# Legacy sync imports (backwards compatible)
# New async imports (preferred)
from .offers_finder import (
    JobSearchResult,
    get_job_urls,
    get_job_urls_async,
    search_jobs,
    search_jobs_async,
)
from .offers_parser import (
    get_job_page,
    get_job_page_async,
    get_job_pages_async,
    get_page_text,
    get_page_text_async,
)

# Playwright utilities
from .playwright_scraper import (
    BrowserManager,
    ScraperConfig,
    cleanup,
    get_cache,
)

__all__ = [
    # Sync API (backwards compatible)
    "get_job_urls",
    "get_job_page",
    "get_page_text",
    "search_jobs",
    "JobSearchResult",
    # Async API (preferred)
    "get_job_urls_async",
    "get_job_page_async",
    "get_job_pages_async",
    "get_page_text_async",
    "search_jobs_async",
    # Utilities
    "BrowserManager",
    "ScraperConfig",
    "get_cache",
    "cleanup",
]
