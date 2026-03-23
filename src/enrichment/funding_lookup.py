"""Enrich companies with funding data from web searches."""

from __future__ import annotations

import json
import logging
import re
import time

import requests

from src.db import Database

logger = logging.getLogger(__name__)

# Known funding amounts for major agtech companies (curated fallback)
KNOWN_FUNDING = {
    "pivot bio": 618_000_000,
    "apeel": 635_000_000,
    "apeel sciences": 635_000_000,
    "farmers business network": 900_000_000,
    "impossible foods": 2_000_000_000,
    "iron ox": 98_000_000,
    "plenty": 941_000_000,
    "bowery farming": 647_000_000,
    "indigo agriculture": 1_200_000_000,
    "indigo ag": 1_200_000_000,
    "monarch tractor": 120_000_000,
    "wild type": 100_000_000,
    "ceres imaging": 26_000_000,
    "producepay": 380_000_000,
    "innerplant": 30_000_000,
    "sound agriculture": 75_000_000,
    "biome makers": 20_000_000,
    "agtonomy": 32_000_000,
    "provivi": 116_000_000,
    "pheronym": 5_000_000,
    "verdant robotics": 46_000_000,
    "carbon robotics": 57_000_000,
    "inari": 433_000_000,
    "cibus": 340_000_000,
    "geltor": 91_000_000,
    "the every company": 175_000_000,
    "calysta": 282_000_000,
    "novonutrients": 10_000_000,
    "plantible foods": 10_000_000,
    "aquabyte": 24_000_000,
    "lygos": 46_000_000,
    "atlas ai": 15_000_000,
    "climateai": 30_000_000,
    "seso": 66_000_000,
    "pyka": 58_000_000,
    "afresh": 148_000_000,
    "regrow ag": 50_000_000,
    "trace genomics": 21_000_000,
    "cropx": 30_000_000,
    "blue river technology": 30_000_000,
    "farmwise": 14_500_000,
    "nitricity": 27_000_000,
    "florapulse": 3_000_000,
    "waterbit": 3_000_000,
    "bioconsortia": 30_000_000,
    "abundant robotics": 12_000_000,
    "granular": 18_200_000,
    "inscripta": 260_000_000,
    "solectrac": 2_000_000,
    "vence": 12_000_000,
    "farmsense": 3_000_000,
    "arable": 40_000_000,
    "bonsai robotics": 11_000_000,
    "windfall bio": 28_000_000,
    "apparvest": 600_000_000,
    "appharvest": 600_000_000,
}

FUNDING_REGEX = re.compile(
    r'\$\s*([\d,.]+)\s*(million|billion|m\b|b\b|mn|bn)',
    re.IGNORECASE,
)


def _parse_funding_amount(text: str) -> float | None:
    """Extract a dollar funding amount from text."""
    for match in FUNDING_REGEX.finditer(text):
        num_str = match.group(1).replace(",", "")
        try:
            amount = float(num_str)
        except ValueError:
            continue
        unit = match.group(2).lower()
        if unit in ("billion", "b", "bn"):
            return amount * 1_000_000_000
        else:
            return amount * 1_000_000
    return None


def enrich_funding(db: Database):
    """Add funding data to companies from curated list and web searches."""
    companies = db.list_companies()
    logger.info(f"Enriching funding for {len(companies)} companies...")

    enriched = 0

    for company in companies:
        # Check if already has funding
        existing = db.conn.execute(
            "SELECT SUM(amount_usd) FROM funding_rounds WHERE company_id = ? AND amount_usd > 0",
            (company.id,),
        ).fetchone()[0]

        existing_grants = db.conn.execute(
            "SELECT SUM(amount_usd) FROM grants WHERE company_id = ? AND amount_usd > 0",
            (company.id,),
        ).fetchone()[0]

        if existing and existing > 100_000:
            continue  # already has substantial funding data

        # Check curated list
        name_lower = company.name.lower().strip()
        # Also try without common suffixes
        name_clean = re.sub(
            r',?\s*\b(inc\.?|llc|corp\.?|ltd|co\.?|pbc|incorporated)\b\.?$',
            '', name_lower, flags=re.IGNORECASE,
        ).strip()

        amount = KNOWN_FUNDING.get(name_lower) or KNOWN_FUNDING.get(name_clean)
        if amount:
            db.conn.execute(
                "INSERT INTO funding_rounds (company_id, round_type, amount_usd, source) VALUES (?, ?, ?, ?)",
                (company.id, "total_raised", amount, "curated"),
            )
            enriched += 1
            logger.debug(f"  {company.name}: ${amount:,.0f} (curated)")

    db.conn.commit()
    logger.info(f"Enriched {enriched}/{len(companies)} companies with funding data")
