"""NSF Award Search API scraper — SBIR awards for CA ag companies.

Endpoint: api.nsf.gov/services/v1/awards.json
No auth required. ProgEleCode=5371 = NSF SBIR program.
"""

from __future__ import annotations

import logging

from src.models import Company, Grant, Status
from src.scrapers.base import BaseScraper
from src.taxonomy import classify

logger = logging.getLogger(__name__)

API_URL = "https://api.nsf.gov/services/v1/awards.json"
PAGE_SIZE = 25  # max allowed by NSF API

AG_KEYWORDS = [
    "agriculture", "crop", "farm", "food safety", "soil",
    "irrigation", "livestock", "precision agriculture", "agtech",
    "plant", "seed", "harvest", "pest", "fertilizer",
    "aquaculture", "dairy", "poultry", "vineyard", "orchard",
    "manure", "pollinator", "weed", "horticulture", "biofuel",
    "algae cultivation", "food production", "cultivated meat",
]

PRINT_FIELDS = (
    "id,title,awardeeName,awardeeCity,awardeeStateCode,"
    "piFirstName,piLastName,startDate,expDate,"
    "estimatedTotalAmt,abstractText,fundProgramName"
)


class NSFSBIRScraper(BaseScraper):
    """Scrape NSF SBIR awards for CA agriculture-related companies."""

    name = "nsf_sbir"
    rate_limit_seconds = 0.5
    max_retries = 2

    def scrape(self) -> list[Company]:
        companies: dict[str, Company] = {}
        self._grants: list[Grant] = []

        for keyword in AG_KEYWORDS:
            self._search_keyword(keyword, companies)

        logger.info(f"NSF SBIR: {len(companies)} unique CA companies")
        return list(companies.values())

    def _search_keyword(self, keyword: str, companies: dict[str, Company]):
        offset = 0

        while True:
            params = {
                "ProgEleCode": "5371",
                "awardeeStateCode": "CA",
                "keyword": keyword,
                "rpp": PAGE_SIZE,
                "offset": offset,
                "printFields": PRINT_FIELDS,
            }

            try:
                resp = self.fetch(API_URL, params=params)
            except Exception as e:
                logger.warning(f"NSF search failed for '{keyword}': {e}")
                return

            data = resp.json()
            awards = data.get("response", {}).get("award", [])
            if not awards:
                break

            for award in awards:
                name = award.get("awardeeName", "").strip()
                if not name:
                    continue

                title = award.get("title", "") or ""
                abstract = award.get("abstractText", "") or ""
                combined = f"{title} {abstract}"
                category = classify(combined)

                city = award.get("awardeeCity", "")
                amount_str = award.get("estimatedTotalAmt", "")
                try:
                    amount = float(amount_str) if amount_str else None
                except (ValueError, TypeError):
                    amount = None

                if name not in companies:
                    companies[name] = Company(
                        name=name,
                        category=category,
                        hq_city=city if city else None,
                        hq_state="CA",
                        status=Status.UNKNOWN,
                        description=abstract[:500] if abstract else title[:500],
                        sources=[self.name],
                    )

                pi_first = award.get("piFirstName", "")
                pi_last = award.get("piLastName", "")
                pi_name = f"{pi_first} {pi_last}".strip()

                self._grants.append(Grant(
                    company_id=0,
                    agency="NSF",
                    program=f"SBIR {award.get('fundProgramName', '')}".strip(),
                    title=title[:200],
                    amount_usd=amount,
                    award_date=award.get("startDate"),
                    end_date=award.get("expDate"),
                    abstract=abstract[:500],
                    source=self.name,
                ))

            if len(awards) < PAGE_SIZE:
                break
            offset += PAGE_SIZE

    @property
    def grants(self) -> list[Grant]:
        return getattr(self, "_grants", [])
