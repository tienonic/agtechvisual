"""THRIVE Agrifood scrapers — WP REST API.

The WordPress REST API at /wp-json/wp/v2/alumni is fully open.
No auth, no Cloudflare on JSON endpoints. 279+ companies.
"""

from __future__ import annotations

import logging

from src.models import Company, Status
from src.scrapers.base import BaseScraper
from src.taxonomy import classify

logger = logging.getLogger(__name__)

API_BASE = "https://thriveagrifood.com/wp-json/wp/v2"

# Taxonomy term IDs for category-company
CATEGORY_ALL_ALUMNI = 187
CATEGORY_TOP50_AGTECH = 189
CATEGORY_TOP50_FOODTECH = 188

# Location taxonomy IDs
LOCATION_US = 11

SKIP_NAMES = {
    "thrive", "svg ventures", "agrifood", "top 50", "logo",
    "thrive agrifood", "menu", "search", "close",
}


def _is_valid_company_name(name: str) -> bool:
    if not name or len(name) < 2 or len(name) > 80:
        return False
    if name.lower() in SKIP_NAMES:
        return False
    return True


class ThriveTop50Scraper(BaseScraper):
    """Scrape Thrive Top 50 AgTech + FoodTech via WP REST API."""

    name = "thrive_top50"
    rate_limit_seconds = 0.5

    def scrape(self) -> list[Company]:
        companies: dict[str, Company] = {}
        tech_map = self._fetch_taxonomy("technology")
        location_map = self._fetch_taxonomy("locations")

        # Fetch Top 50 AgTech (all years) + Top 50 FoodTech
        for cat_id in [CATEGORY_TOP50_AGTECH, CATEGORY_TOP50_FOODTECH]:
            self._fetch_alumni(companies, cat_id, tech_map, location_map)

        return list(companies.values())

    def _fetch_taxonomy(self, taxonomy: str) -> dict[int, str]:
        """Fetch taxonomy terms and return id->name mapping."""
        term_map = {}
        page = 1
        while True:
            try:
                resp = self.fetch(
                    f"{API_BASE}/{taxonomy}",
                    params={"per_page": 100, "page": page},
                )
                terms = resp.json()
                if not terms:
                    break
                for t in terms:
                    term_map[t["id"]] = t["name"]
                if len(terms) < 100:
                    break
                page += 1
            except Exception as e:
                logger.warning(f"Failed to fetch {taxonomy}: {e}")
                break
        return term_map

    def _fetch_alumni(
        self,
        companies: dict[str, Company],
        category_id: int,
        tech_map: dict[int, str],
        location_map: dict[int, str],
    ):
        page = 1
        while True:
            params = {
                "per_page": 100,
                "page": page,
                "category-company": category_id,
                "_embed": "",
            }
            try:
                resp = self.fetch(f"{API_BASE}/alumni", params=params)
            except Exception as e:
                logger.warning(f"Thrive alumni page {page}: {e}")
                break

            items = resp.json()
            if not items:
                break

            for item in items:
                name = item.get("title", {}).get("rendered", "").strip()
                if not _is_valid_company_name(name) or name in companies:
                    continue

                # Get technology categories
                tech_ids = item.get("technology", [])
                tech_names = [tech_map.get(tid, "") for tid in tech_ids]
                tech_str = ", ".join(t for t in tech_names if t)

                # Get location
                loc_ids = item.get("locations", [])
                loc_names = [location_map.get(lid, "") for lid in loc_ids]

                # Try to get website from embedded data
                website = None
                slug = item.get("slug", "")

                category = classify(f"{name} {tech_str}")

                companies[name] = Company(
                    name=name,
                    category=category,
                    status=Status.UNKNOWN,
                    website=website,
                    description=tech_str[:500] if tech_str else None,
                    sources=[self.name],
                )

            logger.info(f"Thrive cat={category_id} page {page}: {len(items)} items, {len(companies)} total")

            if len(items) < 100:
                break
            page += 1


class ThriveAlumniScraper(BaseScraper):
    """Scrape ALL Thrive alumni via WP REST API."""

    name = "thrive_alumni"
    rate_limit_seconds = 0.5

    def scrape(self) -> list[Company]:
        companies: dict[str, Company] = {}
        tech_map = self._fetch_taxonomy("technology")
        location_map = self._fetch_taxonomy("locations")

        page = 1
        while True:
            params = {
                "per_page": 100,
                "page": page,
                "_embed": "",
            }
            try:
                resp = self.fetch(f"{API_BASE}/alumni", params=params)
            except Exception as e:
                logger.warning(f"Thrive alumni page {page}: {e}")
                break

            items = resp.json()
            if not items:
                break

            for item in items:
                name = item.get("title", {}).get("rendered", "").strip()
                if not _is_valid_company_name(name) or name in companies:
                    continue

                tech_ids = item.get("technology", [])
                tech_names = [tech_map.get(tid, "") for tid in tech_ids]
                tech_str = ", ".join(t for t in tech_names if t)

                category = classify(f"{name} {tech_str}")

                companies[name] = Company(
                    name=name,
                    category=category,
                    status=Status.UNKNOWN,
                    description=tech_str[:500] if tech_str else None,
                    sources=[self.name],
                )

            logger.info(f"Thrive alumni page {page}: {len(items)} items, {len(companies)} total")

            if len(items) < 100:
                break
            page += 1

        return list(companies.values())

    def _fetch_taxonomy(self, taxonomy: str) -> dict[int, str]:
        term_map = {}
        try:
            resp = self.fetch(
                f"{API_BASE}/{taxonomy}",
                params={"per_page": 100},
            )
            for t in resp.json():
                term_map[t["id"]] = t["name"]
        except Exception:
            pass
        return term_map
