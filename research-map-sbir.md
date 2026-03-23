# Research Map — SBIR/STTR Data Access (2026-03-23)

## Working Sources

### 1. SBIR Bulk CSV — CORRECTED URL
**URL:** `https://data.www.sbir.gov/mod_awarddatapublic_no_abstract/award_data_no_abstract.csv`
- Old URL (`awarddatapublic/`) returns 403 — wrong path
- New URL confirmed accessible (exceeds 10MB limit = file is live)
- ~65MB, all agencies, all years
- Download with browser User-Agent: `curl -A "Mozilla/5.0..." -O`

### 2. NSF Award API — FULLY OPEN, NO AUTH
**URL:** `https://api.nsf.gov/services/v1/awards.json`
- `ProgEleCode=5371` = NSF SBIR program
- `awardeeStateCode=CA` + `keyword=agriculture` → **93 results**
- Returns: title, abstract, awardee name, city, PI name, amount, dates
- Max 25 per page, use `offset` for pagination
- Example: `?ProgEleCode=5371&awardeeStateCode=CA&keyword=agriculture&rpp=25&offset=0`
- Also try keywords: `food`, `crop`, `precision`, `soil`, `farm`, `livestock`

### 3. NIH RePORTER API — POST, NO AUTH
**URL:** `https://api.reporter.nih.gov/v2/projects/search` (POST)
- Filter: `org_states: ["CA"]`, `activity_codes: ["R43", "R44"]` (SBIR Phase I/II)
- `advanced_text_search.search_text: "agriculture"`
- Health-adjacent ag only (food safety, nutrition, biotech)

### 4. SAM.gov — FREE API KEY NEEDED
**URL:** `https://api.sam.gov/contract-awards/v1/search?api_key=<KEY>`
- `sbirSTTR=Y` filter for SBIR awards
- Up to 400K records, state + NAICS filtering
- Register at SAM.gov for free key

### 5. DOE SBIR — EXCEL DOWNLOAD
- `https://science.osti.gov/sbir/Awards` — direct Excel files
- FY 2020-2024 available, no API, needs local filtering

## Blocked Sources
- SBIR API (`api.www.sbir.gov`) — 429 "not available"
- Old bulk CSV URL — 403 (wrong path)
- Federal RePORTER — offline/deprecated

## Action Plan
1. Fix `sbir_bulk.py` to use corrected CSV URL
2. Build NSF Award API scraper (immediate, 93+ results)
3. Build NIH RePORTER scraper (POST-based)
4. Consider SAM.gov registration for broadest coverage
