"""CLI entrypoint for the AgTech CA scraper."""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from datetime import date
from pathlib import Path

from src.db import Database
from src.models import Company

DB_PATH = Path(__file__).parent.parent / "agtech_ca.db"
EXPORTS_DIR = Path(__file__).parent.parent / "exports"

SCRAPERS = {
    "usaspending": "src.scrapers.usaspending:USASpendingScraper",
    "sbir": "src.scrapers.sbir:SBIRScraper",
    "sbir_bulk": "src.scrapers.sbir_bulk:SBIRBulkScraper",
    "nifa": "src.scrapers.nifa:NIFAScraper",
    "wgcit": "src.scrapers.wgcit:WGCITScraper",
    "growthlist": "src.scrapers.growthlist:GrowthListScraper",
    "world_agritech": "src.scrapers.world_agritech:WorldAgriTechScraper",
    "thrive": "src.scrapers.thrive:ThriveTop50Scraper",
    "thrive_alumni": "src.scrapers.thrive:ThriveAlumniScraper",
    "wellfound": "src.scrapers.wellfound:WellfoundScraper",
    "sec_edgar": "src.scrapers.sec_edgar:SECEdgarScraper",
    "nsf_sbir": "src.scrapers.nsf_sbir:NSFSBIRScraper",
    "seed_list": "src.scrapers.seed_list:SeedListScraper",
}

ENRICHERS = {
    "classify": "src.enrichment.classifier:reclassify_unknowns",
    "tags": "src.enrichment.tag_classifier:reclassify_with_tags",
    "dns": "src.enrichment.dns_check:check_websites",
    "wayback": "src.enrichment.wayback:check_wayback",
    "funding": "src.enrichment.funding_lookup:enrich_funding",
}


def _match_to_company(name_hint, companies, id_map, db):
    """Match a grant/funding to a company by name hint or slug lookup."""
    from src.dedup import to_slug
    if name_hint and name_hint in id_map:
        return id_map[name_hint]
    if name_hint:
        slug = to_slug(name_hint)
        company = db.get_company_by_slug(slug)
        if company:
            return company.id
    return None


def _load_scraper(name: str):
    if name not in SCRAPERS:
        print(f"Unknown scraper: {name}. Available: {', '.join(SCRAPERS)}")
        sys.exit(1)
    module_path, class_name = SCRAPERS[name].rsplit(":", 1)
    import importlib
    mod = importlib.import_module(module_path)
    return getattr(mod, class_name)


def cmd_scrape(args):
    db = Database(DB_PATH)
    names = list(SCRAPERS.keys()) if args.source == "all" else [args.source]

    for name in names:
        print(f"--- Scraping: {name} ---")
        try:
            scraper_cls = _load_scraper(name)
        except Exception as e:
            print(f"  Skipping {name}: {e}")
            continue

        scraper = scraper_cls()
        try:
            companies = scraper.scrape()
        except Exception as e:
            print(f"  Error scraping {name}: {e}")
            continue

        from src.dedup import to_slug

        inserted = 0
        company_id_map: dict[str, int] = {}
        for c in companies:
            try:
                cid = db.upsert_company(c)
                company_id_map[c.name] = cid
                inserted += 1
            except Exception as e:
                logging.debug(f"Failed to upsert {c.name}: {e}")

        print(f"  {len(companies)} companies found, {inserted} upserted")

        # Persist grants (USASpending, SBIR, NIFA)
        if hasattr(scraper, "grants") and scraper.grants:
            grant_count = 0
            for i, g in enumerate(scraper.grants):
                # Match by title snippet or by parallel company
                hint = companies[i].name if i < len(companies) else None
                cid = _match_to_company(hint, companies, company_id_map, db)
                if cid:
                    g.company_id = cid
                    try:
                        db.insert_grant(g)
                        grant_count += 1
                    except Exception:
                        pass
            print(f"  {grant_count} grants stored")

        # Persist funding rounds (GrowthList)
        if hasattr(scraper, "funding_rounds") and scraper.funding_rounds:
            fr_count = 0
            for fr in scraper.funding_rounds:
                # GrowthList stores company name in investors field
                hint = fr.investors
                cid = _match_to_company(hint, companies, company_id_map, db)
                if cid:
                    fr.company_id = cid
                    fr.investors = None  # clear the temp hint
                    try:
                        db.insert_funding_round(fr)
                        fr_count += 1
                    except Exception:
                        pass
            print(f"  {fr_count} funding rounds stored")

    db.close()


