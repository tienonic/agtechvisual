"""SEC EDGAR Full Text Search scraper for Form D filings."""

from __future__ import annotations

import logging

from src.models import Company, FundingRound, Status
from src.scrapers.base import BaseScraper
from src.taxonomy import classify

logger = logging.getLogger(__name__)

EFTS_URL = "https://efts.sec.gov/LATEST/search-index"

SEARCH_TERMS = [
    '"agriculture technology"',
    '"precision agriculture"',
    '"agtech"',
    '"farm management software"',
    '"crop technology"',
    '"agricultural robotics"',
    '"irrigation technology"',
    '"food safety technology"',
    '"agricultural drone"',
    '"vertical farming"',
    '"crop sensor"',
    '"livestock technology"',
    '"food tech"',
    '"foodtech"',
    '"agri-tech"',
    '"ag tech"',
    '"agricultural biotechnology"',
    '"agricultural AI"',
    '"farm software"',
    '"crop monitoring"',
    '"biostimulant"',
    '"indoor farming"',
    '"controlled environment agriculture"',
    '"plant breeding"',
]


class SECEdgarScraper(BaseScraper):
    name = "sec_edgar"
    rate_limit_seconds = 2.0
    max_retries = 2

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.session.headers["User-Agent"] = (
            "AgTechCAScraper/0.1 (research; agtech-ca-research@example.com)"
        )
        self.session.headers["Accept"] = "application/json"

    def scrape(self) -> list[Company]:
        companies: dict[str, Company] = {}
        self._funding_rounds: list[FundingRound] = []

        for term in SEARCH_TERMS:
            self._search_term(term, companies)

        return list(companies.values())

    def _search_term(self, query: str, companies: dict[str, Company]):
        params = {
            "q": query,
            "forms": "D",
            "dateRange": "custom",
            "startdt": "2022-01-01",
            "enddt": "2026-12-31",
        }

        try:
            resp = self.fetch(EFTS_URL, params=params)
        except Exception as e:
            logger.warning(f"EDGAR search failed for {query}: {e}")
            return

        data = resp.json()
        hits = data.get("hits", {}).get("hits", [])

        for hit in hits:
            source = hit.get("_source", {})
            entity_name = source.get("entity_name", "").strip()
            if not entity_name:
                names = source.get("display_names", [])
                entity_name = names[0] if names else ""

            if not entity_name:
                continue

            file_date = source.get("file_date", "")
            form_type = source.get("form_type", "")
            state = source.get("state_of_inc", "")

            description = f"SEC Form D filing: {query}"
            category = classify(query)

            if entity_name not in companies:
                companies[entity_name] = Company(
                    name=entity_name,
                    category=category,
                    state_of_incorporation=state,
                    status=Status.UNKNOWN,
                    description=description,
                    sources=[self.name],
                )

            self._funding_rounds.append(FundingRound(
                company_id=0,
                round_type="form_d",
                date=file_date,
                source=self.name,
            ))

        logger.info(f"EDGAR {query}: {len(hits)} hits, {len(companies)} total companies")

    @property
    def funding_rounds(self) -> list[FundingRound]:
        return getattr(self, "_funding_rounds", [])
