# Research Map: GrowingIL AgriFood Tech Map 2025

**Target:** https://www.growingil.org/agrifoodtechmap2025
**Date:** 2026-03-24
**Database scope:** 750+ Israeli AgriFood companies (curated to 150 on the visual map)

---

## Executive Summary

The GrowingIL AgriFood Tech Map 2025 is a **Wix Thunderbolt** site co-produced with Startup Nation Central (SNC). The visual map showcases 150 curated companies selected from SNC's Finder database of 750+ agrifood startups. The map page itself is a static visual (PDF embedded as image): **company data does not live in a GrowingIL Wix database**. The full 750+ company dataset lives exclusively in **SNC Finder** (finder.startupnationcentral.org), which is Cloudflare-protected and blocks all non-browser access.

The most actionable extraction path is **SNC Finder via browser automation** (Playwright/browser-use with a real Chrome profile). A secondary path is the **GrowingIL Wix Data API** which exposes 100 investor records with full structured data: useful for building the investor side of the dataset.

---

## Findings by Source

### 1. GrowingIL.org: Tech Stack

- **Platform:** Wix Thunderbolt (proprietary Wix SSR framework, not Next.js/React/WordPress)
- **metaSiteId:** `918183db-2639-48e3-9c6c-d5591b717cb0`
- **Cloudflare:** No: Wix's own CDN (parastorage.com, wixstatic.com)
- **Bot blocking:** None beyond Wix's standard auth

### 2. GrowingIL.org: robots.txt

```
Allow: /
Disallow: *?lightbox=
Sitemap: https://www.growingil.org/sitemap.xml
```

No disallowed paths of interest. PetalBot and AhrefsBot face crawl delays.

### 3. GrowingIL.org: Sitemap Structure

- **`/sitemap.xml`** → index pointing to two sub-sitemaps
- **`/dynamic-investors-sitemap.xml`** → 112 individual investor profile URLs at `/investors/{slug}`
- **`/pages-sitemap.xml`** → 30 static pages including:
  - `/agrifoodtechmap2025`: the 2025 map
  - `/2023israeliagtechstartupmap`: 2023 map (title: "2023 Agtech Map | GrowingIL & SNC")
  - `/startup-database`: a startup database page
  - `/investors-map`: investor map page

### 4. GrowingIL.org: Wix Data API (KEY FINDING)

The Wix cloud-data REST API is **publicly accessible** using the site's own visitor instance token.

**Endpoint:** `POST https://www.growingil.org/_api/cloud-data/v1/items/query`

**Auth:** Fetch the visitor instance token fresh from:
```
GET https://www.growingil.org/_api/v2/dynamicmodel
```
Extract `apps["22bef345-3c5b-4c18-b782-74d4085112ff"]["instance"]`

**Headers required:**
```
Authorization: ***
wix-instance: <instance_token>
Content-Type: application/json
```

**Request body:**
```json
{
  "dataCollectionId": "Investors",
  "query": { "paging": { "limit": 100 } }
}
```

**Confirmed accessible collections:**
| Collection | Records | Fields |
|------------|---------|--------|
| `Investors` | **100** | title, website, tagline, investorType, investorCategory, country, rounds, range, subSectors, portfolioCompanies, addedValue, averageAmountOfInvestmentsPerYear, image, flag, link-investors-title |

**Pagination:** Cursor-based. Response includes `pagingMetadata.cursors.next` for next page.

**Important:** The company/startup collection was NOT found under any tested name. Attempted names: Startups, Companies, AgrifoodStartups, AgrifoodTechMap, StartupDatabase, mapCompanies, IsraeliStartups, FoodTech, AgTech, and ~50 others. The agrifoodtechmap2025 page appears to be a static visual (PDF) rather than a dynamic data-backed page. **The 750 company records are in SNC Finder, not in Wix Data.**

**Investor record schema example:**
```json
{
  "title": "Iron Nation",
  "website": "https://www.ironnation.org/",
  "investorType": "VC",
  "investorCategory": "Generalist",
  "country": "Israel",
  "rounds": ["Seed", "Round A"],
  "range": ["$1M - $3M"],
  "subSectors": ["Alternative Protein", "Logistics and Supply chain", "Automation and robotics"],
  "portfolioCompanies": "Greeneye\nMediumWell\nIBI Ag",
  "averageAmountOfInvestmentsPerYear": "4-5",
  "link-investors-title": "/investors/iron-nation"
}
```

### 5. GrowingIL.org: PDF Downloads (PUBLIC)