def cmd_stats(args):
    db = Database(DB_PATH)
    s = db.stats()
    print(f"\nTotal companies: {s['total_companies']}\n")

    if s["by_category"]:
        print("By category:")
        for cat, count in s["by_category"].items():
            print(f"  {cat:20s} {count}")

    if s["by_status"]:
        print("\nBy status:")
        for status, count in s["by_status"].items():
            print(f"  {status:20s} {count}")

    db.close()


def _csv_safe(val) -> str:
    """Sanitize a value for CSV export to prevent formula injection.

    Excel/Sheets execute formulas when cells start with =, +, -, @, tab, or CR.
    Prefix with a single quote to force text interpretation.
    """
    if val is None:
        return ""
    s = str(val)
    if s and s[0] in ("=", "+", "-", "@", "\t", "\r", "\n"):
        return "'" + s
    return s


def cmd_export(args):
    db = Database(DB_PATH)
    companies = db.list_companies()
    today = date.today().isoformat()

    EXPORTS_DIR.mkdir(exist_ok=True)

    if args.format == "csv":
        path = EXPORTS_DIR / f"agtech_ca_{today}.csv"
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "name", "category", "hq_city", "hq_state",
                "state_of_incorporation", "country", "founded_year",
                "status", "website", "website_live", "description", "sources",
            ])
            for c in companies:
                writer.writerow([
                    _csv_safe(c.name), c.category.value,
                    _csv_safe(c.hq_city), _csv_safe(c.hq_state),
                    _csv_safe(c.state_of_incorporation), _csv_safe(c.country),
                    c.founded_year,
                    c.status.value, _csv_safe(c.website), c.website_live,
                    _csv_safe((c.description or "")[:200]),
                    "|".join(c.sources),
                ])
        print(f"Exported {len(companies)} companies to {path}")

    elif args.format == "json":
        path = EXPORTS_DIR / f"agtech_ca_{today}.json"
        data = []
        for c in companies:
            data.append({
                "name": c.name, "category": c.category.value,
                "hq_city": c.hq_city, "hq_state": c.hq_state,
                "founded_year": c.founded_year, "status": c.status.value,
                "website": c.website, "description": c.description,
                "sources": c.sources,
            })
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"Exported {len(companies)} companies to {path}")

    db.close()


def cmd_enrich(args):
    db = Database(DB_PATH)
    enricher_name = args.enricher

    if enricher_name not in ENRICHERS:
        print(f"Unknown enricher: {enricher_name}. Available: {', '.join(ENRICHERS)}")
        sys.exit(1)

    module_path, func_name = ENRICHERS[enricher_name].rsplit(":", 1)
    import importlib
    mod = importlib.import_module(module_path)
    func = getattr(mod, func_name)

    print(f"--- Enriching: {enricher_name} ---")
    if enricher_name == "dns":
        import asyncio
        asyncio.run(func(db))
    else:
        func(db)

    db.close()


def cmd_refine(args):
    db = Database(DB_PATH)

    if args.refine_action == "plan":
        from src.enrichment.web_refine import get_enrichment_queue, make_batches, build_agent_prompt
        queue = get_enrichment_queue(db, limit=args.limit)
        print(f"Found {len(queue)} UNKNOWN companies for enrichment")

        batches = make_batches(queue, batch_size=args.batch_size)
        print(f"Split into {len(batches)} batches of ~{args.batch_size}\n")

        prompts_dir = EXPORTS_DIR / "refine_prompts"
        prompts_dir.mkdir(parents=True, exist_ok=True)

        for i, batch in enumerate(batches):
            prompt = build_agent_prompt(batch, i + 1)
            path = prompts_dir / f"batch_{i+1:02d}.txt"
            with open(path, "w", encoding="utf-8") as f:
                f.write(prompt)
            print(f"Batch {i+1}: {len(batch)} companies -> {path}")

        print(f"\nPrompts saved to {prompts_dir}/")

    elif args.refine_action == "import":
        from src.enrichment.web_refine import import_results
        path = Path(args.path)
        stats = import_results(db, path, dry_run=args.dry_run)
        prefix = "[DRY RUN] " if args.dry_run else ""
        print(f"\n{prefix}Import summary:")
        print(f"  Total results: {stats['total']}")
        print(f"  Updated:       {stats['updated']}")
        print(f"  Skipped:       {stats['skipped']}")
        print(f"  Not found:     {stats['not_found']}")
        if stats.get("fields"):
            print("  Fields updated:")
            for field, count in stats["fields"].items():
                print(f"    {field}: {count}")

    elif args.refine_action == "normalize":
        count = db.normalize_country_values()
        print(f"Normalized {count} country values")

    db.close()


