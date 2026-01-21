"""Multi-source job search scraper.

Searches multiple job boards and returns links to individual job postings.
"""

import asyncio
from dataclasses import dataclass
from urllib.parse import quote_plus

import structlog
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from hireme.scrapping.common import create_driver

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
# Source-specific scrapers
# =============================================================================


def search_indeed(
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
    results = []
    driver = None

    try:
        driver = create_driver(headless=True)

        # Build Indeed search URL
        base_url = "https://fr.indeed.com/jobs"
        search_url = f"{base_url}?q={quote_plus(query)}&l={quote_plus(location)}"

        driver.get(search_url)

        # Wait for job cards to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, ".job_seen_beacon, .jobsearch-ResultsList")
            )
        )

        # Find job cards
        job_cards = driver.find_elements(By.CSS_SELECTOR, ".job_seen_beacon")[
            :max_results
        ]

        for card in job_cards:
            try:
                # Extract job link
                link_elem = card.find_element(By.CSS_SELECTOR, "a[data-jk], h2 a")
                url = link_elem.get_attribute("href")

                # Extract title
                title = None
                try:
                    title_elem = card.find_element(
                        By.CSS_SELECTOR, "h2 span[title], .jobTitle"
                    )
                    title = title_elem.text or title_elem.get_attribute("title")
                except Exception:
                    pass

                # Extract company
                company = None
                try:
                    company_elem = card.find_element(
                        By.CSS_SELECTOR, "[data-testid='company-name'], .companyName"
                    )
                    company = company_elem.text
                except Exception:
                    pass

                # Extract location
                loc = None
                try:
                    loc_elem = card.find_element(
                        By.CSS_SELECTOR,
                        "[data-testid='text-location'], .companyLocation",
                    )
                    loc = loc_elem.text
                except Exception:
                    pass

                if url:
                    results.append(
                        JobSearchResult(
                            url=url,
                            title=title,
                            company=company,
                            location=loc,
                            source="indeed",
                        )
                    )

            except Exception:
                continue

    except TimeoutException as e:
        logger.error("Indeed: Timeout waiting for results", e=e)

    except Exception as e:
        logger.error("Indeed: Error", e=e)
    finally:
        if driver:
            driver.quit()

    return results


def search_wttj(
    query: str,
    location: str = "France",
    max_results: int = 10,
) -> list[JobSearchResult]:
    """Search Welcome to the Jungle for job postings.

    Args:
        query: Search keywords
        location: Job location
        max_results: Maximum number of results to return

    Returns:
        List of job search results
    """
    results = []
    driver = None

    try:
        driver = create_driver(headless=True)

        # Build WTTJ search URL
        base_url = "https://www.welcometothejungle.com/fr/jobs"
        search_url = f"{base_url}?query={quote_plus(query)}&refinementList%5Boffices.country_code%5D%5B%5D=FR"

        driver.get(search_url)

        # Wait for job cards
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (
                    By.CSS_SELECTOR,
                    "[data-testid='search-results-list-item-wrapper'], article",
                )
            )
        )

        # Find job cards
        job_cards = driver.find_elements(
            By.CSS_SELECTOR, "[data-testid='search-results-list-item-wrapper'], article"
        )[:max_results]

        for card in job_cards:
            try:
                # Extract job link
                link_elem = card.find_element(By.CSS_SELECTOR, "a[href*='/jobs/']")
                url = link_elem.get_attribute("href")

                # Extract title
                title = None
                try:
                    title_elem = card.find_element(
                        By.CSS_SELECTOR, "h4, [data-testid='job-title']"
                    )
                    title = title_elem.text
                except Exception:
                    pass

                # Extract company
                company = None
                try:
                    company_elem = card.find_element(
                        By.CSS_SELECTOR, "span[data-testid='company-name'], h3"
                    )
                    company = company_elem.text
                except Exception:
                    pass

                # Extract location
                loc = None
                try:
                    loc_elem = card.find_element(
                        By.CSS_SELECTOR, "[data-testid='job-location'], .location"
                    )
                    loc = loc_elem.text
                except Exception:
                    pass

                if url:
                    results.append(
                        JobSearchResult(
                            url=url,
                            title=title,
                            company=company,
                            location=loc,
                            source="wttj",
                        )
                    )

            except Exception:
                continue

    except TimeoutException:
        print("WTTJ: Timeout waiting for results")
    except Exception as e:
        print(f"WTTJ: Error - {e}")
    finally:
        if driver:
            driver.quit()

    return results


