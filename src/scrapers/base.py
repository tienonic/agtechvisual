"""Base scraper with retry logic and rate limiting."""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod

import requests

from src.models import Company

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Abstract base class for all scrapers."""

    name: str = "base"
    rate_limit_seconds: float = 1.0
    max_retries: int = 3
    timeout: int = 30

    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()
        self.session.headers.setdefault(
            "User-Agent",
            "AgTechCAScraper/0.1 (research project; contact@example.com)",
        )
        self._last_request_time = 0.0

    def _rate_limit(self):
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit_seconds:
            time.sleep(self.rate_limit_seconds - elapsed)
        self._last_request_time = time.time()

    def fetch(self, url: str, method: str = "GET", **kwargs) -> requests.Response:
        """Make an HTTP request with retry and rate limiting."""
        self._rate_limit()
        kwargs.setdefault("timeout", self.timeout)

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.request(method, url, **kwargs)
                if response.status_code == 429:
                    if attempt == self.max_retries:
                        logger.error(f"Rate limited after {self.max_retries} attempts: {url}")
                        raise requests.HTTPError(f"429 Too Many Requests: {url}", response=response)
                    wait = min(2 ** attempt, 30)
                    logger.warning(f"Rate limited on {url}, waiting {wait}s")
                    time.sleep(wait)
                    continue
                response.raise_for_status()
                return response
            except requests.RequestException as e:
                if attempt == self.max_retries:
                    logger.error(f"Failed after {self.max_retries} attempts: {url} - {e}")
                    raise
                wait = min(2 ** attempt, 30)
                logger.warning(f"Attempt {attempt} failed for {url}: {e}, retrying in {wait}s")
                time.sleep(wait)

    @abstractmethod
    def scrape(self) -> list[Company]:
        """Scrape and return a list of companies."""
        ...
