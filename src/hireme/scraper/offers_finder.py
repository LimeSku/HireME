"""Multi-source job search scraper.

Searches multiple job boards and returns links to individual job postings.
Migrated to Playwright for better async support and resource efficiency.
"""

import asyncio
from dataclasses import dataclass
from urllib.parse import quote_plus, urljoin

import structlog
from playwright.async_api import Page
from playwright.async_api import TimeoutError as PlaywrightTimeout

from hireme.scraper.playwright_scraper import BrowserManager

logger = structlog.get_logger(logger_name=__name__)


@dataclass
class JobSearchResult:
    """Single job search result."""

    url: str
    title: str | None = None
    company: str | None = None
    location: str | None = None
    source: str = ""


# =============================================================================
# Source-specific scrapers (async)
# =============================================================================


async def _extract_job_card(
    page: Page,
    card_selector: str,
    link_selector: str,
    title_selector: str,
    company_selector: str,
    location_selector: str,
    source: str,
    max_results: int,
    base_url: str = "",
) -> list[JobSearchResult]:
    """Generic job card extractor for any job board."""
    results = []

    cards = await page.query_selector_all(card_selector)
    for card in cards[:max_results]:
        try:
            # Extract URL
            link = await card.query_selector(link_selector)
            if not link:
                continue
            url = await link.get_attribute("href")
            if not url:
                continue

            # Convert relative URLs to absolute
            if not url.startswith(("http://", "https://")):
                url = urljoin(base_url, url)

            # Extract title
            title = None
            title_elem = await card.query_selector(title_selector)
            if title_elem:
                title = await title_elem.inner_text()

            # Extract company
            company = None
            company_elem = await card.query_selector(company_selector)
            if company_elem:
                company = await company_elem.inner_text()

            # Extract location
            loc = None
            loc_elem = await card.query_selector(location_selector)
            if loc_elem:
                loc = await loc_elem.inner_text()

            results.append(
                JobSearchResult(
                    url=url,
                    title=title,
                    company=company,
                    location=loc,
                    source=source,
                )
            )
        except Exception:
            continue

    return results


async def search_indeed_async(
    query: str,
    location: str = "France",
    max_results: int = 10,
) -> list[JobSearchResult]:
    """Search Indeed France for job postings.

    Args:
        query: Search keywords
        location: Job location
        max_results: Maximum number of results to return

    Returns:
        List of job search results
    """
    base_url = "https://fr.indeed.com/jobs"
    search_url = f"{base_url}?q={quote_plus(query)}&l={quote_plus(location)}"

    try:
        async with BrowserManager.get_page() as page:
            await page.goto(search_url, wait_until="domcontentloaded")

            # Wait for job cards
            await page.wait_for_selector(
                ".job_seen_beacon, .jobsearch-ResultsList", timeout=10000
            )

            results = await _extract_job_card(
                page=page,
                card_selector=".job_seen_beacon",
                link_selector="a[data-jk], h2 a",
                title_selector="h2 span[title], .jobTitle",
                company_selector="[data-testid='company-name'], .companyName",
                location_selector="[data-testid='text-location'], .companyLocation",
                source="indeed",
                max_results=max_results,
                base_url="https://fr.indeed.com",
            )

            logger.info("Indeed search complete", results=len(results))
            return results

    except PlaywrightTimeout:
        logger.error("Indeed: Timeout waiting for results")
        return []
    except Exception as e:
        logger.error("Indeed: Error", error=str(e))
        return []


def search_indeed(
    query: str,
    location: str = "France",
    max_results: int = 10,
) -> list[JobSearchResult]:
    """Sync wrapper for search_indeed_async."""
    return asyncio.run(search_indeed_async(query, location, max_results))


async def search_wttj_async(
    query: str,
    location: str = "France",
    max_results: int = 10,
) -> list[JobSearchResult]:
    """Search Welcome to the Jungle for job postings.

    Args:
        query: Search keywords
        location: Job location (unused, France filter applied)
        max_results: Maximum number of results to return

    Returns:
        List of job search results
    """
    base_url = "https://www.welcometothejungle.com/fr/jobs"
    search_url = f"{base_url}?query={quote_plus(query)}&refinementList%5Boffices.country_code%5D%5B%5D=FR"

    try:
        async with BrowserManager.get_page() as page:
            await page.goto(search_url, wait_until="domcontentloaded")

            # Wait for job cards
            await page.wait_for_selector(
                "[data-testid='search-results-list-item-wrapper'], article",
                timeout=10000,
            )

            results = await _extract_job_card(
                page=page,
                card_selector="[data-testid='search-results-list-item-wrapper'], article",
                link_selector="a[href*='/jobs/']",
                title_selector="h4, [data-testid='job-title']",
                company_selector="span[data-testid='company-name'], h3",
                location_selector="[data-testid='job-location'], .location",
                source="wttj",
                max_results=max_results,
                base_url="https://www.welcometothejungle.com",
            )

            logger.info("WTTJ search complete", results=len(results))
            return results

    except PlaywrightTimeout:
        logger.error("WTTJ: Timeout waiting for results")
        return []
    except Exception as e:
        logger.error("WTTJ: Error", error=str(e))
        return []


def search_wttj(
    query: str,
    location: str = "France",
    max_results: int = 10,
) -> list[JobSearchResult]:
    """Sync wrapper for search_wttj_async."""
    return asyncio.run(search_wttj_async(query, location, max_results))


async def search_linkedin_async(
    query: str,
    location: str = "France",
    max_results: int = 10,
) -> list[JobSearchResult]:
    """Search LinkedIn for job postings.

    NOTE: LinkedIn requires authentication for full access.
    This is a placeholder for future implementation.

    TODO: Implement with authentication (cookies/session)
    """
    logger.warning("LinkedIn: Not implemented (requires authentication)")
    return []