def search_linkedin(
    query: str,
    location: str = "France",
    max_results: int = 10,
) -> list[JobSearchResult]:
    """Search LinkedIn for job postings.

    NOTE: LinkedIn requires authentication for full access.
    This is a placeholder for future implementation.

    TODO: Implement with authentication (cookies/session)

    Args:
        query: Search keywords
        location: Job location
        max_results: Maximum number of results to return

    Returns:
        List of job search results (empty until implemented)
    """
    # Placeholder - requires login to access job listings
    print("LinkedIn: Not implemented (requires authentication)")
    return []


def search_glassdoor(
    query: str,
    location: str = "France",
    max_results: int = 10,
) -> list[JobSearchResult]:
    """Search Glassdoor for job postings.

    NOTE: Glassdoor requires authentication for full access.
    This is a placeholder for future implementation.

    TODO: Implement with authentication (cookies/session)

    Args:
        query: Search keywords
        location: Job location
        max_results: Maximum number of results to return

    Returns:
        List of job search results (empty until implemented)
    """
    # Placeholder - requires login to access job listings
    print("Glassdoor: Not implemented (requires authentication)")
    return []


# =============================================================================
# Source registry
# =============================================================================

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


def search_jobs(
    query: str,
    location: str = "France",
    sources: list[str] | None = None,
    max_results_per_source: int = 10,
) -> list[JobSearchResult]:
    """Search multiple job boards for postings.

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

    all_results = []

    for source in sources:
        if source not in SOURCES:
            print(f"Unknown source: {source}")
            continue

        search_fn = SOURCES[source]
        results: list[JobSearchResult] = search_fn(
            query, location, max_results_per_source
        )
        all_results.extend(results)
        logger.info(f"{source}: Found {len(results)} results")

    return all_results


async def search_jobs_async(
    query: str,
    location: str = "France",
    sources: list[str] | None = None,
    max_results_per_source: int = 10,
) -> list[JobSearchResult]:
    """Search multiple job boards in parallel.

    Args:
        query: Search keywords
        location: Job location
        sources: List of sources to search
        max_results_per_source: Max results per source

    Returns:
        Combined list of job search results
    """
    if sources is None:
        sources = DEFAULT_SOURCES

    loop = asyncio.get_event_loop()

    # Run searches in thread pool
    tasks = []
    for source in sources:
        if source not in SOURCES:
            continue
        search_fn = SOURCES[source]
        task = loop.run_in_executor(
            None,
            search_fn,
            query,
            location,
            max_results_per_source,
        )
        tasks.append(task)

    results_lists = await asyncio.gather(*tasks)

    # Flatten results
    all_results = []
    for results in results_lists:
        all_results.extend(results)

    return all_results


def get_job_urls(
    query: str,
    location: str = "France",
    sources: list[str] | None = None,
    max_results_per_source: int = 10,
) -> list[str]:
    """Convenience function to get just the URLs.

    Args:
        query: Search keywords
        location: Job location
        sources: List of sources to search
        max_results_per_source: Max results per source

    Returns:
        List of job posting URLs
    """
    results = search_jobs(query, location, sources, max_results_per_source)
    return [r.url for r in results]


if __name__ == "__main__":
    # Test search
    print("Searching for: data analyst internship")
    print("=" * 50)

    results = search_jobs(
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
