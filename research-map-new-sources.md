# Research Map — New Data Sources (2026-03-23)

## High Priority (implement now)

### BuiltIn.com — JSON-LD in HTML, ~20 CA agtech companies
- URL: `https://builtin.com/companies/location/na/usa/ca/type/agriculture-startups`
- Data in `<script type="application/ld+json">` as ItemList
- No auth, standard User-Agent works
- Also try: builtinsf.com, builtinla.com variants

### AgStart — Static HTML, ~15 Sacramento ag biotech
- URL: `https://www.agstart.org/innovators.html`
- Direct company URLs listed: botanical-solution.com, pheronym.com, turtletree.com, etc.
- Simple HTML scrape

### WG Innovation Center — Static HTML, ~15 Salinas startups
- URL: `https://wginnovation.com/startups/`
- Company slugs visible, detail pages at `/startups/{slug}/`
- Distinct from existing WGCIT scraper

### AgFunder News WP API — 681 articles, mine for company names
- URL: `https://agfundernews.com/wp-json/wp/v2/posts?categories=773,466&per_page=100`
- Category 773 = Agtech, 466 = Startups & Funding
- 681 articles, each naming 1-5 funded companies
- No auth needed

## Dead/Blocked Sources
- PatentsView API: 410 Gone (discontinued)
- Crunchbase: 403 (paid API only)
- Plug and Play: JS-rendered SPA, no API
- CDFA: No company registry
- OpenCorporates: Requires API key (free tier available)
