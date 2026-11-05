"""Build the public Carrot Core site without the collector database."""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.site_builder import build_site


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "public-site")
    args = parser.parse_args()
    receipt = build_site(ROOT, args.output)
    print(f"Built {receipt['sourceRecordCount']:,} source records and {receipt['nodeCount'] - receipt['sourceRecordCount']} relationship endpoints; {len(receipt['files'])} public files.")
