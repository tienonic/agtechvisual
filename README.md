# Carrot Core agricultural technology map

Carrot Core explores the saved agricultural technology collection at [carrotcore.com](https://www.carrotcore.com/). Home selects datasets; Graph, Treemap, City and Library share the same records and selection. The original analytical reader remains at `analytical.html`, with its geography, classification, funding and size controls.

Home offers two real public datasets. The agricultural technology snapshot contains 2,695 company records from the existing reader. The AI business map contains 5,715 source records plus 8 named relationship endpoints, with 407 saved connections. Select either or both. Agricultural technology is selected by default. Each dataset retains its own record identities and connections; selecting both creates no cross-dataset edges.

The agricultural collection includes global records, with substantial US and California coverage. Categories retain their saved classifications; this collection is not a verified registry of agricultural companies. Its map cells represent source records, with no inferred company relationships.

## Build and inspect the website

Python 3.11 or later is the only build requirement. The ignored collector database is not required.

1. Run `python scripts/build_site.py` to build the explicit public export in `public-site/`.
2. Run `python -m http.server 8080 --directory public-site`, then open `http://localhost:8080/`.
3. Run `python -m unittest tests.test_site_builder` to check record preservation, duplicate IDs, evidence endpoints, deterministic output, shared assets and the public file boundary.

GitHub Pages runs that build on `main` and uploads only `public-site/`. The existing Pages deployment and `CNAME` remain in place. The build rejects unexpected files and local paths. The root `index.html` also opens the generated map when serving the repository after a build.

`public-site/build-receipt.json` records the snapshot hash, shared asset hashes, record count and exact public files. The initial snapshot came from the existing public `index.html` at commit `8ca935199e37883152388bc68b58599574588997`; its original HTML is preserved in `analytical.html`. The source payload and provenance are in `data/public-dashboard.json` and `data/public-provenance.json`.

## Update the data

Continue using the existing collectors and database. `agtech dashboard` saves the same public dashboard fields, regenerates the analytical reader, and rebuilds the explorer through `src/site_builder.py`. A website-only build uses the last saved public snapshot. Collection and enrichment are separate operations; building the website does not refresh observations.

The adapter assigns a stable hash of the exact source name plus a duplicate ordinal. It preserves repeated names and every original field in lazy evidence shards. Renaming a source record changes its ID; ordering among exact repeated names follows source order. The adapter never merges records into verified entities.

## Refresh the shared interface

The reviewed shared implementation is copied into `web/explorer/`; no independent explorer implementation lives here. To adopt an updated release, run `python scripts/refresh_explorer.py /path/to/shared/explorer`, review `web/explorer/release.json`, rebuild, and inspect the rendered views. The refresh copies only the template, browser runtime, font and font license. No source directory, private catalog or local path enters the release manifest.

The interface is an original implementation of the AxiomMath Stacks visual pattern. The bundled Source Serif 4 font uses the SIL Open Font License in `web/explorer/vendor/OFL.txt`.

## Refresh the public AI dataset

Run `python scripts/import_public_ai.py /path/to/ai-public-artifacts`, pointing at the AI publication directory that contains `public-files.json` and `manifest.public.json`. The import accepts AI alone and copies only its dataset and reachable, sanitized detail shards to `data/public-ai/`. It rejects another dataset, an unlisted file, a missing endpoint or a local path. It never imports the private multi-dataset manifest.

The cache stores exact bytes and SHA-256 hashes in `data/public-ai/import-receipt.json`. The source public manifest supplies one entry in the combined Home manifest; it does not replace Home. `python scripts/build_site.py` verifies the cache hashes and publishes only its explicit artifact list. The build and collector pipeline continue to use the separately owned agricultural snapshot. AI collection and source sanitization remain with their existing publication owner.

## Repository contents

- `src/`: collection, normalization, and command-line code.
- `tests/`: automated tests for the Python pipeline.
- `data/`: the saved public dashboard snapshot and provenance.
- `web/explorer/`: shared browser assets and their hash manifest.
- `scripts/build_site.py`: the deterministic public website build.
- `research-map-*.md`: source-specific research notes and coverage maps.

## Requirements

- Python 3.11 or later
- Network access for source collection

## Set up the project

```bash
python -m venv .venv
source .venv/Scripts/activate
python -m pip install -e ".[dev]"
```

On PowerShell, activate the environment with `.venv\Scripts\Activate.ps1`.

## Use the command-line tool

```bash
agtech --help
```

Review each collector's source terms and access limits before running it. Public listings can be incomplete or stale, so verify records before treating the directory as authoritative.

## Run tests

```bash
pytest
```

## Data limits

Live, Dead and Not recorded describe saved website observations, not current company operating status. The original public reader did not include observation dates or database IDs; the explorer leaves those dates missing.

Funding is the sum of saved round amounts in USD, not valuation. Total-raised estimates and individual rounds can overlap. A saved zero means no positive amount was present, not that the company has received no funding. Inspect the original rounds before comparing amounts.

Source labels are preserved collector names. The original snapshot omitted per-label source URLs, and some descriptions are shortened or have source encoding errors. The evidence panel retains these values without inventing missing facts. `methods.html` explains the map and links the full public snapshot.
