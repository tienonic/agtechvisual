"""Re-classify companies with UNKNOWN category using all available text."""

from __future__ import annotations

import logging

from src.db import Database
from src.models import Category
from src.taxonomy import classify

logger = logging.getLogger(__name__)


def reclassify_unknowns(db: Database):
    """Re-run classifier on all UNKNOWN companies using name + description."""
    unknowns = db.list_companies(category=Category.UNKNOWN)
    logger.info(f"Re-classifying {len(unknowns)} UNKNOWN companies...")

    reclassified = 0
    for company in unknowns:
        text = f"{company.name} {company.description or ''}"

        # Pull grant titles and abstracts for richer classification
        grants = db.conn.execute(
            "SELECT title, abstract FROM grants WHERE company_id = ?",
            (company.id,),
        ).fetchall()
        for g in grants:
            if g["title"]:
                text += f" {g['title']}"
            if g["abstract"]:
                text += f" {g['abstract']}"

        # Also check source records for additional text
        try:
            records = db.conn.execute(
                "SELECT raw_data FROM source_records WHERE company_id = ?",
                (company.id,),
            ).fetchall()
            for rec in records:
                if rec["raw_data"]:
                    text += f" {rec['raw_data']}"
        except Exception:
            pass  # source_records table may not exist

        new_category = classify(text)
        if new_category != Category.UNKNOWN:
            db.conn.execute(
                "UPDATE companies SET category = ? WHERE id = ?",
                (new_category.value, company.id),
            )
            reclassified += 1
            logger.debug(f"  {company.name}: {Category.UNKNOWN.value} -> {new_category.value}")

    db.conn.commit()
    logger.info(f"Re-classified {reclassified}/{len(unknowns)} companies")
