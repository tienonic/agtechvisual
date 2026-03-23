# Research Map — Thrive Agrifood (2026-03-23)

## Key Finding: WordPress REST API is FULLY OPEN

No auth, no Cloudflare on JSON endpoints. 279+ companies accessible.

## Endpoints

| Endpoint | Status | Data |
|----------|--------|------|
| `/wp-json/wp/v2/alumni?per_page=100&_embed` | 200 | All alumni, 5 pages |
| `/wp-json/wp/v2/alumni?category-company=228&_embed` | 200 | Top 50 AgTech 2026 (51) |
| `/wp-json/wp/v2/alumni?category-company=189&_embed` | 200 | Top 50 AgTech all years (53) |
| `/wp-json/wp/v2/alumni?category-company=188&_embed` | 200 | Top 50 FoodTech (53) |
| `/wp-json/wp/v2/alumni?category-company=187&_embed` | 200 | All Alumni (279) |
| `/wp-json/wp/v2/alumni?locations=11&_embed` | 200 | US companies (163) |
| `/wp-json/wp/v2/challenge-finalist?per_page=100` | 200 | 62 challenge finalists |
| `/wp-json/wp/v2/technology` | 200 | 25 tech categories |
| `/wp-json/wp/v2/locations` | 200 | 33 country labels |
| `/wp-json/wp/v2/cohort` | 200 | 25 cohort labels |

## Fields per alumni record
- `title.rendered` (company name)
- `slug`, `link`
- `featured_media` (logo URL via `_embed`)
- Taxonomy IDs: `category-company`, `technology`, `locations`, `continent`, `cohort`

## Pagination
- Max 100 per page (server cap is 50, need to paginate 5+ pages)
- Pages 1-5 confirmed working, page 6 returns 400

## Technology taxonomy IDs
- 200: Novel Crop Inputs (37)
- 201: On-Farm Decision Support (34)
- 20: Robotics & Automation (32)
- 14: Biotechnology
- 197: Agribusiness Platform
- 204: CEA
- 198: Animal Technology
