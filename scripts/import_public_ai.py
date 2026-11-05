"""Cache the AI publication's exact allowlisted dataset and evidence shards."""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.public_ai import import_public_ai


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Directory containing public-files.json and manifest.public.json")
    receipt = import_public_ai(parser.parse_args().source, ROOT / "data/public-ai")
    print(f"Imported {receipt['sourceRecordCount']:,} AI source records, {receipt['relationshipEndpointCount']} relationship endpoints and {len(receipt['files'])} exact public artifacts.")
