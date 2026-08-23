# California agricultural technology directory

This repository builds a sourced directory and interactive map of agricultural technology companies active in California. The pipeline collects candidate organizations from public sources, normalizes records, and prepares data for the web visualization.

## Repository contents

- `src/`: collection, normalization, and command-line code.
- `tests/`: automated tests for the Python pipeline.
- `data/`: source and processed records used by the visualization.
- `web/`: static files for the interactive directory.
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

The directory is a research aid, not a complete registry. Company status, location, funding, and category assignments can change. Preserve source URLs and retrieval dates so that each record remains auditable.