Two PDFs are directly downloadable without authentication:

| File | URL | Size | Contents |
|------|-----|------|----------|
| **Agrifood-Tech-2025-Landscape-Map-V2.pdf** | `https://www.growingil.org/_files/ugd/0e38a4_dd262b1d908d41679e18e1fd88d7a28a.pdf` | 1.6 MB | Visual landscape map: company names embedded as image text (not machine-readable) |
| **2023 AgTech Map** | `https://918183db-2639-48e3-9c6c-d5591b717cb0.usrfiles.com/ugd/9347c4_743361b53a404bb495d79ba36460995f.pdf` | 1.4 MB | 2023 version of map |

**Caveat:** Both PDFs contain company names as graphical/vector text, not selectable text. pdftotext extracts only 13 lines (category headers). An OCR pass (tesseract, AWS Textract, GPT-4V) could potentially extract 150 company names from the 2025 map.

### 6. Startup Nation Central: Finder Platform

**URL:** https://finder.startupnationcentral.org
**Tech stack:** Next.js (confirmed by Cloudflare headers and URL patterns)
**Cloudflare:** YES: `Cf-Mitigated: challenge` (managed JS challenge)
**All direct fetches:** 403 Forbidden
**All API probes:** 403 Forbidden (`/api/v1/companies`, `/api/search`, `/graphql`, etc.)

The Finder database contains **7,200+ total Israeli startups** with ~750 tagged as agrifood.

**Known public search URL patterns (browser-accessible):**
```
https://finder.startupnationcentral.org/startups/search?alltags=agtech
https://finder.startupnationcentral.org/startups/search?alltags=agriculture
https://finder.startupnationcentral.org/startups/search?alltags=urban-farming
https://finder.startupnationcentral.org/startups/search?alltags=precision-agriculture
https://finder.startupnationcentral.org/startups/search?alltags=foodtech
https://finder.startupnationcentral.org/company_page/{slug}   ← individual company pages
https://finder.startupnationcentral.org/reports/2025-agrifood-tech-map
```

**No public API found.** No Algolia keys, no GraphQL, no REST JSON endpoints accessible without a real browser session.

### 7. Startup Nation Central: WordPress (Main Site)

**URL:** https://startupnationcentral.org
**Platform:** WordPress
**REST API:** Public, accessible at `/wp-json/wp/v2/`

**Custom post types available:**
| Post Type | REST Base | Notes |
|-----------|-----------|-------|
| `global-challenge` | `/wp-json/wp/v2/global-challenge` | Returns empty array |
| `media-article` | `/wp-json/wp/v2/media-article` | |
| Standard WP types | posts, pages, media, etc. | |

The main WordPress site does not contain the company database: it's a marketing/news site. Company data is in Finder only.

**Notable:** The agritech page (`/agritech/`) contains a Finder watchlist link:
```
https://finder.startupnationcentral.org/watchlist/6CvXBoxBXiW4npfjNekBmbEMv49lqqLvM4MjXYXj6kjmXj4RHL8j6d
```
This watchlist likely contains the curated ~150 agrifood companies from the 2025 map. Accessible via browser only.

---

## Extraction Method Recommendations (Ranked)

### Method 1: Browser Automation on SNC Finder (PRIMARY: 750+ companies)

**Why:** This is where the full 750-company database lives.
**How:** Playwright or browser-use with a real Chrome profile to bypass Cloudflare.

```python
# Target URLs to paginate:
# https://finder.startupnationcentral.org/startups/search?alltags=agtech
# https://finder.startupnationcentral.org/startups/search?sectorclassification=<agrifood_id>
# https://finder.startupnationcentral.org/startups/search?alltags=foodtech
```

The search pages use `__NEXT_DATA__` for server-side rendering: after Cloudflare passes, the JSON in `<script id="__NEXT_DATA__">` should contain the full company list for that page. Scroll/paginate to get all records.

**Sector IDs** (from search URL patterns found):
- `agxzfmlsbGlzdHNpdGVyJAsSF0Jhc2VDbGFzc2lmaWNhdGlvbk1vZGVsGICA4Kv1s8ELDA` = Precision Ag
- `mHtoryFWdL28IY7Pf1iYWt3iB1Y6DLFcx3jfEl50XWk1gcEKfNMiF2` = Farm Equipment & Treatment

**Estimated effort:** 2-4 hours with browser-use automation.

### Method 2: GrowingIL Wix Data API (IMMEDIATE: 100 investors)

**Why:** Already confirmed working, no browser needed, structured JSON.
**Status:** READY TO SCRAPE

