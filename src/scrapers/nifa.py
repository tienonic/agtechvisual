"""NIFA Recent Awards scraper — paginated JSON endpoint.

Endpoint: portal.nifa.usda.gov/lmd4/recent_awards/get_data.js
Page size: 30 (server-enforced)
CA records: ~2,821
"""

from __future__ import annotations

import json
import logging
import urllib.parse

from src.models import Company, Grant, Status
from src.scrapers.base import BaseScraper
from src.taxonomy import classify

logger = logging.getLogger(__name__)

BASE_URL = "https://portal.nifa.usda.gov/lmd4/recent_awards/get_data.js"
PAGE_SIZE = 1000
MAX_PAGES = 10  # safety cap — 2821 CA rows / 1000 = 3 pages

UNIVERSITY_INDICATORS = [
    "university", "college", "regents", "board of trustees",
    "state of", "county of", "department of", "community college",
    "school district", "saes", "extension service",
    "experiment station", "institute of technology",
    "polytechnic", "cooperative extension",
]


def _strip_html(value: str) -> str:
    """Strip HTML div wrappers from NIFA API cell values."""
    if not value:
        return ""
    from bs4 import BeautifulSoup
    if "<" in value:
        return BeautifulSoup(value, "html.parser").get_text(strip=True)
    return value.strip()


def _is_educational_or_gov(name: str) -> bool:
    lower = name.lower()
    return any(ind in lower for ind in UNIVERSITY_INDICATORS)


class NIFAScraper(BaseScraper):
    name = "nifa"
    rate_limit_seconds = 0.5
    timeout = 30

    def scrape(self) -> list[Company]:
        companies: dict[str, Company] = {}
        self._grants: list[Grant] = []

        filters = json.dumps({"State Name": "CALIFORNIA"})
        encoded_filters = urllib.parse.quote(filters)

        for page in range(1, MAX_PAGES + 1):
            url = f"{BASE_URL}?perPage={PAGE_SIZE}&page={page}&columnFilters={encoded_filters}"

            try:
                resp = self.fetch(url)
            except Exception as e:
                logger.error(f"NIFA page {page} failed: {e}")
                break

            try:
                data = resp.json()
            except Exception:
                # Sometimes returns JS wrapper — try extracting JSON
                text = resp.text.strip()
                if text.startswith("[") or text.startswith("{"):
                    data = json.loads(text)
                else:
                    logger.warning(f"NIFA page {page}: non-JSON response")
                    break

            # Handle both array and object responses
            rows = data if isinstance(data, list) else data.get("data", data.get("rows", []))
            if not rows:
                logger.info(f"NIFA: no more data at page {page}")
                break

            for row in rows:
                # Row can be dict or list
                if isinstance(row, dict):
                    grantee = _strip_html(row.get("Grantee Name", ""))
                    title = _strip_html(row.get("Grant Title", ""))
                    program = _strip_html(row.get("Program Name", "") or "")
                    program_area = _strip_html(row.get("Program Area Name", "") or "")
                    amount_str = _strip_html(str(row.get("Award Dollars", ""))).replace(",", "").replace("$", "").strip()
                    award_date = _strip_html(row.get("Award Date", ""))
                elif isinstance(row, list) and len(row) >= 6:
                    award_date = _strip_html(row[0]) if len(row) > 0 else ""
                    grantee = _strip_html(row[5]) if len(row) > 5 else ""
                    title = _strip_html(row[3]) if len(row) > 3 else ""
                    amount_str = _strip_html(str(row[6])).replace(",", "").replace("$", "").strip() if len(row) > 6 else ""
                    program = _strip_html(row[7]) if len(row) > 7 else ""
                    program_area = _strip_html(row[8]) if len(row) > 8 else ""
                else:
                    continue

                if not grantee or _is_educational_or_gov(grantee):
                    continue

                category = classify(f"{title} {program} {program_area}")
                try:
                    amount = float(amount_str) if amount_str else None
                except ValueError:
                    amount = None

                if grantee not in companies:
                    companies[grantee] = Company(
                        name=grantee,
                        category=category,
                        hq_state="CA",
                        status=Status.UNKNOWN,
                        description=title[:500],
                        sources=[self.name],
                    )

                self._grants.append(Grant(
                    company_id=0,
                    agency="USDA",
                    program=f"NIFA {program}".strip(),
                    title=title[:200],
                    amount_usd=amount,
                    award_date=award_date,
                    source=self.name,
                ))

            if len(rows) < PAGE_SIZE:
                logger.info(f"NIFA: last page at {page} ({len(rows)} rows)")
                break

            if page % 10 == 0:
                logger.info(f"NIFA page {page}: {len(companies)} unique companies so far")

        logger.info(f"NIFA: {len(companies)} private CA companies found")
        return list(companies.values())

    @property
    def grants(self) -> list[Grant]:
        return getattr(self, "_grants", [])
