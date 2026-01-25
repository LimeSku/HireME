"""Playwright-based scraper for job offer pages.

Handles JavaScript-rendered pages with efficient resource management.
Migrated from Selenium for better async support and performance.
"""

import asyncio
import re

import structlog

from hireme.scraper.playwright_scraper import (
    BrowserManager,
    get_cache,
    get_multiple_pages,
    get_page_content,
)

logger = structlog.get_logger(logger_name=__name__)


def clean_html_text(text: str) -> str:
    """Clean and compress HTML-extracted text."""
    if not text:
        return ""

    # Normalize whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)

    # Remove common boilerplate
    boilerplate = [
        r"(?i)cookie[s]? (policy|settings|preferences).*?\n",
        r"(?i)accept (all )?cookies.*?\n",
        r"(?i)privacy policy.*?\n",
        r"(?i)terms (of|and) (service|use|conditions).*?\n",
        r"(?i)©.*?all rights reserved.*?\n",
        r"(?i)follow us on.*?\n",
        r"(?i)share (this|on).*?\n",
        r"(?i)subscribe to.*?\n",
        r"(?i)sign up for.*?newsletter.*?\n",
        r"(?i)navigation|menu|footer|header|sidebar.*?\n",
    ]

    for pattern in boilerplate:
        text = re.sub(pattern, "", text)

    return text.strip()


async def get_page_text_async(
    url: str, wait_selector: str | None = None, timeout: int = 15000
) -> str | None:
    """Download and extract text from a web page using Playwright.

    Args:
        url: URL to scrape
        wait_selector: CSS selector to wait for before extracting (optional)
        timeout: Max milliseconds to wait for page load

    Returns:
        Cleaned text content or None if failed
    """
    content = await get_page_content(url, wait_selector, timeout, use_cache=True)
    if content:
        return clean_text(content)
    return None


def get_page_text(
    url: str, wait_selector: str | None = None, timeout: int = 10
) -> str | None:
    """Sync wrapper for get_page_text_async.

    Args:
        url: URL to scrape
        wait_selector: CSS selector to wait for before extracting (optional)
        timeout: Max seconds to wait for page load (converted to ms)

    Returns:
        Cleaned text content or None if failed
    """
    return asyncio.run(get_page_text_async(url, wait_selector, timeout * 1000))


def clean_text(text: str) -> str:
    """Clean extracted text content.

    Args:
        text: Raw text from page

    Returns:
        Cleaned text with normalized whitespace
    """
    lines = text.splitlines()

    # Remove empty lines and normalize whitespace
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped:
            cleaned_lines.append(stripped)

    result: str = "\n".join(cleaned_lines)
    result = clean_html_text(result)
    logger.debug(
        "Extracted text (preview) after cleaning HTML",
        length=len(result),
        preview=result[-500:],
    )

    return result


# Common selectors for known job sites
JOB_SITE_SELECTORS = {
    "linkedin.com": ".jobs-description",
    "indeed.com": "#jobDescriptionText",
    "glassdoor.com": ".jobDescriptionContent",
    "welcometothejungle.com": "[data-testid='job-section-description']",
    "lever.co": ".posting-page",
    "greenhouse.io": "#content",
    "workable.com": "[data-ui='job-description']",
}


def _get_wait_selector(url: str) -> str | None:
    """Get the appropriate wait selector for a known job site."""
    for domain, selector in JOB_SITE_SELECTORS.items():
        if domain in url:
            return selector
    return None


async def get_job_page_async(url: str) -> str | None:
    """Scrape a job posting page (async).

    Uses caching to avoid redundant requests.

    Args:
        url: Job posting URL

    Returns:
        Extracted text or None
    """
    wait_selector = _get_wait_selector(url)
    return await get_page_text_async(url, wait_selector=wait_selector)


def get_job_page(url: str) -> str | None:
    """Convenience function to scrape a job posting page (sync).

    Tries common job site patterns for waiting.
    Uses caching to avoid redundant requests.

    Args:
        url: Job posting URL

    Returns:
        Extracted text or None
    """
    return asyncio.run(get_job_page_async(url))


async def get_job_pages_async(urls: list[str]) -> dict[str, str | None]:
    """Scrape multiple job posting pages efficiently.

    Uses shared browser and concurrent requests with rate limiting.

    Args:
        urls: List of job posting URLs

    Returns:
        Dictionary mapping URLs to their content
    """
    await BrowserManager.initialize()
    try:
        results = await get_multiple_pages(
            urls,
            max_concurrent=3,
            use_cache=True,
        )
        # Clean all results
        return {
            url: clean_text(content) if content else None
            for url, content in results.items()
        }
    finally:
        await BrowserManager.close()


def get_job_pages(urls: list[str]) -> dict[str, str | None]:
    """Sync wrapper for get_job_pages_async."""
    return asyncio.run(get_job_pages_async(urls))


if __name__ == "__main__":
    import asyncio

    async def main():
        test_url = input("Enter job posting URL: ").strip()
        if test_url:
            result_job = await get_job_page_async(test_url)
            if result_job:
                print("\n" + "=" * 50)
                print(result_job)
                print("=" * 50)
            else:
                print("Failed to extract content")

    asyncio.run(main())