```python
import requests, json

def get_wix_token():
    resp = requests.get(
        "https://www.growingil.org/_api/v2/dynamicmodel",
        headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"}
    )
    return resp.json()["apps"]["22bef345-3c5b-4c18-b782-74d4085112ff"]["instance"]

def query_collection(token, collection, limit=100, cursor=None):
    body = {"dataCollectionId": collection, "query": {"paging": {"limit": limit}}}
    if cursor:
        body["query"]["cursorPaging"] = {"cursor": cursor}
    return requests.post(
        "https://www.growingil.org/_api/cloud-data/v1/items/query",
        headers={"Authorization": token, "wix-instance": token, "Content-Type": "application/json"},
        json=body
    ).json()

# Fetch all 100 investors (fits in one request)
token = get_wix_token()
result = query_collection(token, "Investors", limit=100)
investors = result["items"]  # 100 records
```

**Note:** Tokens are session-scoped (short-lived). Re-fetch from dynamicmodel before each scraping session.

### Method 3: OCR the 2025 PDF Map (150 companies, names only)

**Why:** The visual map PDF is publicly accessible and contains 150 curated company names.
**How:** Use GPT-4V or AWS Textract on the PDF pages.

```
URL: https://www.growingil.org/_files/ugd/0e38a4_dd262b1d908d41679e18e1fd88d7a28a.pdf
```

Yields only company names + sector placement, no URLs/founding dates/funding.

### Method 4: Scrape Individual SNC Company Pages (detailed data, slow)

Known company page URL pattern: `https://finder.startupnationcentral.org/company_page/{slug}`

Company slugs can be discovered by:
1. Scraping the search results pages (Method 1 yields slugs as part of card data)
2. Cross-referencing with the 2023 map PDF or press coverage

Each company page contains: description, founding year, funding stage, investors, tags, employee count, location.

### Method 5: 2023 Map + SNC 2025 Watchlist

The 2023 map is available at:
```
https://918183db-2639-48e3-9c6c-d5591b717cb0.usrfiles.com/ugd/9347c4_743361b53a404bb495d79ba36460995f.pdf
```

The SNC agrifood watchlist (likely 150 curated companies from the 2025 map):
```
https://finder.startupnationcentral.org/watchlist/6CvXBoxBXiW4npfjNekBmbEMv49lqqLvM4MjXYXj6kjmXj4RHL8j6d
```
Accessible via browser only.

---

## What's NOT There

| Attempted | Result |
|-----------|--------|
| Airtable embed | Not present |
| Google Sheets embed | Not present |
| Embedded JSON company array in page HTML | Not present |
| Wix Data collection for companies/startups | Not found (40+ name attempts) |
| SNC Finder REST/GraphQL/Algolia API | All 403 (Cloudflare) |
| GrowingIL download/export button | Not present |
| WordPress REST API with company data | Not present (WP site is marketing-only) |

---

## Data Architecture Summary

```
750+ companies
└── SNC Finder database (finder.startupnationcentral.org)
    ├── Browser-only access (Cloudflare blocks curl/requests)
    ├── Search: /startups/search?alltags=agtech (paginated)
    └── Individual pages: /company_page/{slug}

150 curated companies (2025 visual map)
├── PDF: growingil.org/_files/ugd/0e38a4_...pdf  ← image text, OCR needed
└── SNC Finder watchlist: /watchlist/6CvXBoxBXiW4npfjNekBmbEMv49lqqLvM4MjXYXj6kjmXj4RHL8j6d

100 investors (GrowingIL Wix Data)
└── Wix Data API: growingil.org/_api/cloud-data/v1/items/query  ← READY TO SCRAPE
    Collection: "Investors"
    Fields: title, website, type, country, sectors, portfolio companies, rounds, range
```

---

## Recommended Action Plan

1. **Immediate:** Run the Wix Data API scraper to collect all 100 investors (Method 2 above, ~10 min to code)
2. **Primary:** Use browser-use with `--profile Default` to scrape SNC Finder search results for `alltags=agtech`, `alltags=foodtech`, `alltags=precision-agriculture`, `sectorclassification=<agrifood>` (Method 1)
3. **Supplement:** Run GPT-4V OCR on the 2025 PDF map to extract the 150 featured company names (Method 3)
4. **Cross-reference:** Match OCR company names against SNC Finder to get full records

**Note on WDAC:** browser-use with canvas.node is blocked on this Windows machine. Use Playwright directly or headless Chrome via WSL as alternatives.
