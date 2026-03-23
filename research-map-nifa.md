# Research Map — NIFA (2026-03-23)

## Key Finding: `perPage` is the correct parameter (not `size`)

The API uses `perPage` for page size. Using `size` was silently ignored, defaulting to 1 row.

## Working Endpoints

### JSON API (paginated)
```
GET https://portal.nifa.usda.gov/lmd4/recent_awards/get_data.js
    ?perPage=1000&page=1&columnFilters={"State Name":"California"}
```
- Returns 1000 rows per page
- CA total: 2,821 rows (3 pages at perPage=1000)
- All rows have HTML-wrapped values: `<div class='string'>...</div>`

### CSV Download (single request!)
```
GET https://portal.nifa.usda.gov/lmd4/recent_awards/get_data.csv
    ?columnFilters=%7B%22State+Name%22%3A%22California%22%7D
```
- Returns ALL 2,821 CA rows as clean CSV (727 KB)
- Headers: Award Date, Grant Number, Proposal Number, Grant Title, State Name, Grantee Name, Award Dollars, Program Name, Program Area Name, Public Flag

### USASpending crosswalk (pre-filtered private companies)
```
POST https://api.usaspending.gov/api/v2/search/spending_by_award/
{
  "filters": {
    "award_type_codes": ["02","03","04","05"],
    "agencies": [{"type":"awarding","tier":"subtier","name":"National Institute of Food and Agriculture"}],
    "recipient_locations": [{"country":"USA","state":"CA"}],
    "recipient_type_names": ["for_profit_organization","small_business","corporate_entity_not_tax_exempt"]
  }
}
```
- 322 grants to ~150 private CA companies

## Parameters
- `perPage` (int) — items per page (1000 works)
- `page` (int) — 1-indexed
- `sortColumn` (int) — column index
- `columnFilters` (JSON string) — object format: `{"State Name":"California"}`
