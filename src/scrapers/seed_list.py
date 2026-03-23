"""Seed list scraper — loads known agtech companies from CSV."""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from src.models import Category, Company, Status
from src.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

CSV_PATH = Path(__file__).parent.parent.parent / "fixtures" / "known_ca_agtech.csv"


class SeedListScraper(BaseScraper):
    """Load curated list of known agtech companies from CSV."""

    name = "seed_list"
    rate_limit_seconds = 0.0

    def scrape(self) -> list[Company]:
        if not CSV_PATH.exists():
            logger.error(f"Seed list not found: {CSV_PATH}")
            return []

        companies = []
        with open(CSV_PATH, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get("name", "").strip()
                if not name:
                    continue

                cat_str = row.get("category", "UNKNOWN")
                try:
                    category = Category(cat_str)
                except ValueError:
                    category = Category.UNKNOWN

                companies.append(Company(
                    name=name,
                    category=category,
                    hq_city=row.get("hq_city") or None,
                    hq_state=row.get("hq_state") or None,
                    country="US" if row.get("hq_state") else None,
                    status=Status.UNKNOWN,
                    website=row.get("website") or None,
                    description=row.get("description") or None,
                    sources=[self.name],
                ))

        logger.info(f"Seed list: {len(companies)} companies loaded")
        return companies
