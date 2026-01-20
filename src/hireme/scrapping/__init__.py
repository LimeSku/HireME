"""Custom scrapping module with two main components:
- offers_finder: To find job posting URLs based on search criteria.
- offers_parser: To extract and clean job posting content from URLs.

This module uses Selenium for dynamic content handling and BeautifulSoup for HTML parsing.
"""

from .common import create_driver
from .offers_finder import get_job_urls
from .offers_parser import get_job_page

__all__ = ["get_job_urls", "get_job_page", "create_driver"]
