"""Selenium-based scraper for job offer pages.

Handles JavaScript-rendered pages that requests-based scrapers can't handle.
"""

import re

import structlog
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from hireme.scrapping.common import create_driver

logger = structlog.get_logger()


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


def get_page_text(
    url: str, wait_selector: str | None = None, timeout: int = 10
) -> str | None:
    """Download and extract text from a web page using Selenium.

    Args:
        url: URL to scrape
        wait_selector: CSS selector to wait for before extracting (optional)
        timeout: Max seconds to wait for page load

    Returns:
        Cleaned text content or None if failed
    """
    driver = None
    try:
        driver = create_driver(headless=True)
        driver.get(url)

        # Wait for specific element if provided
        if wait_selector:
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, wait_selector))
            )
        else:
            # Wait for body to be present
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )

        # Get main content - try common job posting containers first
        content_selectors = [
            "article",
            "[role='main']",
            ".job-description",
            ".job-details",
            ".job-posting",
            "#job-content",
            "main",
            "body",
        ]

        text = ""
        for selector in content_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    text = elements[0].text
                    if len(text) > 200:  # Found meaningful content
                        break
            except Exception:
                continue

        # Fallback to body
        if not text or len(text) < 200:
            text = driver.find_element(By.TAG_NAME, "body").text

        # Clean the text
        cleaned = clean_text(text)
        return cleaned

    except TimeoutException:
        logger.error(f"Timeout loading page: {url}")
        return None
    except WebDriverException as e:
        logger.error(f"WebDriver error: {e}")
        return None
    finally:
        if driver:
            driver.quit()


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


def get_job_page(url: str) -> str | None:
    """Convenience function to scrape a job posting page.

    Tries common job site patterns for waiting.

    Args:
        url: Job posting URL

    Returns:
        Extracted text or None
    """
    # Common selectors for job sites
    wait_selectors = {
        "linkedin.com": ".jobs-description",
        "indeed.com": "#jobDescriptionText",
        "glassdoor.com": ".jobDescriptionContent",
        "welcometothejungle.com": "[data-testid='job-section-description']",
        "lever.co": ".posting-page",
        "greenhouse.io": "#content",
        "workable.com": "[data-ui='job-description']",
    }

    # Find matching selector for known sites
    wait_selector = None
    for domain, selector in wait_selectors.items():
        if domain in url:
            wait_selector = selector
            break

    return get_page_text(url, wait_selector=wait_selector)


if __name__ == "__main__":
    # Test with a sample URL
    test_url = input("Enter job posting URL: ").strip()
    if test_url:
        result_job = get_job_page(test_url)
        if result_job:
            print("\n" + "=" * 50)
            print(result_job)
            print("=" * 50)
        else:
            print("Failed to extract content")