def cmd_dashboard(args):
    """Generate interactive treemap dashboard HTML."""
    db = Database(DB_PATH)

    from src.dedup import domain_from_url

    companies = db.list_companies()
    company_data = []
    for c in companies:
        # Get all funding rounds
        rounds = db.conn.execute(
            "SELECT amount_usd, round_type, date FROM funding_rounds WHERE company_id = ? ORDER BY date",
            (c.id,),
        ).fetchall()
        funding_total = sum(r["amount_usd"] or 0 for r in rounds)
        funding_rounds = [
            {"amount": r["amount_usd"], "type": r["round_type"], "date": r["date"]}
            for r in rounds if r["amount_usd"]
        ]

        fields_filled = sum(1 for v in [
            c.hq_city, c.hq_state, c.founded_year, c.website,
            c.description, c.website_live is not None,
        ] if v)

        # Build Wayback URL for dead sites
        wayback_url = None
        if c.website_live is False and c.website:
            domain = domain_from_url(c.website)
            if domain:
                wayback_url = f"https://web.archive.org/web/*/{domain}"

        company_data.append({
            "name": c.name,
            "category": c.category.value,
            "country": c.country or "US",
            "hq_state": c.hq_state,
            "status": "LIVE" if c.website_live else ("DEAD" if c.website_live is False else "UNKNOWN"),
            "website": c.website,
            "funding": funding_total,
            "funding_rounds": funding_rounds,
            "description": (c.description or "")[:150],
            "sources": c.sources,
            "data_richness": fields_filled,
            "wayback_url": wayback_url,
        })

    stats = db.stats()
    total_funding = db.conn.execute(
        "SELECT SUM(amount_usd) FROM funding_rounds WHERE amount_usd > 0"
    ).fetchone()[0] or 0

    live_count = sum(1 for c in company_data if c["status"] == "LIVE")
    dead_count = sum(1 for c in company_data if c["status"] == "DEAD")

    dashboard_data = {
        "companies": company_data,
        "stats": {
            "total": len(company_data),
            "total_funding": total_funding,
            "live": live_count,
            "dead": dead_count,
            "by_category": stats["by_category"],
        },
    }

    from src.dashboard_template import render_dashboard
    output_path = Path(__file__).parent.parent / "index.html"
    render_dashboard(dashboard_data, output_path)
    print(f"Dashboard written to {output_path}")
    db.close()


def main():
    parser = argparse.ArgumentParser(description="AgTech CA Company Scraper")
    sub = parser.add_subparsers(dest="command")

    p_scrape = sub.add_parser("scrape", help="Scrape a data source")
    p_scrape.add_argument("source", help="Source name or 'all'")
    p_scrape.set_defaults(func=cmd_scrape)

    p_enrich = sub.add_parser("enrich", help="Enrich existing data")
    p_enrich.add_argument("enricher", help="Enricher name: classify, dns, wayback")
    p_enrich.set_defaults(func=cmd_enrich)

    p_stats = sub.add_parser("stats", help="Show database statistics")
    p_stats.set_defaults(func=cmd_stats)

    p_dash = sub.add_parser("dashboard", help="Generate interactive treemap dashboard")
    p_dash.set_defaults(func=cmd_dashboard)

    p_refine = sub.add_parser("refine", help="Web-based data refinement")
    refine_sub = p_refine.add_subparsers(dest="refine_action")
    p_refine_plan = refine_sub.add_parser("plan", help="Generate research batch prompts")
    p_refine_plan.add_argument("--limit", type=int, default=None, help="Max companies")
    p_refine_plan.add_argument("--batch-size", type=int, default=25, help="Companies per batch")
    p_refine_import = refine_sub.add_parser("import", help="Import research results")
    p_refine_import.add_argument("path", help="JSON file or directory")
    p_refine_import.add_argument("--dry-run", action="store_true")
    refine_sub.add_parser("normalize", help="Normalize country values")
    p_refine.set_defaults(func=cmd_refine)

    p_export = sub.add_parser("export", help="Export data")
    p_export.add_argument("format", choices=["csv", "json"])
    p_export.set_defaults(func=cmd_export)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args.func(args)


if __name__ == "__main__":
    main()
