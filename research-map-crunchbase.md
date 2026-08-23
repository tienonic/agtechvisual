# Research Map: Crunchbase Data Access

**Target:** crunchbase.com | **Type:** web | **Date:** 2026-03-24

## Findings

### Direct Access: BLOCKED
- Company profile pages return **403** to non-browser requests
- AI crawlers explicitly blocked in robots.txt (Claude, GPTBot, etc.)
- Sitemap index returns 403
- Basic API **discontinued**: no new API keys issued

### Crunchbase Basic API (deprecated)
- 3 endpoints existed: Organization Search, Entity Lookup, Autocomplete
- Rate limit was 200 calls/min
- **No longer accepting new registrations**
- Existing keys may still work if user has one

### Google Search Snippet Extraction
- `site:crunchbase.com "[company name]"` returns profile links
- Snippets show: round count, latest round date, investor count, short description
- **Funding amounts are OBFUSCATED**: shown as "obfuscated amount" without Pro subscription
- Useful for: confirming a company exists on Crunchbase, getting round count

### What DOES Work (current approach)
Our WebSearch queries like `"[company name]" raised funding series` are actually the best approach because:
1. News articles (AgFunder, TechCrunch, press releases) contain the actual dollar amounts
2. No paywall or obfuscation
3. Often more detail (lead investor, round type, use of funds)
4. This is what we've been doing and it's finding $10M-$140M rounds

## Actionable Alternatives

### 1. Apify Crunchbase Scraper (best option for bulk)
- Free trial available
- Headless browser approach bypasses 403
- Can extract funding amounts that are visible to logged-in free users
- **Action:** Register at apify.com, use their Crunchbase scraper with our 470 company slugs

### 2. Piloterr API
- $1.50 per 1,000 records
- Pre-scraped Crunchbase data including funding rounds
- **Action:** ~$1 total cost to pull all remaining companies

### 3. Browser-use with Chrome profile
- `browser-use --profile "Default" open https://crunchbase.com/organization/[slug]`
- If user has a free Crunchbase account, logged-in pages show more data
- Could automate: navigate to each company page, extract funding from DOM
- **Action:** Build a browser-use loop that visits each Crunchbase page

### 4. News article approach (CURRENT: already working well)
- `"[company name]" "raised" OR "funding" OR "series"` via WebSearch
- AgFunder News, TechCrunch, press releases have unobfuscated amounts
- This is our overnight cron approach: already found $400M+ across researched companies

### 5. Tracxn free snippets
- Search results from `site:tracxn.com "[company name]"` sometimes show funding in snippets
- Already appearing in our search results organically

## Recommendation for Morning

**Don't build a Crunchbase scraper.** The news-article WebSearch approach is already finding more detailed funding data than Crunchbase snippets would provide. The overnight cron is pulling $10M-$140M rounds with investor names and round types from press coverage.

**If you want more coverage:** Register for Apify free trial and run their Crunchbase scraper on the ~470 remaining company slugs as a one-shot bulk enrichment. Cost: $0 (free trial).