def search_linkedin(
    query: str,
    location: str = "France",
    max_results: int = 10,
) -> list[JobSearchResult]:
    """Sync wrapper for search_linkedin_async."""
    return asyncio.run(search_linkedin_async(query, location, max_results))


async def search_glassdoor_async(
    query: str,
    location: str = "France",
    max_results: int = 10,
) -> list[JobSearchResult]:
    """Search Glassdoor for job postings.

    NOTE: Glassdoor requires authentication for full access.
    This is a placeholder for future implementation.

    TODO: Implement with authentication (cookies/session)
    """
    logger.warning("Glassdoor: Not implemented (requires authentication)")
    return []


def search_glassdoor(
    query: str,
    location: str = "France",
    max_results: int = 10,
) -> list[JobSearchResult]:
    """Sync wrapper for search_glassdoor_async."""
    return asyncio.run(search_glassdoor_async(query, location, max_results))


# =============================================================================
# Source registry
# =============================================================================

# Async source functions
SOURCES_ASYNC = {
    "indeed": search_indeed_async,
    "wttj": search_wttj_async,
    "linkedin": search_linkedin_async,
    "glassdoor": search_glassdoor_async,
}

# Sync source functions (for backwards compatibility)
SOURCES = {
    "indeed": search_indeed,
    "wttj": search_wttj,
    "linkedin": search_linkedin,
    "glassdoor": search_glassdoor,
}

DEFAULT_SOURCES = ["indeed", "wttj"]


# =============================================================================
# Main search functions
# =============================================================================


async def search_jobs_async(
    query: str,
    location: str = "France",
    sources: list[str] | None = None,
    max_results_per_source: int = 10,
) -> list[JobSearchResult]:
    """Search multiple job boards in parallel using shared browser.

    This is the preferred method - uses native async with a single
    browser instance for all sources.

    Args:
        query: Search keywords (e.g., "data analyst internship")
        location: Job location (default: "France")
        sources: List of sources to search (default: ["indeed", "wttj"])
        max_results_per_source: Max results per source (default: 10)

    Returns:
        Combined list of job search results from all sources
    """
    if sources is None:
        sources = DEFAULT_SOURCES

    # Initialize browser once for all searches
    await BrowserManager.initialize()

    try:
        # Run all searches in parallel (sharing browser)
        tasks = []
        valid_sources = []
        for source in sources:
            if source not in SOURCES_ASYNC:
                logger.warning("Unknown source", source=source)
                continue
            search_fn = SOURCES_ASYNC[source]
            tasks.append(search_fn(query, location, max_results_per_source))
            valid_sources.append(source)

        results_lists = await asyncio.gather(*tasks, return_exceptions=True)

        # Flatten results, handling any errors
        all_results: list[JobSearchResult] = []
        for i, results in enumerate(results_lists):
            if isinstance(results, BaseException):
                logger.error(
                    "Search failed", source=valid_sources[i], error=str(results)
                )
                continue
            all_results.extend(results)
            logger.info(
                "Search complete", source=valid_sources[i], results=len(results)
            )

        return all_results

    finally:
        # Clean up browser
        await BrowserManager.close()


def search_jobs(
    query: str,
    location: str = "France",
    sources: list[str] | None = None,
    max_results_per_source: int = 10,
) -> list[JobSearchResult]:
    """Search multiple job boards for postings (sync wrapper).

    For better performance, prefer using search_jobs_async directly.

    Args:
        query: Search keywords (e.g., "data analyst internship")
        location: Job location (default: "France")
        sources: List of sources to search (default: ["indeed", "wttj"])
        max_results_per_source: Max results per source (default: 10)

    Returns:
        Combined list of job search results from all sources
    """
    return asyncio.run(
        search_jobs_async(query, location, sources, max_results_per_source)
    )


async def get_job_urls_async(
    query: str,
    location: str = "France",
    sources: list[str] | None = None,
    max_results_per_source: int = 10,
) -> list[str]:
    """Convenience function to get just the URLs (async).

    Args:
        query: Search keywords
        location: Job location
        sources: List of sources to search
        max_results_per_source: Max results per source

    Returns:
        List of job posting URLs
    """
    results = await search_jobs_async(query, location, sources, max_results_per_source)
    # Deduplicate URLs
    seen = set()
    unique_urls = []
    for r in results:
        if r.url not in seen:
            seen.add(r.url)
            unique_urls.append(r.url)
    return unique_urls


def get_job_urls(
    query: str,
    location: str = "France",
    sources: list[str] | None = None,
    max_results_per_source: int = 10,
) -> list[str]:
    """Convenience function to get just the URLs (sync wrapper).

    Args:
        query: Search keywords
        location: Job location
        sources: List of sources to search
        max_results_per_source: Max results per source

    Returns:
        List of job posting URLs (deduplicated)
    """
    return asyncio.run(
        get_job_urls_async(query, location, sources, max_results_per_source)
    )


if __name__ == "__main__":
    import asyncio

    async def main():
        print("Searching for: data analyst internship")
        print("=" * 50)

        results = await search_jobs_async(
            query="data analyst stage",
            location="France",
            sources=["indeed", "wttj"],
            max_results_per_source=5,
        )

        print(f"\nTotal: {len(results)} results")
        print("=" * 50)

        for r in results:
            print(f"\n[{r.source}] {r.title}")
            print(f"  Company: {r.company}")
            print(f"  Location: {r.location}")
            print(f"  URL: {r.url}")

    asyncio.run(main())
