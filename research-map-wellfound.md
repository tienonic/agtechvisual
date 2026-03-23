# Research Map — Wellfound (2026-03-23)

## Summary: Low priority — only ~11 CA agriculture companies

No public API. Data embedded in `__NEXT_DATA__` JSON in page source.
Cloudflare Turnstile blocks headless browsers. Page 2+ may 403.

## Access Method
1. Fetch `https://wellfound.com/startups/l/california/agriculture`
2. Parse `<script id="__NEXT_DATA__">` JSON
3. Navigate `data.props.pageProps.apolloState.data` for `StartupResult:*` nodes
4. Fields: name, slug, companySize, markets, locations, websiteUrl, highConcept, logoUrl

## Companies found (page 1)
Seso, Orchard Robotics, Pepper, Pyka, Nitricity, Promenade Group, Farmers Business Network, Afresh, Happy Hope Dweller, Talavishiraaj Groups

## Related URLs to also try
- `/startups/l/california/food-tech-3`
- `/startups/l/california/sustainability`
- `/startups/l/san-francisco/agriculture`
