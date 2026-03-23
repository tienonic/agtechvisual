"""SBIR bulk CSV scraper — downloads the full award dataset and filters locally.

Data source: https://data.www.sbir.gov/awarddatapublic/
File: award_data_no_abstract.csv (~65MB)
No auth required. Contains ALL historical SBIR/STTR awards.
"""

from __future__ import annotations

import csv
import io
import logging
import os
import tempfile
from pathlib import Path

import requests

from src.models import Company, Grant, Status
from src.scrapers.base import BaseScraper
from src.taxonomy import classify

logger = logging.getLogger(__name__)

CSV_URL = "https://data.www.sbir.gov/mod_awarddatapublic_no_abstract/award_data_no_abstract.csv"
CACHE_PATH = Path(__file__).parent.parent.parent / "fixtures" / "sbir_bulk_ca.csv"

AG_AGENCIES = {"USDA"}
AG_KEYWORDS_OTHER = [
    "agriculture", "agricultural", "crop", "farm", "irrigation",
    "livestock", "plant science", "soil", "food safety", "pest",
    "precision ag", "harvest", "seed", "horticulture", "dairy",
    "forestry", "aquaculture", "pollinator", "weed", "fertilizer",
    "grain", "vineyard", "orchard",
]

YEAR_MIN = 2022


class SBIRBulkScraper(BaseScraper):
    """Download the full SBIR CSV, filter to CA ag-related awards."""

    name = "sbir_bulk"
    rate_limit_seconds = 0.0
    timeout = 600  # 10 min for 65MB

    def scrape(self) -> list[Company]:
        rows = self._get_ca_rows()
        companies: dict[str, Company] = {}
        self._grants: list[Grant] = []

        for row in rows:
            firm = row.get("Company", "").strip()
            if not firm:
                continue

            agency = row.get("Agency", "")
            title = row.get("Award Title", "") or ""
            year_str = row.get("Award Year", "") or row.get("Year", "")

            try:
                year = int(year_str)
            except (ValueError, TypeError):
                year = 0

            if year < YEAR_MIN:
                continue

            # For non-USDA agencies, require ag keywords
            if agency not in AG_AGENCIES:
                combined = f"{title} {firm}".lower()
                if not any(kw in combined for kw in AG_KEYWORDS_OTHER):
                    continue

            category = classify(title)
            city = row.get("City", "")
            state = row.get("State", "")
            amount_str = row.get("Award Amount", "").replace(",", "").replace("$", "")
            try:
                amount = float(amount_str) if amount_str else None
            except ValueError:
                amount = None

            if firm not in companies:
                companies[firm] = Company(
                    name=firm,
                    category=category,
                    hq_city=city if city else None,
                    hq_state=state if state else None,
                    status=Status.UNKNOWN,
                    website=row.get("Company Website") or None,
                    description=title[:500],
                    sources=[self.name],
                )

            self._grants.append(Grant(
                company_id=0,
                agency=agency,
                program=f"SBIR {row.get('Phase', '')} {row.get('Program', '')}".strip(),
                title=title[:200],
                amount_usd=amount,
                award_date=row.get("Award Start Date") or row.get("Proposal Award Date"),
                end_date=row.get("Award End Date") or row.get("Contract End Date"),
                source=self.name,
            ))

        logger.info(f"SBIR Bulk: {len(companies)} CA ag-related companies (2022+)")
        return list(companies.values())

    def _get_ca_rows(self) -> list[dict]:
        """Get CA rows from cache or download."""
        if CACHE_PATH.exists():
            logger.info(f"Using cached SBIR data from {CACHE_PATH}")
            return self._read_csv(CACHE_PATH)

        logger.info(f"Downloading SBIR bulk CSV ({CSV_URL})...")
        logger.info("This is ~65MB and may take several minutes...")

        try:
            resp = requests.get(CSV_URL, stream=True, timeout=self.timeout,
                                headers={"User-Agent": "AgTechCAScraper/0.1"})
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"Download failed: {e}")
            logger.info("Retry later on better wifi. The scraper will cache the filtered result.")
            return []

        # Stream to temp file, then filter CA rows to cache
        ca_rows = []
        total_bytes = 0
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".csv", delete=False) as tmp:
            tmp_path = tmp.name
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    tmp.write(chunk)
                    total_bytes += len(chunk)
                    if total_bytes % (10 * 1024 * 1024) < 1024 * 1024:
                        logger.info(f"  Downloaded {total_bytes // (1024*1024)}MB...")

        logger.info(f"Download complete ({total_bytes // (1024*1024)}MB). Filtering CA rows...")

        try:
            with open(tmp_path, encoding="utf-8", errors="replace") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    state = row.get("State", "").strip().upper()
                    if state == "CA" or state == "CALIFORNIA":
                        ca_rows.append(row)
        finally:
            os.unlink(tmp_path)

        # Cache the filtered CA rows
        if ca_rows:
            CACHE_PATH.parent.mkdir(exist_ok=True)
            with open(CACHE_PATH, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=ca_rows[0].keys())
                writer.writeheader()
                writer.writerows(ca_rows)
            logger.info(f"Cached {len(ca_rows)} CA rows to {CACHE_PATH}")

        return ca_rows

    def _read_csv(self, path: Path) -> list[dict]:
        with open(path, encoding="utf-8", errors="replace") as f:
            return list(csv.DictReader(f))

    @property
    def grants(self) -> list[Grant]:
        return getattr(self, "_grants", [])
